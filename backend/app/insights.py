"""Deterministic meal insights computed from retrieved USDA data: allergens, diet checks, score, summary, swaps.

No AI is involved here, so these are instant and consistent from one scan to the next.
"""

from __future__ import annotations

import re

from .knowledge import DIETS

# ---------------------------------------------------------------------------
# Allergens (only ever adds; matched on food names, USDA descriptions and product ingredients)
# ---------------------------------------------------------------------------

ALLERGEN_KEYWORDS = {
    "gluten": ["bread", "baguette", "toast", "pasta", "noodle", "wheat", "flour", "naan", "pizza", "bun", "cracker",
               "croissant", "cake", "cheesecake", "cookie", "biscuit", "couscous", "seitan", "barley", "rye", "pastry",
               "chapati", "roti", "paratha", "bagel", "muffin", "pancake", "waffle", "dumpling", "breaded", "spaghetti",
               "macaroni", "lasagna", "tortilla, flour", "pita", "crouton", "semolina", "bulgur", "malt", "soy sauce"],
    "dairy": ["cheese", "milk", "cream", "butter", "yogurt", "yoghurt", "ghee", "paneer", "mozzarella", "parmesan",
              "brie", "feta", "ricotta", "cheddar", "gouda", "camembert", "ice cream", "latte", "whey", "casein",
              "custard", "raita", "lassi", "kheer"],
    "eggs": ["egg", "omelet", "omelette", "mayo", "mayonnaise", "aioli", "meringue", "custard", "frittata", "quiche"],
    "fish": ["salmon", "tuna", "cod", "sardine", "anchovy", "anchovies", "mackerel", "trout", "fish", "haddock",
             "tilapia", "pollock", "halibut", "herring", "hilsa", "catfish", "fish sauce"],
    "crustaceans": ["shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish"],
    "molluscs": ["mussel", "clam", "oyster", "squid", "octopus", "scallop", "calamari", "snail", "escargot"],
    "peanuts": ["peanut", "satay", "groundnut"],
    "tree_nuts": ["almond", "walnut", "cashew", "pistachio", "hazelnut", "pecan", "macadamia", "pesto", "praline",
                  "brazil nut", "pine nut", "marzipan", "nutella"],
    "soy": ["tofu", "soy", "soya", "edamame", "tempeh", "miso", "soybean"],
    "sesame": ["sesame", "tahini", "hummus", "halva"],
    "mustard": ["mustard"],
    "celery": ["celery", "celeriac"],
    "sulphites": ["wine", "vinegar, balsamic", "balsamic", "dried apricot"],
    "lupin": ["lupin", "lupine"],
}
_ALLERGEN_PATTERNS = {
    a: re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")(s|es)?\b")
    for a, words in ALLERGEN_KEYWORDS.items()
}
_NUT_BUTTERS = re.compile(r"\b(peanut|almond|cashew|nut|seed|apple|sunflower|cocoa|shea) butter")
# Phrases that contain an allergen word but not the allergen.
_NOT_ALLERGENS = re.compile(r"\b(cream of tartar|coconut milk|coconut cream|almond milk|oat milk|soy milk|rice milk|"
                            r"egg ?plant|butternut|buttermilk biscuit mix)\b")


def detect_allergens(*texts: str | None) -> list[str]:
    text = " ".join(t for t in texts if t).lower()
    text = _NUT_BUTTERS.sub(r"\1 spread", text)
    plant_milks = re.findall(r"\b(almond|soy|oat|rice|coconut) (milk|cream)\b", text)
    text = _NOT_ALLERGENS.sub(" ", text)
    found = {a for a, p in _ALLERGEN_PATTERNS.items() if p.search(text)}
    for source, _ in plant_milks:  # "almond milk" is a tree nut, not dairy
        found |= {"almond": {"tree_nuts"}, "soy": {"soy"}}.get(source, set())
    return sorted(found)


