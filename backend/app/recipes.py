"""Recipe retrieval over the Food.com dataset (data/recipes.db, built by scripts/build_recipe_db.py).

Recipes and meal plans are picked from ~500k real, rated recipes instead of being written by an AI:
filters enforce the user's diet and allergens, full-text search matches cuisine, meal and ingredients,
and nutrient goals (e.g. "rich in iron") boost recipes built on foods that are good sources.
"""

from __future__ import annotations

import html
import json
import math
import re
import sqlite3
import threading

from .config import BACKEND_DIR
from .knowledge import GUIDES, NUTRIENTS
from .schemas import MealPlan, MealPlanRequest, PlanDay, PlannedMeal, Profile, Recipe, RecipeList, RecipeRequest, ServingNutrition

DB_PATH = BACKEND_DIR / "data" / "recipes.db"
_local = threading.local()

# Max animal level allowed per diet: 0 vegan, 1 vegetarian, 2 pescatarian, 3 meat, 4 pork.
DIET_ANIMAL = {"vegan": 0, "vegetarian": 1, "pescatarian": 2, "halal": 3, "kosher": 3}
MEAL_TERMS = {
    "breakfast": "breakfast OR brunch OR oatmeal OR pancake OR omelet OR smoothie",
    "lunch": "lunch OR salad OR sandwich OR soup OR wrap",
    "dinner": "\"one dish meal\" OR curry OR stew OR chicken OR beef OR pasta OR vegetable OR lentil OR rice",
    "snack": "snack OR \"lunch/snacks\" OR dip OR bar OR \"spreads\"",
    "dessert": "dessert OR cake OR cookie OR pie OR pudding",
}
# Extra nutrient-dense ingredient words beyond the nutrient guides' food lists.
NUTRIENT_TERMS = {
    "iron_mg": ["spinach", "lentil", "chickpea", "kidney bean", "black bean", "tofu", "beef", "liver", "quinoa",
                "pumpkin seed", "kale", "molasses", "chard"],
    "calcium_mg": ["yogurt", "cheese", "milk", "tofu", "sardine", "kale", "broccoli", "almond", "ricotta", "paneer"],
    "vitamin_c_mg": ["bell pepper", "red pepper", "broccoli", "orange", "lemon", "lime", "strawberr", "kiwi", "tomato",
                     "mango", "cauliflower"],
    "vitamin_d_mcg": ["salmon", "sardine", "tuna", "mackerel", "mushroom", "egg"],
    "vitamin_b12_mcg": ["salmon", "tuna", "beef", "egg", "yogurt", "clam", "sardine", "nutritional yeast"],
    "fiber_g": ["lentil", "bean", "chickpea", "oat", "barley", "quinoa", "whole wheat", "broccoli", "pear", "raspberr"],
    "protein_g": ["chicken", "egg", "tofu", "lentil", "greek yogurt", "tuna", "salmon", "beef", "paneer", "tempeh"],
    "potassium_mg": ["potato", "sweet potato", "banana", "white bean", "spinach", "avocado", "tomato"],
    "magnesium_mg": ["pumpkin seed", "almond", "spinach", "cashew", "black bean", "dark chocolate", "brown rice"],
    "zinc_mg": ["beef", "chickpea", "pumpkin seed", "cashew", "oyster", "crab", "oat"],
    "folate_mcg": ["lentil", "chickpea", "spinach", "asparagus", "avocado", "broccoli", "edamame"],
}
# Nutrients Food.com reports per serving can be ranked on directly.
NUTRIENT_COLUMNS = {"protein_g": "protein_g", "fiber_g": "fiber_g"}


def available() -> bool:
    return DB_PATH.exists()


def _db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def stats() -> dict:
    if not available():
        return {"available": False}
    db = _db()
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    return {"available": True, "recipes": db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0], **meta}


def _quote(term: str) -> str:
    return '"' + re.sub(r'[^a-z0-9 /]', " ", term.lower()).strip() + '"'


