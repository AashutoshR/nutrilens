"""Build NutriLens's recipe database (data/recipes.db) from the Food.com "Recipes and Reviews" dataset.

Download it from https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews (free Kaggle account), then:

    python scripts/build_recipe_db.py path/to/archive.zip      (or path/to/recipes.csv)

Each recipe is tagged once at build time (allergens, meat/fish/dairy level, cuisine) so searches can
filter by the user's diet and allergens instantly.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.insights import detect_allergens  # noqa: E402
from app.knowledge import CUISINES  # noqa: E402

csv.field_size_limit(10_000_000)

# Food.com keywords that name a cuisine, mapped to NutriLens cuisine names.
CUISINE_ALIASES = {c.lower(): c for c in CUISINES} | {
    "southwest asia (middle east)": "Middle Eastern", "middle eastern": "Middle Eastern", "lebanese": "Middle Eastern",
    "turkish": "Middle Eastern", "moroccan": "Middle Eastern", "pakistani": "Indian",
    "southwestern u.s.": "Mexican", "tex mex": "Mexican", "creole": "American", "cajun": "American",
    "southern": "American", "hawaiian": "American", "portuguese": "Spanish", "puerto rican": "Caribbean", "cuban": "Caribbean",
    "scottish": "British", "welsh": "British", "english": "British", "irish": "British",
}

# Whole words with optional plurals, so "hamburger buns" isn't ham and "eggplant" isn't egg.
_PORK = re.compile(r"\b(pork|ham|bacon|salami|prosciutto|pepperoni|chorizo|lard|pancetta|sausage|hot dog|gelatin)(s|es)?\b")
_MEAT = re.compile(r"\b(beef|steak|chicken|turkey|lamb|mutton|goat|duck|veal|venison|meat|meatball|ground round|"
                   r"liver|broth|bouillon|stock|anchovy|anchovies|worcestershire|pork|ham|bacon|salami|sausage|"
                   r"pepperoni|chorizo|lard)(s|es)?\b|\bground (beef|chuck)\b|\bhamburger(s)?\b(?! bun)")
_FISH = re.compile(r"\b(fish|salmon|tuna|cod|sardine|mackerel|trout|shrimp|prawn|crab|lobster|mussel|clam|oyster|squid|"
                   r"scallop|tilapia|haddock|halibut|catfish|snapper)(s|es)?\b")
_DAIRY_EGG = re.compile(r"\b(cheese|milk|cream|butter|yogurt|ghee|paneer|egg|honey|whey|mayonnaise|ice cream|buttermilk)"
                        r"(s|es)?\b")
_VEG_STOCK = re.compile(r"\b(vegetable (broth|stock|bouillon)|veggie (broth|stock))")
_PLANT = re.compile(r"\b(almond|soy|oat|rice|coconut) (milk|cream)|\b(peanut|almond|cashew) butter")


# Food.com has no Italian/French tags (they're inside "European"), so recognise those dishes by name.
DISH_CUISINES = [
    ("Italian", re.compile(r"\b(italian|lasagn[ae]|risotto|carbonara|bolognese|parmigiana|parmesan chicken|pesto|gnocchi|"
                           r"bruschetta|minestrone|tiramisu|focaccia|marinara|alfredo|ravioli|tortellini|cacciatore|"
                           r"piccata|osso buco|polenta|panna cotta|caprese|calzone|frittata|penne|linguine|fettuccine|"
                           r"spaghetti|ziti|manicotti|cannoli|biscotti|panzanella|arancini|saltimbocca|marsala|tuscan|"
                           r"sicilian|neapolitan|roman|milanese|florentine|pizza)\b")),
    ("French", re.compile(r"\b(french|quiche|cr[eê]pes?|ratatouille|bourguignon|coq au vin|croissants?|souffl[eé]|"
                          r"gratin|bouillabaisse|cassoulet|ni[cç]oise|tarte|brioche|proven[cç]al|beurre|vichyssoise|"
                          r"clafoutis|madeleines?|b[eé]chamel|parisian|normandy|lyonnaise|dauphinoise|confit)\b")),
    ("Mediterranean", re.compile(r"\b(mediterranean)\b")),
    ("Bengali", re.compile(r"\b(bengali|bengal|kolkata|calcutta)\b")),
]


def cuisine_of(category: str, keywords: list[str], name: str = "") -> str | None:
    """Specific cuisines ("Indian") win over broad tags ("Asian"); dish names fill in Italian, French and others."""
    tags = [t.lower() for t in [category, *keywords]]
    exact = {c.lower(): c for c in CUISINES}
    found = next((exact[t] for t in tags if t in exact), None) or \
        next((CUISINE_ALIASES[t] for t in tags if t in CUISINE_ALIASES), None)
    if found:
        return found
    lowered = name.lower()
    return next((c for c, pattern in DISH_CUISINES if pattern.search(lowered)), None)


def r_list(value: str) -> list[str]:
    """Parse R's c("a", "b") / "a" / NA / character(0) list syntax used in the CSV export."""
    value = (value or "").strip()
    if not value or value in ("NA", "character(0)"):
        return []
    if value.startswith("c(") and value.endswith(")"):
        # Keep NA entries as "" so quantities stay aligned with their ingredients.
        return [(m.group(1) or "").replace('\\"', '"')
                for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|\bNA\b', value[2:-1])]
    return [value.strip('"')]


def minutes(iso: str) -> int | None:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", (iso or "").strip())
    if not m or not any(m.groups()):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def number(value: str) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if v != v else v  # NaN


def animal_level(ingredients: str) -> int:
    """0 vegan, 1 vegetarian (dairy/egg), 2 pescatarian, 3 meat, 4 pork."""
    text = _PLANT.sub(" ", _VEG_STOCK.sub(" ", ingredients))
    if _PORK.search(text):
        return 4
    if _MEAT.search(text):
        return 3
    if _FISH.search(text):
        return 2
    if _DAIRY_EGG.search(text):
        return 1
    return 0


def open_recipes(path: str):
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.endswith("recipes.csv"))
        return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", newline=""))
    return csv.DictReader(open(path, encoding="utf-8", newline=""))