HIDDEN_RULES = [
    (r"\b(curry|korma|masala|tikka|biryani|makhani)\b", "Curries and gravies are often thickened with cashew or almond paste (tree nuts) and cream (dairy)."),
    (r"\b(sauce|dressing|marinade|gravy)\b", "Sauces and dressings can contain mustard, soy, sesame or dairy that you can't see."),
    (r"\b(salami|sausage|chorizo|pepperoni|hot dog|frankfurter|deli|luncheon)\b", "Processed meats can contain mustard, celery or milk powder in their seasoning, and are high in sodium."),
    (r"\b(bread|baguette|bun|roll|naan|bagel)\b", "Breads may be glazed with egg or topped with sesame seeds."),
    (r"\b(cake|cookie|pastry|brownie|muffin|dessert|pie)\b", "Baked desserts usually contain eggs and dairy, and may contain nuts."),
    (r"\b(fried|fries|tempura|pakora|fritter)\b", "Fried foods may be cooked in shared oil with fish or shellfish."),
    (r"\b(pesto|salad)\b", "Salads and pesto can contain pine nuts, other tree nuts or cheese."),
    (r"\b(thai|pad|satay|stir.?fry)\b", "Asian-style dishes often use fish sauce, shrimp paste, peanuts or soy."),
]


def hidden_warnings(texts: list[str], found: set[str]) -> list[str]:
    joined = " ".join(texts).lower()
    out = []
    for pattern, message in HIDDEN_RULES:
        if re.search(pattern, joined) and message not in out:
            out.append(message)
    return out[:3]


# ---------------------------------------------------------------------------
# Diet compatibility
# ---------------------------------------------------------------------------

_PORK = r"\b(pork|ham|bacon|salami|prosciutto|pepperoni|chorizo|lard|pancetta|sausage|hot dog|gelatin)\b"
_MEAT = r"\b(beef|steak|chicken|turkey|lamb|mutton|goat|duck|veal|venison|meat|meatball|burger|jerky|liver|" \
        r"broth, beef|broth, chicken|" + _PORK[3:-3] + r")\b"
_FISH = r"\b(fish|salmon|tuna|cod|sardine|anchov|mackerel|trout|shrimp|prawn|crab|lobster|mussel|clam|oyster|squid|" \
        r"octopus|scallop|calamari|hilsa|tilapia|haddock|herring)"
_ANIMAL_DAIRY_EGG = r"\b(cheese|milk|cream|butter|yogurt|ghee|paneer|egg|honey|whey|mayonnaise|ice cream)"


def diet_checks(diets: list[str], texts: list[str], totals: dict) -> list[dict]:
    text = " ".join(texts).lower()
    text = _NUT_BUTTERS.sub(r"\1 spread", text)
    text = re.sub(r"\b(almond|soy|oat|rice|coconut) (milk|cream)\b", "plant drink", text)
    has_pork = bool(re.search(_PORK, text))
    has_meat = bool(re.search(_MEAT, text))
    has_fish = bool(re.search(_FISH, text))
    has_animal = bool(re.search(_ANIMAL_DAIRY_EGG, text))
    allergens = set(detect_allergens(text))
    checks = []
    for d in diets:
        ok, reason = True, "Fits this diet."
        if d == "vegan" and (has_meat or has_fish or has_animal):
            ok, reason = False, "Contains animal products."
        elif d == "vegetarian" and (has_meat or has_fish):
            ok, reason = False, "Contains meat or fish."
        elif d == "pescatarian" and has_meat:
            ok, reason = False, "Contains meat."
        elif d in ("halal", "kosher") and has_pork:
            ok, reason = False, "Contains pork."
        elif d == "kosher" and allergens & {"crustaceans", "molluscs"}:
            ok, reason = False, "Contains shellfish."
        elif d == "gluten_free" and "gluten" in allergens:
            ok, reason = False, "Contains gluten."
        elif d == "dairy_free" and "dairy" in allergens:
            ok, reason = False, "Contains dairy."
        elif d == "keto" and totals["carbs_g"] > 20:
            ok, reason = False, f"{totals['carbs_g']:.0f} g of carbs is too many for one keto meal."
        elif d == "low_sodium" and totals["sodium_mg"] > 600:
            ok, reason = False, f"{totals['sodium_mg']:.0f} mg sodium is high for a low-sodium diet."
        elif d == "diabetic_friendly" and (totals["sugar_g"] > 15 or totals["carbs_g"] > 75):
            ok, reason = False, "High in sugar or fast carbs; pair with protein and fiber, or reduce the portion."
        elif d == "paleo" and ("gluten" in allergens or "dairy" in allergens):
            ok, reason = False, "Contains grains or dairy."
        if d in ("halal", "kosher") and ok and has_meat:
            reason = "No pork found, but check how the meat was prepared."
        checks.append({"diet": DIETS[d], "compatible": ok, "reason": reason})
    return checks