def _profile_filters(profile: Profile) -> tuple[str, list]:
    clauses, args = [], []
    levels = [DIET_ANIMAL[d] for d in profile.diets if d in DIET_ANIMAL]
    if levels:
        clauses.append("r.animal <= ?")
        args.append(min(levels))
    if "halal" in profile.diets or "kosher" in profile.diets:
        clauses.append("r.animal != 4")
    avoid = set(profile.allergens)
    if "gluten_free" in profile.diets:
        avoid.add("gluten")
    if "dairy_free" in profile.diets:
        avoid.add("dairy")
    for a in sorted(avoid):
        clauses.append("(',' || r.allergens || ',') NOT LIKE ?")
        args.append(f"%,{a},%")
    if "keto" in profile.diets:
        clauses.append("r.carbs_g <= 15")
    if "low_sodium" in profile.diets:
        clauses.append("r.sodium_mg <= 600")
    if "diabetic_friendly" in profile.diets:
        clauses.append("r.sugar_g <= 12")
    return " AND ".join(clauses), args


def _candidates(match: str | None, profile: Profile, extra_where: str = "", extra_args: list | None = None,
                limit: int = 600) -> list[sqlite3.Row]:
    where, args = _profile_filters(profile)
    conditions = [c for c in (where, extra_where, "r.calories > 0") if c]
    if match:
        sql = f"""SELECT r.*, bm25(recipes_fts, 6.0, 2.0, 2.0, 1.0) AS rank
                  FROM recipes_fts JOIN recipes r ON r.id = recipes_fts.rowid
                  WHERE recipes_fts MATCH ? AND {' AND '.join(conditions)} ORDER BY rank LIMIT ?"""
        return _db().execute(sql, [match, *args, *(extra_args or []), limit]).fetchall()
    sql = f"""SELECT r.*, 0.0 AS rank FROM recipes r WHERE {' AND '.join(conditions)}
              ORDER BY r.reviews DESC LIMIT ?"""
    return _db().execute(sql, [*args, *(extra_args or []), limit]).fetchall()


def _nutrient_hits(row: sqlite3.Row, nutrient: str | None) -> list[str]:
    if not nutrient:
        return []
    text = row["ingredients"].lower()
    terms = NUTRIENT_TERMS.get(nutrient, [])
    guide = GUIDES.get(nutrient)
    if guide:
        terms = terms + [s.name.split(",")[0].split("(")[0].strip().lower() for s in guide.sources]
    return sorted({t for t in terms if len(t) > 2 and t in text})


def _score(row: sqlite3.Row, nutrient: str | None, ingredients: list[str]) -> float:
    rating = row["rating"] or 3.5
    popularity = math.log1p(row["reviews"] or 0)
    score = -row["rank"] + 1.5 * rating + 0.8 * popularity
    hits = _nutrient_hits(row, nutrient)
    score += 3.0 * len(hits)
    if nutrient in NUTRIENT_COLUMNS and row[NUTRIENT_COLUMNS[nutrient]]:
        score += 0.15 * row[NUTRIENT_COLUMNS[nutrient]]
    if ingredients:
        text = row["ingredients"].lower()
        score += 2.0 * sum(1 for i in ingredients if i.lower() in text)
    if row["image"]:
        score += 1.0
    return score


# Pantry basics that don't describe a dish ("a salad of tuna, feta and cucumber", not "of salt and oil").
STAPLES = {
    "salt", "pepper", "black pepper", "fresh ground pepper", "fresh ground black pepper", "water", "boiling water",
    "oil", "olive oil", "vegetable oil", "canola oil", "cooking spray", "sugar", "granulated sugar", "butter",
    "margarine", "flour", "all-purpose flour", "baking powder", "baking soda", "ice", "garlic", "garlic cloves",
    "garlic clove", "paprika", "cumin", "chili powder", "dried oregano", "oregano", "fresh oregano", "parsley",
    "fresh parsley", "vanilla", "vanilla extract", "cinnamon", "nutmeg", "lemon juice", "lime juice", "kosher salt",
    "sea salt", "salt & pepper", "salt and pepper", "pepper, to taste", "nonstick cooking spray",
}


