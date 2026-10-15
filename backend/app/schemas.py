"""Pydantic models shared by the API and the Claude structured-output calls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The 14 major allergens recognised by EU/UK food law, which also covers the US "Big 9".
Allergen = Literal[
    "gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soy",
    "dairy",
    "tree_nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphites",
    "lupin",
    "molluscs",
]

Diet = Literal[
    "vegetarian",
    "vegan",
    "pescatarian",
    "keto",
    "paleo",
    "gluten_free",
    "dairy_free",
    "halal",
    "kosher",
    "low_sodium",
    "diabetic_friendly",
]

NutrientKey = Literal[
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "iron_mg",
    "calcium_mg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_b12_mcg",
    "potassium_mg",
    "magnesium_mg",
    "zinc_mg",
    "folate_mcg",
]


# ---------------------------------------------------------------------------
# Claude output shapes (vision analysis)
# ---------------------------------------------------------------------------


class Nutrients(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sugar_g: float
    sodium_mg: float
    iron_mg: float
    calcium_mg: float
    vitamin_c_mg: float
    vitamin_d_mcg: float
    vitamin_b12_mcg: float
    potassium_mg: float
    magnesium_mg: float
    zinc_mg: float
    folate_mcg: float


class FoodMatch(BaseModel):
    fdc_id: int
    description: str
    source: str


class DetectedItem(BaseModel):
    name: str
    portion_description: str = Field(description="Human portion, e.g. '1 cup' or '2 slices'")
    estimated_grams: float
    confidence: float = Field(description="0.0-1.0 confidence that the item is identified correctly")
    ingredients: list[str]
    allergens: list[Allergen]
    per_100g: Nutrients
    match: FoodMatch | None = None
    alternatives: list[FoodMatch] = []


class DietCheck(BaseModel):
    diet: str
    compatible: bool
    reason: str


class VisionAnalysis(BaseModel):
    is_food: bool
    dish_name: str
    cuisine: str
    cuisine_confidence: float
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "dessert", "drink"]
    items: list[DetectedItem]
    hidden_allergen_warnings: list[str] = Field(
        description="Allergens that may be present but are not visible, e.g. 'curry sauce often contains cashews'"
    )
    diet_compatibility: list[DietCheck]
    health_score: int = Field(description="1 (very unhealthy) to 10 (very healthy)")
    health_summary: str
    healthier_swaps: list[str]


# ---------------------------------------------------------------------------
# Claude output shapes (recipes & meal plans)
# ---------------------------------------------------------------------------


class ServingNutrition(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    iron_mg: float | None = None  # not every recipe source reports these
    calcium_mg: float | None = None


class Recipe(BaseModel):
    name: str
    cuisine: str
    description: str
    prep_minutes: int
    cook_minutes: int
    servings: int
    ingredients: list[str]
    steps: list[str]
    allergens: list[Allergen]
    diet_tags: list[str]
    highlight_nutrients: list[str]
    per_serving: ServingNutrition
    id: int | None = None
    image: str | None = None
    measurements_estimated: bool = False
    may_contain: list[Allergen] = []


class RecipeList(BaseModel):
    recipes: list[Recipe]


class PlannedMeal(BaseModel):
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    name: str
    cuisine: str
    description: str
    calories: float
    protein_g: float
    iron_mg: float | None = None
    allergens: list[Allergen]
    recipe_id: int | None = None


class PlanDay(BaseModel):
    day: int
    theme: str
    meals: list[PlannedMeal]
    total_calories: float
    total_protein_g: float
    tip: str


class MealPlan(BaseModel):
    title: str
    days: list[PlanDay]
    shopping_list: list[str]
    notes: str


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class Profile(BaseModel):
    name: str = ""
    sex: Literal["female", "male", "other"] = "female"
    age: int = 30
    diets: list[Diet] = []
    allergens: list[Allergen] = []
    cuisines: list[str] = []
    calorie_target: int = 2000
    goal: Literal["maintain", "lose", "gain", "muscle"] = "maintain"


class ItemInput(BaseModel):
    name: str
    portion_description: str = ""
    estimated_grams: float
    confidence: float = 1.0
    ingredients: list[str] = []
    allergens: list[Allergen] = []
    per_100g: Nutrients
    match: FoodMatch | None = None
    alternatives: list[FoodMatch] = []


class DescribeRequest(BaseModel):
    dish_name: str
    cuisine: str = ""
    meal_type: str = "lunch"
    items: list[ItemInput]


class EvaluateRequest(BaseModel):
    items: list[ItemInput]
    scope: Literal["meal", "day"] = "meal"


class RecipeRequest(BaseModel):
    cuisine: str | None = None
    focus_nutrient: NutrientKey | None = None
    ingredients_on_hand: list[str] = []
    meal_type: str | None = None
    max_minutes: int | None = None
    count: int = Field(default=3, ge=1, le=6)
    # Allergens to exclude for this search; None means "use the profile's allergens".
    avoid_allergens: list[Allergen] | None = None


class MealPlanRequest(BaseModel):
    days: int = Field(default=3, ge=1, le=7)
    focus_nutrients: list[NutrientKey] = []
    cuisines: list[str] = []
    avoid_allergens: list[Allergen] | None = None


class LogMealRequest(BaseModel):
    dish_name: str
    cuisine: str = ""
    meal_type: str = "meal"
    items: list[ItemInput]
    thumbnail: str | None = Field(default=None, description="Small data: URL preview")


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=300)


class LocalModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    device: Literal["gpu", "cpu"] = "gpu"
