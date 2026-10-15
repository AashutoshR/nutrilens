"""Retrieval over the USDA FoodData Central database (data/foods.db, built by scripts/build_food_db.py).

This is the "R" in NutriLens's RAG pipeline: the AI only names the foods it sees, and every
nutrient value comes from a matching USDA record found here with full-text search.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from functools import lru_cache

from .config import BACKEND_DIR
from .schemas import Nutrients

DB_PATH = BACKEND_DIR / "data" / "foods.db"
NUTRIENT_KEYS = list(Nutrients.model_fields)

SOURCES = {
    "survey_fndds_food": "USDA · foods as eaten",
    "sr_legacy_food": "USDA · standard reference",
    "foundation_food": "USDA · foundation foods",
    "branded_food": "Branded product",
}

# Generic foods and prepared dishes are what appear on plates; branded products only when asked for
# or when no generic food covers a dish name (e.g. "butter chicken").
TYPE_PENALTY = {"survey_fndds_food": 0.0, "sr_legacy_food": 0.3, "foundation_food": 0.5, "branded_food": 1.5}
# Descriptions that are rarely what a photo shows unless the query says so.
ODD_WORDS = ("babyfood", "baby food", "infant", "formula", "dehydrated", "powder", "dry mix", "unprepared",
             "freeze-dried", "frozen concentrate", "toddler", "imitation", "substitute", "replacement", "alaska native",
             "meatless", "vegetarian", "meat substitute")
# Words that turn a food into a different, composite item ("salami sandwich", "banana pudding").
COMPOSITE_WORDS = {
    "sandwich", "sauce", "juice", "pudding", "chips", "soup", "dip", "ball", "souffle", "pie", "cake", "dressing",
    "spread", "nectar", "tapenade", "oil", "croquette", "pilaf", "rolls", "roll", "cocktail", "drink", "flavored",
    "candy", "bar", "cereal", "muffin", "bread", "sub", "wrap", "burrito", "casserole", "salad", "stew", "pizza",
    "biscuit", "cookie", "smoothie", "shake", "baby", "fried", "breaded", "canned", "frozen", "crackers", "snack",
    "seasoning", "mix", "flavor", "chunks", "nugget", "nuggets", "patty", "roll",
}
# How it was cooked: nice to match, but never required ("roasted chicken" should still find chicken).
COOKING_WORDS = {"roasted", "roast", "grilled", "baked", "boiled", "steamed", "sauteed", "broiled", "toasted", "smoked",
                 "poached", "stewed", "braised", "cooked", "seared", "pan"}
# Foods eaten cooked: a "raw" record is the wrong default for them.
COOKED_FOODS = {"chicken", "beef", "pork", "turkey", "lamb", "fish", "salmon", "tuna", "cod", "shrimp", "egg", "rice",
                "pasta", "bacon", "sausage", "steak", "duck", "lentil", "bean", "potato", "noodle"}

STOP_WORDS = {
    "a", "an", "and", "the", "of", "with", "in", "on", "some", "few", "several", "piece", "pieces", "slice",
    "slices", "sliced", "small", "large", "medium", "bowl", "plate", "serving", "portion", "dish", "side",
    "fresh", "homemade", "style", "assorted", "mixed", "wedge", "wedges", "cube", "cubes", "cubed", "bite",
    "bites", "chunk", "chunks", "strip", "strips", "half", "whole", "handful", "cup", "cups", "glass",
}
SYNONYMS = {
    "baguette": "french bread", "prosciutto": "prosciutto ham", "charcuterie": "",
    "mandarin": "tangerine", "clementine": "tangerine", "aubergine": "eggplant", "courgette": "zucchini",
    "fries": "french fries", "coriander": "cilantro", "garbanzo": "chickpeas",
    "capsicum": "pepper", "rocket": "arugula", "prawn": "shrimp", "prawns": "shrimp", "curd": "yogurt",
    "dal": "lentils", "dhal": "lentils", "roti": "chapati", "chapatti": "chapati",
    "basmati": "white", "jasmine": "white", "beetroot": "beets", "yoghurt": "yogurt", "porridge": "oatmeal",
}

_local = threading.local()


def available() -> bool:
    return DB_PATH.exists()


def _db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


PHRASES = {
    "cured meat": "ham", "cold cut": "luncheon meat", "cold cuts": "luncheon meat", "deli meat": "luncheon meat",
    "lunch meat": "luncheon meat", "fresh cheese": "cheese", "soft cheese": "brie cheese", "hard cheese": "cheddar cheese",
    "flatbread": "pita bread", "spring onion": "green onion", "ice lolly": "ice pop",
}


# Vague names with no "NFS" (typical) record in USDA get a sensible, commonly eaten default.
DEFAULTS = {
    "chicken": "chicken breast rotisserie skin not eaten", "roasted chicken": "chicken breast rotisserie skin not eaten",
    "chicken piece": "chicken breast rotisserie skin not eaten", "grilled chicken": "chicken breast grilled skin not eaten",
    "vegetables": "vegetables mixed cooked boiled", "mixed vegetables": "vegetables mixed cooked boiled",
    "roasted vegetables": "vegetables mixed cooked boiled", "steamed vegetables": "vegetables mixed cooked boiled",
    "meat": "beef roast", "salad": "mixed salad greens raw", "green salad": "mixed salad greens raw",
}


def _terms(text: str) -> list[str]:
    text = DEFAULTS.get(text.lower().strip(), text.lower())
    for phrase, replacement in PHRASES.items():
        text = re.sub(rf"\b{phrase}\b", replacement, text)
    words = []
    for w in re.findall(r"[a-z]+", text):
        w = SYNONYMS.get(w, w)
        words.extend(x for x in w.split() if x and x not in STOP_WORDS and len(x) > 1)
    return list(dict.fromkeys(words))


def _stem(word: str) -> str:
    """Plural to singular, enough to compare food names: tomatoes→tomato, berries→berry, olives→olive."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("oes", "ses", "xes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