def _parts(row: sqlite3.Row) -> list[str]:
    """Ingredient names without their leading amounts."""
    return [re.sub(r"^[\d\s/.,-]+", "", html.unescape(i)).strip() for i in json.loads(row["ingredients"])]


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _summary(row: sqlite3.Row, hits: list[str]) -> str:
    """A short, factual description built from the recipe's own data (the source's text is often a personal comment)."""
    key = [p for p in dict.fromkeys(_parts(row)) if p and p.lower() not in STAPLES][:4]
    style = f"A {row['cuisine']} recipe" if row["cuisine"] else "A home-style recipe"
    sentences = [f"{style} made with {_join(key)}." if key else f"{style}."]
    time_bits = []
    if row["total_min"]:
        t = row["total_min"]
        time_bits.append(f"ready in {t} minutes" if t < 120 else f"ready in about {round(t / 60)} hours")
    if row["servings"]:
        n = int(row["servings"])
        time_bits.append(f"serves {n}")
    if time_bits:
        sentences.append(" and ".join(time_bits).capitalize() + ".")
    facts = []
    if (row["protein_g"] or 0) >= 20:
        facts.append(f"high in protein ({row['protein_g']:.0f} g)")
    if (row["fiber_g"] or 0) >= 6:
        facts.append(f"rich in fiber ({row['fiber_g']:.0f} g)")
    if (row["carbs_g"] or 99) <= 10:
        facts.append("low in carbs")
    if (row["sodium_mg"] or 0) >= 1200:
        facts.append("salty")
    if facts:
        sentences.append(f"Per serving it's {_join(facts)}, at {row['calories']:.0f} kcal.")
    if hits:
        sentences.append(f"Good sources here: {', '.join(hits[:4])}.")
    return " ".join(sentences)


# Ingredients that often carry an allergen that isn't in their name (cross-contact or hidden in the product).
MAY_CONTAIN_RULES = [
    (r"\b(chocolate|cocoa|chocolate chips?|candy|candies|candy bars?)\b", ["tree_nuts", "peanuts", "dairy", "soy"]),
    (r"\b(granola|muesli|trail mix|cereal)\b", ["tree_nuts", "peanuts", "gluten"]),
    (r"\b(cake mix|brownie mix|cookie mix|biscuit mix|pancake mix|bisquick|muffin mix)\b", ["eggs", "dairy", "soy", "tree_nuts"]),
    (r"\bice cream\b", ["tree_nuts", "peanuts", "eggs"]),
    (r"\b(curry paste|red curry|green curry)\b", ["crustaceans", "fish"]),
    (r"\b(bouillon|stock cubes?|broth|stock)\b", ["celery", "gluten"]),
    (r"\b(sausages?|hot dogs?|salami|bologna|deli|luncheon)\b", ["mustard", "celery", "dairy"]),
    (r"\b(bread|buns?|rolls?|bagels?|hamburger buns?)\b", ["sesame", "eggs"]),
    (r"\b(seasoning|spice mix|taco seasoning|cajun seasoning)\b", ["celery", "mustard"]),
    (r"\b(margarine)\b", ["dairy", "soy"]),
    (r"\b(caramel|toffee|nougat)\b", ["dairy", "tree_nuts"]),
    (r"\b(raisins|dried apricots?|dried fruit)\b", ["sulphites"]),
    (r"\b(oats|oatmeal|rolled oats)\b", ["gluten"]),
]
_MAY_CONTAIN = [(re.compile(p), allergens) for p, allergens in MAY_CONTAIN_RULES]


def _may_contain(row: sqlite3.Row) -> list[str]:
    text = " ".join([row["name"] or "", *_parts(row)]).lower()
    contains = set((row["allergens"] or "").split(","))
    found = {a for pattern, allergens in _MAY_CONTAIN if pattern.search(text) for a in allergens}
    return sorted(found - contains)


def _safe_for(rows: list[sqlite3.Row], avoid: set[str]) -> list[sqlite3.Row]:
    """Drop recipes that may contain an allergen the user avoids (the SQL filter already removed definite ones)."""
    return [r for r in rows if not avoid & set(_may_contain(r))] if avoid else rows


def _with_avoid(profile: Profile, avoid: list[str] | None) -> Profile:
    return profile if avoid is None else profile.model_copy(update={"allergens": list(avoid)})


