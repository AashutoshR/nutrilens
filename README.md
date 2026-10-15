# 🥗 NutriLens

**Snap. Know. Nourish.** A multimodal AI nutrition assistant for the desktop. Add a photo of your meal and NutriLens:

- **Identifies every food** on the plate with AI and estimates the portions
- **Looks each food up in the USDA FoodData Central database** (~1.9 million foods), so calories, macros and 12 vitamins and
  minerals come from real data, not AI guesses
- **Flags allergens** (the 14 major allergens), including hidden ones like cashews in curry gravy, and warns loudly when a meal
  contains something you avoid
- **Checks your diet** (vegetarian, vegan, keto, halal, gluten-free and more)
- **Finds nutrient gaps**. *Low in iron?* It shows the best iron sources and popular iron-rich dishes, filtered to your diet,
  with your favourite cuisines first
- **Picks recipes and meal plans** from ~500,000 real, rated Food.com recipes that respect your restrictions, with a shopping list

## How it works (RAG)

```
photo ─► AI "look" step ─► list of foods + portions          (the only AI call: ~30 s on a laptop GPU, seconds with Claude)
             │
             ▼
      retrieval: full-text search over USDA FoodData Central   (data/foods.db, SQLite FTS5, milliseconds)
             │
             ▼
      compute: nutrients × grams, allergens, diet checks,       (rules in insights.py: instant, consistent)
               health score, summary, swaps, nutrient gaps
```

- The AI only has to *recognise* food, which small models do well and quickly. Every number is *retrieved* from USDA data.
- Each food shows the USDA record it matched. Users can switch to another match, search the database, or add a food the AI missed;
  everything recalculates instantly with no AI call.
- Analyses run as background jobs: users can keep using the app and are notified when the meal is ready.
- Recipes and meal plans are retrieved from the Food.com dataset (`data/recipes.db`) by cuisine, meal, ingredients on hand and
  nutrient goals, filtered by the user's diet and allergens. Without that dataset, the AI writes recipes instead.

## Desktop experience

- **Sidebar navigation** with a live "today" calorie ring and scan progress; collapses to an icon rail (automatically below 1180 px wide)
- **Three ways to add a photo:** upload or drag & drop a file, paste a screenshot/photo with **Ctrl+V**, or snap one with your **webcam**
- **Two-panel results:** a sticky summary (photo, score, macros, Log button) beside the detailed nutrition, allergen and gap cards

| Shortcut | Action |
|---|---|
| `Alt+1` … `Alt+5` | Scan · Today · Nutrient guide · Recipes · Profile |
| `Ctrl+O` | Open a photo |
| `Ctrl+V` | Paste an image from the clipboard |
| `Enter` / `Esc` | Analyse the photo / start over |
| `Space` | Capture (in the webcam window) |
| `↑` `↓` | Browse nutrients in the guide |
| `Ctrl+Enter` | Find recipes or build a meal plan |
| `Ctrl+S` | Save your profile |

## Architecture

```
frontend/  React 18 + Vite        Scan · Today · Nutrients · Recipes · Profile
backend/   FastAPI + SQLite
   ├─ analysis.py   the RAG pipeline (look → retrieve → compute) and background jobs
   ├─ foods.py      retrieval over USDA FoodData Central (data/foods.db)
   ├─ recipes.py    recipe and meal-plan retrieval over Food.com (data/recipes.db)
   ├─ insights.py   rules: allergens, diet checks, health score, summary, swaps
   ├─ local.py      on-device AI through Ollama (free, private, offline)
   ├─ ai.py         Claude API (optional, most accurate)
   ├─ nutrition.py  portion scaling, DRI-based daily targets, %DV, nutrient gaps
   ├─ knowledge.py  allergens, diets, cuisines, nutrient guides
   └─ scripts/      build_food_db.py, build_recipe_db.py
```

## Run it

**Requirements:** Python 3.10+ and Node 18+. Double-click **`start.bat`** to set up and start everything, then open
<http://localhost:8000>. Keep its window open while you use the app.

### 1. Build the food database (once, ~10 minutes)

Download the USDA FoodData Central **Full Download (CSV)** from <https://fdc.nal.usda.gov/download-datasets/>
(`FoodData_Central_csv_2026-04-30.zip`, ~460 MB) into `backend/data/raw/usda/`, then:

