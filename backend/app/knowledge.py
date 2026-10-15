"""Curated nutrition knowledge: allergens, cuisines, nutrient food sources and popular dishes.

The data here is deterministic so nutrient-gap suggestions are instant, free and work
offline; Claude is used for the open-ended parts (vision, recipes, meal plans).

Each food/dish carries an ``animal`` level so it can be filtered against a diet:
  none < dairy_egg < fish < meat < pork
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ALLERGENS = {
    "gluten": {"label": "Gluten", "icon": "🌾"},
    "crustaceans": {"label": "Crustaceans", "icon": "🦐"},
    "eggs": {"label": "Eggs", "icon": "🥚"},
    "fish": {"label": "Fish", "icon": "🐟"},
    "peanuts": {"label": "Peanuts", "icon": "🥜"},
    "soy": {"label": "Soy", "icon": "🫘"},
    "dairy": {"label": "Dairy", "icon": "🥛"},
    "tree_nuts": {"label": "Tree nuts", "icon": "🌰"},
    "celery": {"label": "Celery", "icon": "🥬"},
    "mustard": {"label": "Mustard", "icon": "🟡"},
    "sesame": {"label": "Sesame", "icon": "⚪"},
    "sulphites": {"label": "Sulphites", "icon": "🍷"},
    "lupin": {"label": "Lupin", "icon": "🌼"},
    "molluscs": {"label": "Molluscs", "icon": "🦪"},
}

DIETS = {
    "vegetarian": "Vegetarian",
    "vegan": "Vegan",
    "pescatarian": "Pescatarian",
    "keto": "Keto / low-carb",
    "paleo": "Paleo",
    "gluten_free": "Gluten-free",
    "dairy_free": "Dairy-free",
    "halal": "Halal",
    "kosher": "Kosher",
    "low_sodium": "Low sodium",
    "diabetic_friendly": "Diabetic-friendly",
}

CUISINES = [
    "Indian", "Italian", "Mexican", "Chinese", "Japanese", "Thai", "Korean",
    "Vietnamese", "Mediterranean", "Middle Eastern", "Greek", "French",
    "American", "Ethiopian", "Caribbean", "Spanish", "British", "Bengali", "Indonesian",
]

NUTRIENTS = {
    # key: label, unit, kind ("target" = aim to reach, "limit" = stay under)
    "calories": {"label": "Calories", "unit": "kcal", "kind": "target"},
    "protein_g": {"label": "Protein", "unit": "g", "kind": "target"},
    "carbs_g": {"label": "Carbohydrates", "unit": "g", "kind": "target"},
    "fat_g": {"label": "Fat", "unit": "g", "kind": "target"},
    "fiber_g": {"label": "Fiber", "unit": "g", "kind": "target"},
    "sugar_g": {"label": "Sugar", "unit": "g", "kind": "limit"},
    "sodium_mg": {"label": "Sodium", "unit": "mg", "kind": "limit"},
    "iron_mg": {"label": "Iron", "unit": "mg", "kind": "target"},
    "calcium_mg": {"label": "Calcium", "unit": "mg", "kind": "target"},
    "vitamin_c_mg": {"label": "Vitamin C", "unit": "mg", "kind": "target"},
    "vitamin_d_mcg": {"label": "Vitamin D", "unit": "mcg", "kind": "target"},
    "vitamin_b12_mcg": {"label": "Vitamin B12", "unit": "mcg", "kind": "target"},
    "potassium_mg": {"label": "Potassium", "unit": "mg", "kind": "target"},
    "magnesium_mg": {"label": "Magnesium", "unit": "mg", "kind": "target"},
    "zinc_mg": {"label": "Zinc", "unit": "mg", "kind": "target"},
    "folate_mcg": {"label": "Folate", "unit": "mcg", "kind": "target"},
}

# Micronutrients we watch for gaps (macros are handled by the calorie split).
GAP_NUTRIENTS = [
    "iron_mg", "calcium_mg", "vitamin_d_mcg", "vitamin_b12_mcg", "fiber_g",
    "protein_g", "vitamin_c_mg", "potassium_mg", "magnesium_mg", "zinc_mg", "folate_mcg",
]


@dataclass
class Food:
    name: str
    amount: float
    serving: str
    animal: str = "none"
    allergens: list[str] = field(default_factory=list)
    high_carb: bool = False


@dataclass
class Dish:
    name: str
    cuisine: str
    blurb: str
    animal: str = "none"
    allergens: list[str] = field(default_factory=list)
    high_carb: bool = False


@dataclass
class NutrientGuide:
    why: str
    deficiency_signs: list[str]
    tip: str
    sources: list[Food]
    dishes: list[Dish]


F, D = Food, Dish

GUIDES: dict[str, NutrientGuide] = {
    "iron_mg": NutrientGuide(
        why="Iron carries oxygen in your blood. Low iron is the most common nutrient deficiency worldwide.",
        deficiency_signs=["Tiredness", "Pale skin", "Shortness of breath", "Cold hands and feet", "Brittle nails"],
        tip="Pair plant iron with vitamin C (lemon, peppers, tomato) to boost absorption up to 3x, and keep tea/coffee an hour away from iron-rich meals.",
        sources=[
            F("Fortified breakfast cereal", 18, "1 serving", "none", ["gluten"], True),
            F("Chicken liver", 9.9, "85 g", "meat"),
            F("Oysters", 7.8, "85 g", "fish", ["molluscs"]),
            F("Lentils, cooked", 6.6, "1 cup", high_carb=True),
            F("Spinach, cooked", 6.4, "1 cup"),
            F("Chickpeas, cooked", 4.7, "1 cup", high_carb=True),
            F("Kidney beans, cooked", 3.9, "1 cup", high_carb=True),
            F("Blackstrap molasses", 3.6, "1 tbsp", high_carb=True),
            F("Firm tofu", 3.4, "½ cup", allergens=["soy"]),
            F("Dark chocolate (70%+)", 3.4, "30 g"),
            F("Quinoa, cooked", 2.8, "1 cup", high_carb=True),
            F("Lean beef", 2.6, "85 g", "meat"),
            F("Pumpkin seeds", 2.5, "30 g"),
            F("Sardines", 2.4, "85 g", "fish", ["fish"]),
        ],
        dishes=[
            D("Palak Paneer", "Indian", "Spinach curry with cottage cheese", "dairy_egg", ["dairy"]),
            D("Chana Masala", "Indian", "Spiced chickpea curry", high_carb=True),
            D("Rajma Chawal", "Indian", "Kidney bean curry with rice", high_carb=True),
            D("Dal Tadka", "Indian", "Tempered yellow lentils", high_carb=True),
            D("Shorshe Palong Shaak", "Bengali", "Spinach cooked in mustard paste", allergens=["mustard"]),
            D("Mujaddara", "Middle Eastern", "Lentils and rice with crispy onions", high_carb=True),
            D("Hummus with Tahini", "Middle Eastern", "Chickpea dip with sesame", allergens=["sesame"]),
            D("Fakes (Greek lentil soup)", "Greek", "Lentil soup with vinegar and olive oil", high_carb=True),
            D("Spanakopita", "Greek", "Spinach and feta pie", "dairy_egg", ["gluten", "dairy", "eggs"], True),
            D("Black Bean Tacos", "Mexican", "Corn tortillas with black beans and salsa", high_carb=True),
            D("Carne Asada", "Mexican", "Grilled marinated steak", "meat"),
            D("Pasta e Fagioli", "Italian", "Pasta and bean soup", allergens=["gluten", "celery"], high_carb=True),
            D("Bistecca alla Fiorentina", "Italian", "Tuscan grilled T-bone steak", "meat"),
            D("Mapo Tofu", "Chinese", "Silken tofu in chili-bean sauce", "pork", ["soy"]),
            D("Beef & Broccoli Stir-fry", "Chinese", "Beef and broccoli in oyster sauce", "meat", ["soy", "molluscs"]),
            D("Gyudon", "Japanese", "Simmered beef and onion rice bowl", "meat", ["soy", "gluten"], True),
            D("Edamame", "Japanese", "Steamed salted soybeans", allergens=["soy"]),
            D("Bulgogi", "Korean", "Grilled soy-marinated beef", "meat", ["soy", "sesame", "gluten"]),
            D("Sigeumchi Namul", "Korean", "Sesame spinach side dish", allergens=["sesame", "soy"]),
            D("Larb", "Thai", "Minced meat salad with lime and herbs", "meat", ["fish"]),
            D("Misir Wot", "Ethiopian", "Spicy red lentil stew", high_carb=True),
            D("Chili con Carne", "American", "Beef and bean chili", "meat", high_carb=True),
            D("Boeuf Bourguignon", "French", "Beef braised in red wine", "meat", ["sulphites", "celery"]),
            D("Liver and Onions", "British", "Pan-fried calf liver with onions", "meat"),
            D("Garbanzos con Espinacas", "Spanish", "Chickpeas with spinach and cumin", high_carb=True),
            D("Callaloo", "Caribbean", "Stewed leafy greens with okra"),
        ],
    ),
    "calcium_mg": NutrientGuide(
        why="Calcium builds bones and teeth and keeps muscles and nerves working.",
        deficiency_signs=["Muscle cramps", "Brittle nails", "Weak bones over time"],
        tip="Vitamin D is needed to absorb calcium; spread calcium across meals (the body absorbs ~500 mg at a time).",
        sources=[
            F("Plain yogurt", 450, "1 cup", "dairy_egg", ["dairy"]),
            F("Parmesan", 330, "30 g", "dairy_egg", ["dairy"]),
            F("Milk", 300, "1 cup", "dairy_egg", ["dairy"]),
            F("Calcium-set tofu", 430, "½ cup", allergens=["soy"]),
            F("Fortified soy milk", 300, "1 cup", allergens=["soy"]),
            F("Canned sardines (with bones)", 325, "85 g", "fish", ["fish"]),
            F("Canned salmon (with bones)", 180, "85 g", "fish", ["fish"]),
            F("Collard greens, cooked", 270, "1 cup"),
            F("Ragi (finger millet) flour", 344, "100 g", high_carb=True),
            F("Tahini", 130, "2 tbsp", allergens=["sesame"]),
            F("Almonds", 75, "30 g", allergens=["tree_nuts"]),
            F("Chia seeds", 180, "30 g"),
        ],
        dishes=[
            D("Ragi Mudde", "Indian", "Finger-millet dumplings", high_carb=True),
            D("Paneer Tikka", "Indian", "Grilled spiced cottage cheese", "dairy_egg", ["dairy"]),
            D("Mishti Doi", "Bengali", "Sweet set yogurt", "dairy_egg", ["dairy"], True),
            D("Tzatziki", "Greek", "Yogurt, cucumber and garlic dip", "dairy_egg", ["dairy"]),
            D("Caprese Salad", "Italian", "Mozzarella, tomato and basil", "dairy_egg", ["dairy"]),
            D("Eggplant Parmigiana", "Italian", "Baked eggplant with parmesan", "dairy_egg", ["dairy", "eggs"]),
            D("Agedashi Tofu", "Japanese", "Fried tofu in dashi broth", "fish", ["soy", "fish", "gluten"]),
            D("Sardinhas Assadas", "Spanish", "Grilled sardines", "fish", ["fish"]),
            D("Quesadillas", "Mexican", "Cheese-filled tortillas", "dairy_egg", ["dairy", "gluten"], True),
            D("Labneh with Za'atar", "Middle Eastern", "Strained yogurt with herbs and sesame", "dairy_egg", ["dairy", "sesame"]),
            D("Bok Choy with Garlic", "Chinese", "Stir-fried bok choy"),
            D("Gratin Dauphinois", "French", "Creamy baked potatoes", "dairy_egg", ["dairy"], True),
        ],
    ),
    "vitamin_d_mcg": NutrientGuide(
        why="Vitamin D helps absorb calcium and supports immunity. Few foods contain it; sunlight is the main source.",
        deficiency_signs=["Fatigue", "Bone or back pain", "Low mood", "Frequent infections"],
        tip="10-30 minutes of midday sun a few times a week helps. Many people in northern latitudes need a supplement in winter; ask your doctor.",
        sources=[
            F("Salmon", 14.2, "85 g", "fish", ["fish"]),
            F("Rainbow trout", 16.2, "85 g", "fish", ["fish"]),
            F("Canned tuna", 1.7, "85 g", "fish", ["fish"]),
            F("Sardines", 4.1, "85 g", "fish", ["fish"]),
            F("UV-exposed mushrooms", 9.2, "½ cup"),
            F("Fortified milk", 2.9, "1 cup", "dairy_egg", ["dairy"]),
            F("Fortified plant milk", 2.9, "1 cup", allergens=["soy"]),
            F("Egg yolk", 1.1, "1 large", "dairy_egg", ["eggs"]),
            F("Cod liver oil", 11.3, "1 tsp", "fish", ["fish"]),
        ],
        dishes=[
            D("Salmon Teriyaki", "Japanese", "Glazed grilled salmon", "fish", ["fish", "soy", "gluten"]),
            D("Shorshe Ilish", "Bengali", "Hilsa fish in mustard sauce", "fish", ["fish", "mustard"]),
            D("Fish Moilee", "Indian", "Kerala fish in coconut milk", "fish", ["fish"]),
            D("Grilled Salmon with Greens", "Mediterranean", "Simple lemon-herb salmon", "fish", ["fish"]),
            D("Mushroom Risotto", "Italian", "Creamy rice with mushrooms", "dairy_egg", ["dairy"], True),
            D("Shakshuka", "Middle Eastern", "Eggs poached in spiced tomato", "dairy_egg", ["eggs"]),
            D("Fish Tacos", "Mexican", "Grilled fish in corn tortillas", "fish", ["fish"], True),
            D("Kedgeree", "British", "Smoked fish, rice and eggs", "fish", ["fish", "eggs", "dairy"], True),
            D("Mushroom Japchae", "Korean", "Glass noodles with mushrooms", allergens=["soy", "sesame"], high_carb=True),
        ],
    ),
    "vitamin_b12_mcg": NutrientGuide(
        why="B12 keeps nerves and red blood cells healthy. It is found almost only in animal foods, so vegans need fortified foods or supplements.",
        deficiency_signs=["Fatigue", "Tingling in hands or feet", "Memory problems", "Mouth ulcers"],
        tip="If you eat vegan, rely on fortified foods (nutritional yeast, plant milks) or a B12 supplement.",
        sources=[
            F("Clams", 84, "85 g", "fish", ["molluscs"]),
            F("Beef liver", 60, "85 g", "meat"),
            F("Nutritional yeast (fortified)", 8, "2 tbsp"),
            F("Salmon", 2.6, "85 g", "fish", ["fish"]),
            F("Tuna", 2.5, "85 g", "fish", ["fish"]),
            F("Beef", 1.4, "85 g", "meat"),
            F("Milk", 1.2, "1 cup", "dairy_egg", ["dairy"]),
            F("Fortified plant milk", 1.0, "1 cup", allergens=["soy"]),
            F("Yogurt", 1.1, "1 cup", "dairy_egg", ["dairy"]),
            F("Eggs", 0.5, "1 large", "dairy_egg", ["eggs"]),
        ],
        dishes=[
            D("Linguine alle Vongole", "Italian", "Pasta with clams", "fish", ["molluscs", "gluten"], True),
            D("Egg Curry", "Indian", "Boiled eggs in onion-tomato gravy", "dairy_egg", ["eggs"]),
            D("Nicoise Salad", "French", "Tuna, egg and green bean salad", "fish", ["fish", "eggs"]),
            D("Poke Bowl", "American", "Raw tuna or salmon rice bowl", "fish", ["fish", "soy", "sesame"], True),
            D("Pho Bo", "Vietnamese", "Beef noodle soup", "meat", ["fish"], True),
            D("Tofu Scramble with Nutritional Yeast", "American", "Vegan breakfast scramble", allergens=["soy"]),
            D("Bibimbap", "Korean", "Rice bowl with beef, egg and vegetables", "meat", ["eggs", "soy", "sesame"], True),
        ],
    ),
    "fiber_g": NutrientGuide(
        why="Fiber feeds healthy gut bacteria, keeps you full, and helps control blood sugar and cholesterol.",
        deficiency_signs=["Constipation", "Feeling hungry soon after meals", "Blood sugar swings"],
        tip="Increase fiber gradually and drink more water as you do.",
        sources=[
            F("Chia seeds", 10, "30 g"),
            F("Lentils, cooked", 15.6, "1 cup", high_carb=True),
            F("Black beans, cooked", 15, "1 cup", high_carb=True),
            F("Raspberries", 8, "1 cup"),
            F("Avocado", 10, "1 whole"),
            F("Oats", 8, "1 cup cooked", allergens=["gluten"], high_carb=True),
            F("Pear with skin", 5.5, "1 medium", high_carb=True),
            F("Broccoli, cooked", 5, "1 cup"),
            F("Almonds", 3.5, "30 g", allergens=["tree_nuts"]),
        ],
        dishes=[
            D("Chana Masala", "Indian", "Spiced chickpea curry", high_carb=True),
            D("Misir Wot", "Ethiopian", "Spicy red lentil stew", high_carb=True),
            D("Minestrone", "Italian", "Vegetable and bean soup", allergens=["celery"], high_carb=True),
            D("Frijoles Charros", "Mexican", "Pinto bean stew", "pork", high_carb=True),
            D("Falafel Bowl", "Middle Eastern", "Chickpea fritters with salad", allergens=["sesame"], high_carb=True),
            D("Guacamole", "Mexican", "Mashed avocado dip"),
            D("Overnight Oats", "American", "Soaked oats with fruit and seeds", allergens=["gluten"], high_carb=True),
            D("Fasolada", "Greek", "White bean soup", allergens=["celery"], high_carb=True),
        ],
    ),
    "protein_g": NutrientGuide(
        why="Protein builds and repairs muscle, keeps you full and supports immunity.",
        deficiency_signs=["Muscle loss", "Feeling weak", "Slow healing", "Constant hunger"],
        tip="Spread protein across meals; 25-30 g per meal is a good target for most adults.",
        sources=[
            F("Chicken breast", 26, "85 g", "meat"),
            F("Greek yogurt", 20, "1 cup", "dairy_egg", ["dairy"]),
            F("Lentils, cooked", 18, "1 cup", high_carb=True),
            F("Tempeh", 17, "85 g", allergens=["soy"]),
            F("Tuna", 22, "85 g", "fish", ["fish"]),
            F("Paneer", 18, "100 g", "dairy_egg", ["dairy"]),
            F("Eggs", 12.6, "2 large", "dairy_egg", ["eggs"]),
            F("Firm tofu", 10, "½ cup", allergens=["soy"]),
            F("Seitan", 21, "85 g", allergens=["gluten"]),
            F("Peanut butter", 7, "2 tbsp", allergens=["peanuts"]),
        ],
        dishes=[
            D("Tandoori Chicken", "Indian", "Yogurt-marinated grilled chicken", "meat", ["dairy"]),
            D("Paneer Bhurji", "Indian", "Spiced scrambled cottage cheese", "dairy_egg", ["dairy"]),
            D("Souvlaki", "Greek", "Grilled meat skewers", "meat"),
            D("Chicken Tikka Salad", "Indian", "Grilled chicken on greens", "meat", ["dairy"]),
            D("Tempeh Stir-fry", "Chinese", "Tempeh with vegetables", allergens=["soy"]),
            D("Steamed Fish with Ginger", "Chinese", "Whole fish with ginger and scallion", "fish", ["fish", "soy"]),
            D("Chicken Fajitas", "Mexican", "Sizzling chicken and peppers", "meat"),
            D("Tofu Katsu", "Japanese", "Breaded fried tofu", allergens=["soy", "gluten"]),
        ],
    ),
    "vitamin_c_mg": NutrientGuide(
        why="Vitamin C supports immunity, skin and wound healing, and boosts iron absorption.",
        deficiency_signs=["Bleeding gums", "Slow wound healing", "Frequent colds", "Easy bruising"],
        tip="Vitamin C is destroyed by long cooking; eat some raw fruit or vegetables daily.",
        sources=[
            F("Guava", 125, "1 fruit"),
            F("Red bell pepper", 152, "1 cup raw"),
            F("Kiwi", 64, "1 fruit"),
            F("Orange", 70, "1 medium", high_carb=True),
            F("Strawberries", 89, "1 cup"),
            F("Broccoli", 81, "1 cup"),
            F("Amla (Indian gooseberry)", 300, "100 g"),
            F("Papaya", 88, "1 cup", high_carb=True),
        ],
        dishes=[
            D("Kachumber Salad", "Indian", "Cucumber, tomato and onion salad"),
            D("Som Tam", "Thai", "Green papaya salad", "fish", ["fish", "peanuts", "crustaceans"]),
            D("Pico de Gallo", "Mexican", "Fresh tomato and chili salsa"),
            D("Gazpacho", "Spanish", "Chilled tomato and pepper soup"),
            D("Tabbouleh", "Middle Eastern", "Parsley, tomato and bulgur salad", allergens=["gluten"]),
            D("Peperonata", "Italian", "Stewed sweet peppers"),
            D("Goi Cuon", "Vietnamese", "Fresh spring rolls with herbs", "fish", ["crustaceans", "peanuts"], True),
        ],
    ),
    "potassium_mg": NutrientGuide(
        why="Potassium balances fluids and helps keep blood pressure in check.",
        deficiency_signs=["Muscle cramps", "Weakness", "Irregular heartbeat"],
        tip="Swap some salty snacks for potassium-rich produce to improve your sodium-potassium balance.",
        sources=[
            F("Baked potato with skin", 926, "1 medium", high_carb=True),
            F("White beans, cooked", 1190, "1 cup", high_carb=True),
            F("Spinach, cooked", 840, "1 cup"),
            F("Avocado", 975, "1 whole"),
            F("Banana", 422, "1 medium", high_carb=True),
            F("Coconut water", 600, "1 cup"),
            F("Salmon", 534, "85 g", "fish", ["fish"]),
        ],
        dishes=[
            D("Aloo Palak", "Indian", "Potato and spinach curry", high_carb=True),
            D("Fasolada", "Greek", "White bean soup", allergens=["celery"], high_carb=True),
            D("Patatas a lo Pobre", "Spanish", "Potatoes with peppers and onion", high_carb=True),
            D("Plantain & Black Beans", "Caribbean", "Fried plantain with beans", high_carb=True),
            D("Guacamole", "Mexican", "Mashed avocado dip"),
        ],
    ),
    "magnesium_mg": NutrientGuide(
        why="Magnesium supports over 300 enzymes, including those for energy, muscles, nerves and sleep.",
        deficiency_signs=["Muscle twitches", "Poor sleep", "Fatigue", "Headaches"],
        tip="Nuts, seeds and whole grains are the easiest daily sources.",
        sources=[
            F("Pumpkin seeds", 156, "30 g"),
            F("Almonds", 80, "30 g", allergens=["tree_nuts"]),
            F("Spinach, cooked", 157, "1 cup"),
            F("Cashews", 74, "30 g", allergens=["tree_nuts"]),
            F("Black beans, cooked", 120, "1 cup", high_carb=True),
            F("Dark chocolate (70%+)", 65, "30 g"),
            F("Brown rice, cooked", 86, "1 cup", high_carb=True),
        ],
        dishes=[
            D("Palak Dal", "Indian", "Spinach and lentil stew", high_carb=True),
            D("Kaju Curry", "Indian", "Cashew curry", "dairy_egg", ["tree_nuts", "dairy"]),
            D("Black Bean Soup", "Mexican", "Smoky black bean soup", high_carb=True),
            D("Muhammara", "Middle Eastern", "Red pepper and walnut dip", allergens=["tree_nuts", "gluten"]),
            D("Brown Rice Bibimbap", "Korean", "Vegetable rice bowl", allergens=["soy", "sesame"], high_carb=True),
        ],
    ),
    "zinc_mg": NutrientGuide(
        why="Zinc supports immunity, wound healing, taste and smell.",
        deficiency_signs=["Frequent infections", "Loss of taste or smell", "Slow healing", "Hair loss"],
        tip="Soaking or sprouting beans and grains improves zinc absorption from plant foods.",
        sources=[
            F("Oysters", 32, "85 g", "fish", ["molluscs"]),
            F("Beef", 5.3, "85 g", "meat"),
            F("Crab", 6.5, "85 g", "fish", ["crustaceans"]),
            F("Pumpkin seeds", 2.2, "30 g"),
            F("Chickpeas, cooked", 2.5, "1 cup", high_carb=True),
            F("Cashews", 1.6, "30 g", allergens=["tree_nuts"]),
            F("Oats", 2.3, "1 cup cooked", allergens=["gluten"], high_carb=True),
        ],
        dishes=[
            D("Chole", "Indian", "North Indian chickpea curry", high_carb=True),
            D("Beef Rendang", "Indonesian", "Slow-cooked spiced beef", "meat"),
            D("Crab Fried Rice", "Thai", "Fried rice with crab", "fish", ["crustaceans", "eggs", "soy"], True),
            D("Hamburger Steak", "American", "Seasoned beef patty", "meat"),
            D("Hummus", "Middle Eastern", "Chickpea and tahini dip", allergens=["sesame"]),
        ],
    ),
    "folate_mcg": NutrientGuide(
        why="Folate is needed to make DNA and red blood cells, and is especially important before and during pregnancy.",
        deficiency_signs=["Fatigue", "Mouth sores", "Irritability"],
        tip="Leafy greens and legumes are the richest natural sources; folate is heat-sensitive, so steam rather than boil.",
        sources=[
            F("Lentils, cooked", 358, "1 cup", high_carb=True),
            F("Chickpeas, cooked", 282, "1 cup", high_carb=True),
            F("Spinach, cooked", 263, "1 cup"),
            F("Asparagus", 268, "1 cup"),
            F("Avocado", 160, "1 whole"),
            F("Broccoli", 168, "1 cup"),
            F("Edamame", 482, "1 cup", allergens=["soy"]),
        ],
        dishes=[
            D("Dal Makhani", "Indian", "Black lentils simmered with butter", "dairy_egg", ["dairy"], True),
            D("Edamame", "Japanese", "Steamed salted soybeans", allergens=["soy"]),
            D("Asparagus Risotto", "Italian", "Creamy asparagus rice", "dairy_egg", ["dairy"], True),
            D("Lentil Soup", "Mediterranean", "Lemony red lentil soup", high_carb=True),
            D("Spinach Gomae", "Japanese", "Spinach with sesame dressing", allergens=["sesame", "soy"]),
        ],
    ),
}

_ANIMAL_RANK = {"none": 0, "dairy_egg": 1, "fish": 2, "meat": 3, "pork": 4}


def fits_profile(entry: Food | Dish, diets: list[str], allergens: list[str]) -> bool:
    """True if a food/dish is compatible with the user's diets and avoids their allergens."""
    if set(entry.allergens) & set(allergens):
        return False
    rank = _ANIMAL_RANK[entry.animal]
    if "vegan" in diets and rank > 0:
        return False
    if "vegetarian" in diets and rank > 1:
        return False
    if "pescatarian" in diets and rank > 2:
        return False
    if ("halal" in diets or "kosher" in diets) and entry.animal == "pork":
        return False
    if "kosher" in diets and {"crustaceans", "molluscs"} & set(entry.allergens):
        return False
    if "gluten_free" in diets and "gluten" in entry.allergens:
        return False
    if "dairy_free" in diets and "dairy" in entry.allergens:
        return False
    if ("keto" in diets or "diabetic_friendly" in diets) and entry.high_carb:
        return False
    return True