CATEGORY_HEADS = {"fish", "cheese", "beef", "pork", "chicken", "turkey", "lamb", "egg", "bread", "rice", "pasta",
                  "milk", "coffee", "tea", "nut", "seed", "bean", "squash", "pepper", "lettuce", "cereal"}

# Variants that are rarely the plain food on a plate unless the query asks for them.
QUALIFIERS = {_stem(w) for w in ("reduced", "low", "free", "light", "lite", "diet", "glutinous", "pickled", "candied",
                                 "mixture", "unenriched", "fortified", "sugar", "calorie", "nonfat", "skim", "canned",
                                 "drained", "can")}
COMPOSITE_STEMS = {_stem(w) for w in COMPOSITE_WORDS}


def _row_to_food(row: sqlite3.Row) -> dict:
    nutrients = {k: (row[k] if row[k] is not None else 0.0) for k in NUTRIENT_KEYS}
    return {
        "fdc_id": row["fdc_id"],
        "description": row["description"],
        "source": SOURCES.get(row["data_type"], row["data_type"]),
        "data_type": row["data_type"],
        "category": row["category"],
        "brand": row["brand"],
        "ingredients": row["ingredients"],
        "per_100g": nutrients,
    }


def _coverage(desc_words: set[str], terms: list[str]) -> int:
    return sum(1 for t in terms if _stem(t) in desc_words)


def _score(row: sqlite3.Row, terms: list[str], query_text: str) -> float:
    desc = row["description"].lower()
    words = {_stem(w) for w in re.findall(r"[a-z]+", desc)}
    stems = {_stem(t) for t in terms}
    segments = desc.split(",")
    head_words = [_stem(w) for w in re.findall(r"[a-z]+", segments[0])]
    # USDA often names foods category-first ("Fish, salmon, NFS", "Cheese, Brie"): the food is the next segment.
    if len(segments) > 1 and head_words and set(head_words) <= CATEGORY_HEADS and not set(head_words) & stems:
        head_words = [_stem(w) for w in re.findall(r"[a-z]+", segments[1])]

    score = TYPE_PENALTY.get(row["data_type"], 1.0) + 0.05 * row["rank"]
    score -= 2.0 * _coverage(words, terms)                       # every query word present
    if head_words and set(head_words) <= stems:                  # "Salami, NFS" / "Tomatoes, raw" for "salami" / "tomato"
        score -= 3.0
    elif head_words and head_words[0] in stems:
        score -= 1.0
    extra = set(head_words) - stems
    score += 1.2 * len(extra & COMPOSITE_STEMS) + 0.15 * len(extra)  # "salami sandwich", "banana pudding"
    score += 0.2 * desc.count(",")                                # fewer qualifiers = more generic
    score += 0.8 * len((words & QUALIFIERS) - stems)              # "reduced calorie", "glutinous", "pickled"
    if "nfs" in words:                                            # USDA's "not further specified": the typical version
        score -= 0.6
    if ", raw" in desc:                                           # raw is right for fruit and veg, wrong for meat or rice
        score += 1.2 if (words & COOKED_FOODS) and "raw" not in stems else -0.6
    if not any(w in query_text for w in ODD_WORDS) and any(w in desc for w in ODD_WORDS):
        score += 4.0
    return score