```bash
cd backend
.venv\Scripts\python scripts\build_food_db.py data\raw\usda\FoodData_Central_csv_2026-04-30.zip
```

### 2. Build the recipe database (optional, ~5 minutes)

Download **Food.com – Recipes and Reviews** from <https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews>
(free Kaggle account), then:

```bash
.venv\Scripts\python scripts\build_recipe_db.py %USERPROFILE%\Downloads\archive.zip
```

### 3. Set up the AI (app owner only; customers never see this)

**Free, on-device (default):** install [Ollama](https://ollama.com) and run `ollama pull gemma4:e4b`, then in `backend/.env`:

```
NUTRILENS_PROVIDER=local
NUTRILENS_LOCAL_MODEL=gemma4:e4b
NUTRILENS_LOCAL_DEVICE=gpu      # or cpu, to leave the graphics card free for games
```

**Claude (most accurate, paid):** set `NUTRILENS_PROVIDER=claude` and `ANTHROPIC_API_KEY=...` from
<https://console.anthropic.com>. Admins can also use `PUT /api/settings/api-key` or `PUT /api/settings/local`.

Without an AI, NutriLens never invents an analysis: it says photo analysis is unavailable. The nutrient guide, recipes and
clearly labelled sample meals still work.

### Development

```bash
cd backend && .venv\Scripts\uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## Deploy to Render

The repository includes a `Dockerfile` and a `render.yaml` Blueprint for Render's free plan.

- **Photos:** the hosted app uses Google Gemini (free tier) to recognise foods. Ollama can't run on Render.
- **Data:** it ships `backend/data-lite/`, a small edition of the data: every generic USDA food (no branded
  products) and the 50,000 best-reviewed recipes. Rebuild it with `python scripts/build_lite_data.py`.
- **Visitors:** each visitor gets a private, anonymous profile and meal log through a cookie, with no sign-up.
- **Locked settings:** the settings that change the AI are switched off on the hosted site.

Steps:

1. Create a Gemini API key at https://aistudio.google.com/apikey.
2. Push this repository to GitHub. A private repository works.
3. In Render, choose **New > Blueprint**, pick the repository and paste the key into `GEMINI_API_KEY` when asked.

Free-plan limits:

- The service sleeps after 15 minutes without visitors, and the first visit afterwards takes about a minute.
- Its disk is wiped on every restart or deploy, so saved profiles and meal logs don't survive.
- To keep profiles and meals, add a Render disk (paid) and set `NUTRILENS_DB` to a path on it.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/analyze` | Start analysing a meal photo (multipart `image`); returns a `job_id` |
| `GET` | `/api/analyze/{job_id}` | Job progress (`looking` → `matching` → `done`), foods seen so far, and the result |
| `POST` | `/api/describe` | Recompute nutrition and insights after portion or match edits (no AI) |
| `GET` | `/api/foods/search?q=` | Search the food database (`&branded=true` to include branded products) |
| `GET` | `/api/foods/{fdc_id}` · `/api/foods/barcode/{gtin}` | One food by USDA id or barcode |
| `POST` | `/api/recipes` · `/api/meal-plan` | Recipes and meal plans for the user's profile |
| `GET/PUT` | `/api/profile` | Diet, allergens, cuisines, calorie target, goal |
| `POST/GET/DELETE` | `/api/meals` | Meal log |
| `GET` | `/api/today` | Today's totals, %DV, remaining gaps, 7-day history |
| `GET` | `/api/nutrients/{key}` | Food sources and popular dishes for a nutrient (e.g. `iron_mg`) |
| `GET` | `/api/data/status` | Which databases are installed and how big they are |

Interactive docs: <http://localhost:8000/docs>

## Data sources and licences

- **USDA FoodData Central**: U.S. Department of Agriculture, Agricultural Research Service. <https://fdc.nal.usda.gov>
- **Food.com Recipes and Reviews** (Kaggle, irkaal): check the dataset's licence before any commercial use.

> NutriLens provides estimates for general wellness and is not medical advice. Photos can't reveal every ingredient,
> so people with severe allergies should always confirm with whoever prepared the food.