# ---------------------------------------------------------------------------
# Score, summary and swaps
# ---------------------------------------------------------------------------

_VEG_FRUIT = r"\b(apple|banana|orange|tangerine|berry|berries|grape|melon|mango|pear|peach|plum|kiwi|tomato|" \
             r"lettuce|spinach|kale|salad|broccoli|carrot|pepper|cucumber|onion|cabbage|bean|lentil|chickpea|pea|" \
             r"vegetable|fruit|greens|zucchini|eggplant|cauliflower|avocado|mushroom|squash|pumpkin|olive)"
_PROCESSED = r"\b(salami|ham|bacon|sausage|pepperoni|chorizo|prosciutto|hot dog|deli|luncheon)\b"
_REFINED = r"\b(white bread|french bread|baguette|bagel|croissant|naan|white rice|pasta|cracker|bread, white)\b"
_SWEET = r"\b(cake|cookie|candy|chocolate|soda|syrup|honey|ice cream|pastry|donut|doughnut|sweet)\b"


def score_meal(totals: dict, texts: list[str], meal_share_kcal: float) -> int:
    text = " ".join(texts).lower()
    score = 6.0
    if totals["fiber_g"] >= 8:
        score += 1.5
    elif totals["fiber_g"] >= 4:
        score += 0.5
    elif totals["fiber_g"] < 2:
        score -= 1
    if totals["protein_g"] >= 20:
        score += 1
    if re.search(_VEG_FRUIT, text):
        score += 1
    if totals["sodium_mg"] > 1500:
        score -= 2
    elif totals["sodium_mg"] > 900:
        score -= 1
    if totals["sugar_g"] > 25:
        score -= 1.5
    elif totals["sugar_g"] > 12:
        score -= 0.5
    if totals["calories"] > 1.5 * meal_share_kcal:
        score -= 1
    if re.search(_PROCESSED, text):
        score -= 1
    return int(min(10, max(1, round(score))))


def summarize(totals: dict, rows: list[dict], texts: list[str]) -> str:
    text = " ".join(texts).lower()
    good = [r["label"].lower() for r in rows if r["kind"] == "target" and r["status"] == "good"
            and r["key"] not in ("calories", "carbs_g", "fat_g")]
    low = [r["label"].lower() for r in rows if r["kind"] == "target" and r["status"] == "low"
           and r["key"] in ("fiber_g", "protein_g", "iron_mg", "calcium_mg", "vitamin_c_mg", "vitamin_d_mcg")]
    high = [r["label"].lower() for r in rows if r["kind"] == "limit" and r["status"] == "high"]
    first = f"About {totals['calories']:.0f} kcal with {totals['protein_g']:.0f} g protein"
    first += f", and a good source of {', '.join(good[:3])}." if good else "."
    parts = []
    if high:
        parts.append(f"it's high in {' and '.join(high)}")
    if low:
        parts.append(f"light on {', '.join(low[:3])}")
    second = "A well-balanced plate." if not parts else "Watch out: " + "; ".join(parts) + "."
    if re.search(_PROCESSED, text) and "sodium" in " ".join(high):
        second += " Most of the salt comes from the cured meats."
    return f"{first} {second}"


_FRIED = r"\b(vada|wada|pakora|pakoda|bhaji|bajji|samosa|kachori|bonda|puri|poori|bhatura|fries|fried|fritter|" \
         r"tempura|nugget|katsu|schnitzel|chips|crisps|churro|jalebi|spring roll)"