def _to_recipe(row: sqlite3.Row, nutrient: str | None) -> Recipe:
    hits = _nutrient_hits(row, nutrient)
    highlight = []
    if nutrient and hits:
        highlight.append(NUTRIENTS[nutrient]["label"])
    if (row["protein_g"] or 0) >= 20:
        highlight.append("Protein")
    if (row["fiber_g"] or 0) >= 6:
        highlight.append("Fiber")
    tags = []
    animal = row["animal"]
    if animal == 0:
        tags.append("vegan")
    elif animal == 1:
        tags.append("vegetarian")
    allergens = [a for a in (row["allergens"] or "").split(",") if a]
    if "gluten" not in allergens:
        tags.append("gluten-free")
    if "dairy" not in allergens:
        tags.append("dairy-free")
    return Recipe(
        id=row["id"], name=html.unescape(row["name"]), cuisine=row["cuisine"] or "Home cooking", description=_summary(row, hits),
        prep_minutes=row["prep_min"] or 0, cook_minutes=row["cook_min"] or max(0, (row["total_min"] or 0) - (row["prep_min"] or 0)),
        servings=int(row["servings"] or 1), ingredients=[html.unescape(i) for i in json.loads(row["ingredients"])],
        steps=[html.unescape(st) for st in json.loads(row["steps"])],
        allergens=allergens, diet_tags=tags, highlight_nutrients=list(dict.fromkeys(highlight)),
        per_serving=ServingNutrition(
            calories=row["calories"] or 0, protein_g=row["protein_g"] or 0, carbs_g=row["carbs_g"] or 0,
            fat_g=row["fat_g"] or 0, fiber_g=row["fiber_g"] or 0, iron_mg=None, calcium_mg=None,
        ),
        image=row["image"], may_contain=_may_contain(row),
    )


def get(recipe_id: int) -> Recipe | None:
    if not available():
        return None
    row = _db().execute("SELECT r.*, 0.0 AS rank FROM recipes r WHERE r.id = ?", (recipe_id,)).fetchone()
    return _to_recipe(row, None) if row else None


def _cuisine_filter(cuisines: list[str]) -> tuple[str, list]:
    if not cuisines:
        return "", []
    return f"r.cuisine IN ({','.join('?' * len(cuisines))})", list(cuisines)


def _and(*parts: str) -> str:
    return " AND ".join(p for p in parts if p)


def search(req: RecipeRequest, profile: Profile) -> RecipeList:
    profile = _with_avoid(profile, req.avoid_allergens)
    avoid = set(profile.allergens)
    # A cuisine the user picks is a rule; their favourite cuisines are only a preference.
    cuisines = [req.cuisine] if req.cuisine else profile.cuisines
    cuisine_where, cuisine_args = _cuisine_filter(cuisines)
    meal = f"({MEAL_TERMS[req.meal_type]})" if req.meal_type in MEAL_TERMS else None
    boost = NUTRIENT_TERMS.get(req.focus_nutrient, []) if req.focus_nutrient else []
    boost = boost + req.ingredients_on_hand
    boost_match = "(" + " OR ".join(_quote(b) for b in boost) + ")" if boost else None
    time_where, time_args = ("r.total_min IS NOT NULL AND r.total_min <= ?", [req.max_minutes]) if req.max_minutes else ("", [])

    full = _and(meal or "", boost_match or "") or None
    attempts = [(full, True)]
    if meal and boost_match:
        attempts += [(boost_match, True), (meal, True)]
    attempts.append((None, True))  # any well-reviewed recipe of that cuisine
    if not req.cuisine and cuisines:
        attempts += [(full, False), (boost_match, False), (None, False)]

    rows = []
    for match, use_cuisine in attempts:
        where = _and(time_where, cuisine_where if use_cuisine else "")
        args = time_args + (cuisine_args if use_cuisine else [])
        rows = _safe_for(_candidates(match, profile, where, args), avoid)
        if len(rows) >= req.count:
            break

    rows = sorted(rows, key=lambda r: _score(r, req.focus_nutrient, req.ingredients_on_hand), reverse=True)
    picked, seen_names = [], set()
    for r in rows:
        key = re.sub(r"[^a-z]", "", r["name"].lower())
        if key in seen_names:
            continue
        seen_names.add(key)
        picked.append(_to_recipe(r, req.focus_nutrient))
        if len(picked) >= req.count:
            break
    return RecipeList(recipes=picked)