SCHEMA = """
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, category TEXT, keywords TEXT, cuisine TEXT,
    ingredients TEXT NOT NULL, steps TEXT NOT NULL, image TEXT, rating REAL, reviews INTEGER,
    prep_min INTEGER, cook_min INTEGER, total_min INTEGER, servings REAL,
    calories REAL, fat_g REAL, saturated_fat_g REAL, sodium_mg REAL, carbs_g REAL, fiber_g REAL, sugar_g REAL, protein_g REAL,
    allergens TEXT NOT NULL, animal INTEGER NOT NULL
);
CREATE INDEX recipes_animal ON recipes(animal);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def main(src: str, out_path: str) -> None:
    out = Path(out_path)
    tmp = out.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
    batch, n, kept = [], 0, 0
    for r in open_recipes(src):
        n += 1
        quantities = r_list(r.get("RecipeIngredientQuantities", ""))
        parts = r_list(r.get("RecipeIngredientParts", ""))
        steps = r_list(r.get("RecipeInstructions", ""))
        calories = number(r.get("Calories"))
        if not parts or not steps or calories is None:
            continue
        ingredients = [f"{q} {p}".strip() if q and q != "NA" else p for q, p in zip(quantities + [""] * len(parts), parts)]
        keywords = r_list(r.get("Keywords", ""))
        category = (r.get("RecipeCategory") or "").strip()
        cuisine = cuisine_of(category, keywords, r["Name"])
        images = r_list(r.get("Images", ""))
        parts_text = " ".join(parts).lower()
        batch.append((
            int(float(r["RecipeId"])), r["Name"].strip(), (r.get("Description") or "").strip()[:600], category,
            ", ".join(keywords), cuisine, json.dumps(ingredients), json.dumps(steps), images[0] if images else None,
            number(r.get("AggregatedRating")), int(number(r.get("ReviewCount")) or 0),
            minutes(r.get("PrepTime")), minutes(r.get("CookTime")), minutes(r.get("TotalTime")),
            number(r.get("RecipeServings")),
            calories, number(r.get("FatContent")), number(r.get("SaturatedFatContent")), number(r.get("SodiumContent")),
            number(r.get("CarbohydrateContent")), number(r.get("FiberContent")), number(r.get("SugarContent")),
            number(r.get("ProteinContent")),
            ",".join(detect_allergens(r["Name"], parts_text)), animal_level(parts_text),
        ))
        if len(batch) >= 10_000:
            db.executemany(f"INSERT OR IGNORE INTO recipes VALUES ({','.join('?' * 25)})", batch)
            kept += len(batch)
            batch.clear()
            print(f"[{time.strftime('%H:%M:%S')}] {n:,} read, {kept:,} kept", flush=True)
    db.executemany(f"INSERT OR IGNORE INTO recipes VALUES ({','.join('?' * 25)})", batch)
    kept += len(batch)

    print("Building the search index…", flush=True)
    db.executescript("""
        CREATE VIRTUAL TABLE recipes_fts USING fts5(
            name, keywords, category, ingredients, content='recipes', content_rowid='id', tokenize='porter unicode61'
        );
        INSERT INTO recipes_fts(rowid, name, keywords, category, ingredients)
            SELECT id, name, keywords || ' ' || coalesce(cuisine, ''), category, ingredients FROM recipes;
        INSERT INTO recipes_fts(recipes_fts) VALUES ('optimize');
    """)
    db.execute("INSERT INTO meta VALUES ('source', ?)", (Path(src).name,))
    db.execute("INSERT INTO meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M"),))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    print(f"Done: {kept:,} recipes in {out} ({out.stat().st_size / 1e6:,.0f} MB)", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/build_recipe_db.py <archive.zip | recipes.csv> [out.db]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).resolve().parent.parent / "data" / "recipes.db"))
