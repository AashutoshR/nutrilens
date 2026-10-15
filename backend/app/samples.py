"""Built-in sample meals for trying NutriLens before Claude is connected.

These are only ever shown when the user explicitly picks "Try a sample meal": they are
never presented as the analysis of a photo the user uploaded.
"""

from __future__ import annotations

from .knowledge import DIETS, Dish, fits_profile
from .schemas import DetectedItem, DietCheck, Nutrients, Profile, VisionAnalysis

_FIELDS = list(Nutrients.model_fields)


def N(*values: float) -> Nutrients:
    return Nutrients(**dict(zip(_FIELDS, values)))


def _item(name, portion, grams, conf, ingredients, allergens, per100) -> DetectedItem:
    return DetectedItem(name=name, portion_description=portion, estimated_grams=grams, confidence=conf,
                        ingredients=ingredients, allergens=allergens, per_100g=per100)


#            kcal  prot carb  fat  fib  sug  Na    Fe   Ca   VitC VitD B12  K    Mg  Zn   Fol
SAMPLES = [
    dict(
        id="thali", emoji="🍛",
        dish_name="Butter Chicken Thali", cuisine="Indian", meal_type="dinner", animal="meat",
        items=[
            _item("Butter chicken", "1 bowl", 220, 0.9, ["chicken", "tomato", "butter", "cream", "garam masala"],
                  ["dairy"], N(150, 12, 5, 9.5, 0.8, 3, 380, 0.9, 40, 3, 0.2, 0.3, 250, 20, 1.1, 10)),
            _item("Basmati rice", "1 cup", 180, 0.95, ["basmati rice"], [],
                  N(121, 3.5, 25, 0.4, 0.4, 0.1, 1, 0.2, 3, 0, 0, 0, 35, 12, 0.6, 3)),
            _item("Garlic naan", "1 piece", 90, 0.85, ["wheat flour", "yogurt", "garlic", "butter"],
                  ["gluten", "dairy"], N(290, 9, 50, 6, 2, 3, 460, 2.9, 75, 0.5, 0, 0.1, 120, 22, 0.8, 80)),
            _item("Cucumber raita", "small bowl", 80, 0.8, ["yogurt", "cucumber", "cumin"], ["dairy"],
                  N(60, 3, 5, 3, 0.4, 4, 150, 0.1, 110, 2, 0.1, 0.4, 170, 12, 0.5, 8)),
        ],
        hidden=["Restaurant butter chicken gravy is often thickened with cashew paste (tree nuts)."],
        score=5,
        summary="A satisfying, protein-rich plate, but the creamy gravy and naan push up saturated fat and sodium. It's light on vegetables, fiber and iron.",
        swaps=["Swap naan for a whole-wheat roti to add fiber", "Add a side of palak (spinach) or kachumber salad",
               "Ask for less cream or choose chicken tikka masala made with yogurt"],
    ),
    dict(
        id="pizza", emoji="🍕",
        dish_name="Margherita Pizza with Side Salad", cuisine="Italian", meal_type="lunch", animal="dairy_egg",
        items=[
            _item("Margherita pizza", "2 slices", 220, 0.93, ["wheat dough", "tomato sauce", "mozzarella", "basil", "olive oil"],
                  ["gluten", "dairy"], N(250, 11, 30, 9.5, 1.8, 3.5, 560, 2.3, 190, 2, 0.1, 0.5, 170, 22, 1.3, 60)),
            _item("Mixed green salad with balsamic", "1 side bowl", 80, 0.75, ["mixed leaves", "cherry tomato", "balsamic vinegar", "olive oil"],
                  ["sulphites"], N(45, 1.2, 5, 2.5, 1.5, 3, 90, 0.9, 30, 15, 0, 0, 230, 12, 0.2, 60)),
        ],
        hidden=["Some pizza bases contain egg or soy flour improvers."],
        score=6,
        summary="Good calcium from the mozzarella and a decent side of greens. Sodium is high for one meal, and protein and fiber could be better.",
        swaps=["Choose a thin whole-wheat crust", "Add rocket and mushrooms as toppings", "Add a handful of chickpeas to the salad"],
    ),
    dict(
        id="poke", emoji="🥗",
        dish_name="Salmon Poke Bowl", cuisine="Japanese", meal_type="lunch", animal="fish",
        items=[
            _item("Raw salmon", "120 g cubes", 120, 0.9, ["salmon"], ["fish"],
                  N(208, 20, 0, 13, 0, 0, 59, 0.3, 9, 0, 11, 3.2, 363, 27, 0.4, 26)),
            _item("Sushi rice", "1 cup", 180, 0.9, ["rice", "rice vinegar", "sugar"], [],
                  N(130, 2.4, 29, 0.3, 0.3, 4, 180, 0.2, 2, 0, 0, 0, 30, 8, 0.4, 3)),
            _item("Edamame", "¼ cup", 50, 0.85, ["soybeans"], ["soy"],
                  N(121, 12, 9, 5, 5, 2, 6, 2.3, 63, 6, 0, 0, 436, 64, 1.4, 311)),
            _item("Avocado", "¼ avocado", 50, 0.9, ["avocado"], [],
                  N(160, 2, 9, 15, 7, 0.7, 7, 0.6, 12, 10, 0, 0, 485, 29, 0.6, 81)),
            _item("Seaweed salad", "small scoop", 30, 0.7, ["wakame", "sesame oil", "sesame seeds"], ["sesame", "soy"],
                  N(70, 1, 10, 3, 3, 6, 700, 0.8, 40, 1, 0, 0, 50, 40, 0.3, 50)),
            _item("Soy-sesame dressing", "1 tbsp", 15, 0.6, ["soy sauce", "sesame oil", "mirin"], ["soy", "gluten", "sesame"],
                  N(120, 3, 10, 7, 0.5, 6, 3000, 1, 20, 0, 0, 0, 150, 30, 0.3, 10)),
        ],
        hidden=["Spicy mayo toppings usually contain egg.", "Imitation crab, if added, contains fish and often egg and wheat."],
        score=8,
        summary="A well-balanced bowl with high-quality protein, omega-3s and an excellent dose of vitamin D. Watch the sodium from the dressing and seaweed salad.",
        swaps=["Use brown rice or half rice, half greens", "Ask for dressing on the side", "Add cucumber and radish for crunch and volume"],
    ),
]


SAMPLES_BY_ID = {s["id"]: s for s in SAMPLES}


def catalog() -> list[dict]:
    return [{"id": s["id"], "emoji": s["emoji"], "dish_name": s["dish_name"], "cuisine": s["cuisine"]} for s in SAMPLES]


def analyze(sample_id: str, profile: Profile) -> VisionAnalysis | None:
    sample = SAMPLES_BY_ID.get(sample_id)
    if sample is None:
        return None
    allergens = sorted({a for i in sample["items"] for a in i.allergens})
    as_dish = Dish(sample["dish_name"], sample["cuisine"], "", sample["animal"], allergens, high_carb=True)
    checks = []
    for d in profile.diets:
        ok = fits_profile(as_dish, [d], [])
        checks.append(DietCheck(diet=DIETS[d], compatible=ok,
                                reason="Fits this diet." if ok else "Contains ingredients this diet excludes."))
    return VisionAnalysis(
        is_food=True, dish_name=sample["dish_name"], cuisine=sample["cuisine"], cuisine_confidence=0.9,
        meal_type=sample["meal_type"], items=sample["items"], hidden_allergen_warnings=sample["hidden"],
        diet_compatibility=checks, health_score=sample["score"], health_summary=sample["summary"],
        healthier_swaps=sample["swaps"],
    )