SLOT_SHARE = {"breakfast": 0.25, "lunch": 0.32, "dinner": 0.33, "snack": 0.10}
THEMES = ["Fresh start", "Comfort classics", "Bright & light", "Spice route", "Garden goodness", "Weekend treat", "Easy wins"]


def meal_plan(req: MealPlanRequest, profile: Profile) -> MealPlan:
    profile = _with_avoid(profile, req.avoid_allergens)
    avoid = set(profile.allergens)
    """Pick real recipes for each slot so each day lands near the calorie target, with variety across days."""
    target = profile.calorie_target
    focus = req.focus_nutrients[0] if req.focus_nutrients else None
    cuisines = req.cuisines or profile.cuisines
    pools: dict[str, list[sqlite3.Row]] = {}
    for slot, share in SLOT_SHARE.items():
        kcal = target * share
        meal = f"({MEAL_TERMS[slot]})"
        cw, ca = _cuisine_filter(cuisines if slot in ("lunch", "dinner") else [])
        # Strict first (favourite cuisine, right size, well reviewed), then looser so a day is never left empty.
        attempts = [
            (meal, _and(cw, "r.calories BETWEEN ? AND ? AND r.reviews >= 3"), ca + [kcal * 0.75, kcal * 1.3]),
            (meal, "r.calories BETWEEN ? AND ? AND r.reviews >= 3", [kcal * 0.75, kcal * 1.3]),
            (meal, "r.calories BETWEEN ? AND ?", [kcal * 0.5, kcal * 1.6]),
            (None, "r.calories BETWEEN ? AND ?", [kcal * 0.3, kcal * 2.0]),
        ]
        rows = []
        for match, where, args in attempts:
            rows = _safe_for(_candidates(match, profile, where, args, limit=800), avoid)
            if len(rows) >= req.days:
                break
        rows = sorted(rows, key=lambda r: _score(r, focus, []), reverse=True)
        pools[slot] = rows[: max(12, req.days * 3)]

    used: set[int] = set()
    days, shopping = [], {}
    for d in range(req.days):
        meals = []
        for slot in SLOT_SHARE:
            pool = [r for r in pools[slot] if r["id"] not in used] or pools[slot]
            if not pool:
                continue
            kcal = target * SLOT_SHARE[slot]
            shortlist = pool[: max(6, req.days * 2)]
            row = min(enumerate(shortlist), key=lambda ir: abs((ir[1]["calories"] or 0) - kcal) / kcal + 0.04 * ir[0])[1]
            used.add(row["id"])
            hits = _nutrient_hits(row, focus)
            meals.append(PlannedMeal(
                meal_type=slot, name=html.unescape(row["name"]), cuisine=row["cuisine"] or row["category"] or "Home cooking",
                description=(f"{row['total_min']} min" if row["total_min"] else "")
                            + (f" · good {NUTRIENTS[focus]['label'].lower()} sources: {', '.join(hits[:3])}" if hits else ""),
                recipe_id=row["id"],
                calories=round(row["calories"] or 0), protein_g=round(row["protein_g"] or 0, 1), iron_mg=None,
                allergens=[a for a in (row["allergens"] or "").split(",") if a],
            ))
            for ing in json.loads(row["ingredients"]):
                name = re.sub(r"^[\d\s/.,-]+", "", ing).strip().lower()
                if name:
                    shopping[name] = shopping.get(name, 0) + 1
        total = sum(m.calories for m in meals)
        tip = (f"About {total:.0f} kcal: close to your {target} kcal target."
               if abs(total - target) <= 0.15 * target else
               f"About {total:.0f} kcal; adjust portions to reach your {target} kcal target.")
        days.append(PlanDay(day=d + 1, theme=THEMES[d % len(THEMES)], meals=meals, total_calories=round(total),
                            total_protein_g=round(sum(m.protein_g for m in meals), 1), tip=tip))
    shopping_list = [k for k, _ in sorted(shopping.items(), key=lambda kv: (-kv[1], kv[0]))][:40]
    title = f"{req.days}-day plan" + (f" rich in {NUTRIENTS[focus]['label'].lower()}" if focus else "")
    return MealPlan(title=title, days=days, shopping_list=shopping_list,
                    notes="Every meal is a real recipe, filtered for your diet and allergens. Click a meal to see how to cook it.")