_BREAD = r"\b(pav|bun|roll|bread|baguette|bagel|naan|kulcha|toast|croissant|sandwich|burger|pita|tortilla|wrap)"


def _amount(item, nutrient: str) -> float:
    return item.estimated_grams * getattr(item.per_100g, nutrient) / 100


def _top(items, nutrient: str):
    best = max(items, key=lambda i: _amount(i, nutrient), default=None)
    return (best, _amount(best, nutrient)) if best else (None, 0.0)


def swaps(totals: dict, texts: list[str], diets: list[str], items: list | None = None, cuisine: str = "") -> list[str]:
    """Suggestions written for this meal: they name the food behind each problem, most impactful first."""
    text = " ".join(texts).lower()
    items = [i for i in (items or []) if i.estimated_grams > 0]
    veg_ok = "vegan" in diets or "vegetarian" in diets
    indian = cuisine.lower() in ("indian", "bengali")
    out: list[tuple[float, str]] = []  # (impact, suggestion)

    for i in items:
        name = i.name.strip()
        if re.search(_FRIED, name.lower()) and _amount(i, "fat_g") >= 4:
            out.append((_amount(i, "fat_g") * 2, f"The {name.lower()} is deep-fried. An air-fried or baked version keeps "
                                                 f"the taste with far less oil (about {round(_amount(i, 'fat_g'))} g of fat here)."))
            break

    meat = [i for i in items if re.search(_PROCESSED, i.name.lower())]
    if meat or re.search(_PROCESSED, text):
        what = meat[0].name.lower() if meat else "cured meat"
        out.append((25, f"Swap half the {what} for beans, hummus or roast vegetables to cut the salt." if veg_ok
                    else f"Swap some of the {what} for roast chicken or smoked salmon to cut the salt."))

    breads = [i for i in items if re.search(_BREAD, i.name.lower())]
    if breads:
        b = max(breads, key=lambda i: i.estimated_grams)
        better = "a wholewheat pav or a multigrain bun" if indian else "a wholegrain or sourdough version"
        out.append((15, f"Choose {better} instead of the {b.name.lower()} for more fiber and steadier energy."))
    elif re.search(_REFINED, text):
        out.append((12, "Choose wholegrain or brown versions of the bread, rice or pasta for more fiber."))

    if totals["sodium_mg"] > 900:
        top, mg = _top(items, "sodium_mg")
        if top is not None and mg > 300:
            out.append((totals["sodium_mg"] / 60, f"Most of the salt ({round(mg)} mg) comes from the {top.name.lower()}: "
                                                  + ("go easy on it, or skip salty chutneys and pickles." if indian else "go easy on it, or skip salty sauces.")))

    if totals["sugar_g"] > 20:
        top, g = _top(items, "sugar_g")
        if top is not None and g > 8:
            if re.search(_SWEET, top.name.lower()):
                out.append((g, f"Most of the sugar ({round(g)} g) comes from the {top.name.lower()}: "
                               "have a smaller portion, or swap it for fresh fruit."))
            else:
                out.append((g / 2, f"The {top.name.lower()} adds about {round(g)} g of sugar; an unsweetened version cuts it."))

    if totals["fiber_g"] < 4:
        side = "kachumber salad, sprouts or a bowl of dal" if indian else "a side salad or a handful of vegetables"
        out.append((10, f"Add {side} for fiber; this meal has only {round(totals['fiber_g'], 1)} g."
                    if not re.search(_VEG_FRUIT, text) else
                    f"Add beans, chickpeas or wholegrains: even with the vegetables, this meal has only "
                    f"{round(totals['fiber_g'], 1)} g of fiber."))

    if totals["protein_g"] < 12:
        extra = "dal, paneer, curd or sprouts" if indian else (
            "lentils, tofu, paneer, yogurt or eggs" if veg_ok else "eggs, yogurt, lentils, tofu or lean meat")
        out.append((9, f"Add a protein such as {extra}."))

    out.sort(key=lambda pair: -pair[0])
    return [text for _, text in out[:3]]