def suggestions_for(nutrient: str, diets: list[str], allergens: list[str],
                    cuisines: list[str], limit_sources: int = 6, limit_dishes: int = 6) -> dict | None:
    """Food sources and popular dishes for a nutrient, filtered to the user's profile.

    Dishes from the user's preferred cuisines are ranked first.
    """
    guide = GUIDES.get(nutrient)
    if guide is None:
        return None
    meta = NUTRIENTS[nutrient]
    sources = [s for s in guide.sources if fits_profile(s, diets, allergens)]
    sources.sort(key=lambda s: s.amount, reverse=True)
    dishes = [d for d in guide.dishes if fits_profile(d, diets, allergens)]
    preferred = {c.lower() for c in cuisines}
    dishes.sort(key=lambda d: d.cuisine.lower() not in preferred)
    return {
        "nutrient": nutrient,
        "label": meta["label"],
        "unit": meta["unit"],
        "why": guide.why,
        "deficiency_signs": guide.deficiency_signs,
        "tip": guide.tip,
        "sources": [asdict(s) for s in sources[:limit_sources]],
        "dishes": [
            {**asdict(d), "preferred": d.cuisine.lower() in preferred} for d in dishes[:limit_dishes]
        ],
        "filtered_out": (len(guide.sources) - len(sources)) + (len(guide.dishes) - len(dishes)),
    }