def _fts(table: str, match: str, branded_only: bool = False, limit: int = 400) -> list[sqlite3.Row]:
    extra = "AND f.data_type = 'branded_food'" if branded_only else ""
    sql = f"""SELECT f.*, bm25({table}) AS rank FROM {table} JOIN foods f ON f.fdc_id = {table}.rowid
              WHERE {table} MATCH ? {extra} ORDER BY rank LIMIT ?"""
    return _db().execute(sql, (match, limit)).fetchall()


@lru_cache(maxsize=4096)
def _search_cached(text: str, limit: int, include_branded: bool) -> tuple:
    terms = _terms(text)
    if not terms:
        return ()
    core = [t for t in terms if t not in COOKING_WORDS] or terms  # cooking words rank results but aren't required
    quoted = [f'"{t}"' for t in core]
    rows = _fts("generic_fts", " AND ".join(quoted)) or _fts("generic_fts", " OR ".join(quoted))
    ranked = sorted(rows, key=lambda r: _score(r, terms, text))

    # A dish name the generic foods don't fully cover ("butter chicken", "margherita pizza"): try products by that name.
    best_cover = _coverage({_stem(w) for w in re.findall(r"[a-z]+", ranked[0]["description"].lower())}, core) if ranked else 0
    if include_branded or (len(core) >= 2 and best_cover < len(core)):
        branded = _fts("foods_fts", " AND ".join(quoted), branded_only=True, limit=150)
        if branded:
            ranked = sorted(list(ranked) + list(branded), key=lambda r: _score(r, terms, text))
    return tuple(_row_to_food(r) for r in ranked[:limit])


def search(text: str, limit: int = 8, include_branded: bool = False) -> list[dict]:
    if not available():
        return []
    return [dict(f) for f in _search_cached(text.strip().lower(), limit, include_branded)]


def get(fdc_id: int) -> dict | None:
    if not available():
        return None
    row = _db().execute("SELECT * FROM foods WHERE fdc_id = ?", (fdc_id,)).fetchone()
    return _row_to_food(row) if row else None


def by_barcode(gtin: str) -> dict | None:
    if not available():
        return None
    digits = re.sub(r"\D", "", gtin)
    row = _db().execute("SELECT * FROM foods WHERE gtin = ? OR gtin = ? LIMIT 1", (digits, digits.zfill(14))).fetchone()
    return _row_to_food(row) if row else None


_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "half": 0.5,
                 "several": 3, "few": 3, "couple": 2}
_UNITS = ("slice", "cup", "piece", "tbsp", "tablespoon", "tsp", "teaspoon", "oz", "wedge", "stalk", "leaf",
          "fruit", "medium", "large", "small", "bowl", "serving", "link", "patty", "fillet", "egg", "roll", "bun")


def portion_grams(fdc_id: int, portion_text: str) -> float | None:
    """Turn "2 slices" into grams using USDA's own portion weights for the matched food."""
    text = portion_text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    count = float(m.group(1)) if m else next((v for w, v in _NUMBER_WORDS.items() if re.search(rf"\b{w}\b", text)), None)
    unit = next((u for u in _UNITS if u in text), None)
    if count is None or unit is None:
        return None
    rows = _db().execute("SELECT description, grams FROM portions WHERE fdc_id = ?", (fdc_id,)).fetchall()
    for r in rows:
        desc = r["description"].lower()
        if unit in desc:
            amount = re.match(r"(\d+(?:\.\d+)?)", desc)
            per_unit = r["grams"] / (float(amount.group(1)) if amount and float(amount.group(1)) > 0 else 1)
            return round(count * per_unit)
    return None


def stats() -> dict:
    if not available():
        return {"available": False}
    db = _db()
    counts = dict(db.execute("SELECT data_type, COUNT(*) FROM foods GROUP BY data_type").fetchall())
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    return {"available": True, "foods": sum(counts.values()), "by_type": counts, **meta}
