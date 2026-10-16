# NutriLens

Take a photo of a meal and get its nutrition, allergens and recipe ideas.

NutriLens uses a vision model to recognise the foods in a photo, then looks each one up in USDA FoodData Central to
work out calories, macros and micronutrients. It also checks the meal against your diet and allergies, points out
nutrients you're short on, and suggests recipes and meal plans from a Food.com recipe collection.

## Features

- Food recognition from an uploaded file, a pasted image (Ctrl+V) or a webcam
- Nutrition from USDA FoodData Central: calories, macros and 12 vitamins and minerals
- Portion editing, switching a food's USDA match, and adding foods the AI missed, all recalculated instantly
- Detection of the 14 major allergens, including likely hidden ones (e.g. cashews in curry sauces)
- Diet checks: vegetarian, vegan, pescatarian, keto, paleo, gluten-free, dairy-free, halal, kosher and more
- Nutrient gap suggestions, e.g. low iron shows iron-rich foods and dishes from your preferred cuisines
- Recipe search and multi-day meal plans with a shopping list, filtered by allergens (including "may contain")
- Daily log with a 7-day calorie history

## How it works

```
photo ──> vision model ──> list of foods + estimated portions
                │
                ▼
          full-text search over USDA FoodData Central (SQLite FTS5)
                │
                ▼
          nutrients x grams, allergens, diet checks, score, swaps
```

The model is only asked to name the foods and estimate portions. All nutrition numbers come from the matched USDA
records, and the allergen, diet and scoring logic is rule-based (`backend/app/insights.py`), so results are
repeatable and every food shows which database record it came from.

Photo analysis runs as a background job, so the rest of the app stays usable while a photo is being processed.

Supported vision backends:

| Provider | Setting | Notes |
|---|---|---|
| Ollama | `NUTRILENS_PROVIDER=local` | Runs on your machine; default model `gemma4:e4b` |
| Google Gemini | `NUTRILENS_PROVIDER=gemini` | Free tier available; used for the hosted version |
| Anthropic Claude | `NUTRILENS_PROVIDER=claude` | Paid; can also write recipes when no recipe database is installed |

With Ollama as the provider and `GEMINI_API_KEY` set, a scan that takes longer than 45 seconds (for example because a
game is using the GPU) falls back to Gemini.

## Tech stack

- Frontend: React 18, Vite
- Backend: Python, FastAPI, SQLite (FTS5)
- Data: USDA FoodData Central, Food.com Recipes and Reviews

## Getting started

### Prerequisites

- Windows (the `start.bat` launcher; the app itself is cross-platform)
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) with a vision model, or a Gemini / Anthropic API key

### Quick start

```bash
git clone https://github.com/AashutoshR/nutrilens.git
cd nutrilens
```

Double-click `start.bat`. On first run it creates the Python virtual environment, unpacks the bundled data and builds
the frontend, then serves the app at http://localhost:8000.

### Food and recipe data

The repository ships a lite edition of the data in `backend/data-lite/`: the 13,602 generic USDA foods (no branded
products) and 50,000 recipes. `start.bat` unpacks it into `backend/data/` if no databases are there yet.

For the full datasets (about 1.9 million foods including branded products, and about 500,000 recipes):

1. Download the FoodData Central "Full Download" CSV from https://fdc.nal.usda.gov/download-datasets/, then run:

   ```bash
   .venv\Scripts\python scripts\build_food_db.py path\to\FoodData_Central_csv_2026-04-30.zip
   ```

2. Download [Food.com Recipes and Reviews](https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews) from Kaggle, then run:

   ```bash
   .venv\Scripts\python scripts\build_recipe_db.py path\to\archive.zip
   ```

`scripts/build_lite_data.py` regenerates `data-lite/` from the full databases.

### Configuration

Settings are read from environment variables or `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `NUTRILENS_PROVIDER` | `claude` | `local`, `gemini` or `claude` |
| `NUTRILENS_LOCAL_MODEL` | `gemma4:e4b` | Ollama model used when the provider is `local` |
| `NUTRILENS_LOCAL_DEVICE` | `gpu` | `gpu` or `cpu` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `GEMINI_API_KEY` | | Gemini key from https://aistudio.google.com/apikey |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model ID |
| `ANTHROPIC_API_KEY` | | Claude key from https://console.anthropic.com |
| `NUTRILENS_MODEL` | `claude-opus-5-5` | Claude model ID |
| `NUTRILENS_DB` | `backend/nutrilens.db` | SQLite file for profiles and meal logs |
| `NUTRILENS_PUBLIC` | off | Hosted mode: per-visitor data (cookie), admin endpoints disabled, scan rate limit |

Example for local use with Ollama:

```
NUTRILENS_PROVIDER=local
NUTRILENS_LOCAL_MODEL=gemma4:e4b
```

### Development

```bash
# backend (http://localhost:8000, API docs at /docs)
cd backend
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# frontend with hot reload (http://localhost:5173)
cd frontend
npm install
npm run dev
```

## Deployment

The repo contains a `Dockerfile` and a Render Blueprint (`render.yaml`). The image bundles the lite data and runs in
hosted mode with Gemini.

1. Create a Gemini API key.
2. In Render, choose New > Blueprint and select this repository.
3. Enter `GEMINI_API_KEY` when prompted.

On Render's free plan the service sleeps after 15 minutes of inactivity, and the filesystem is reset on each restart or
deploy, so saved profiles and meal logs are lost. Attach a persistent disk and point `NUTRILENS_DB` at it to keep them.

## Project structure

```
backend/
  app/
    main.py          API routes
    analysis.py      photo analysis pipeline and background jobs
    foods.py         USDA food search and portion conversion
    recipes.py       recipe search, allergen filtering, meal plans
    insights.py      allergens, diet checks, health score, swaps
    nutrition.py     daily targets and nutrient totals
    knowledge.py     allergen, diet, cuisine and nutrient reference data
    local.py         Ollama client
    gemini.py        Gemini client
    ai.py            Claude client
    db.py            profiles and meal log (SQLite)
  scripts/           database build scripts
  data-lite/         bundled lite databases
frontend/
  src/
    App.jsx          app shell and navigation
    components/      pages (Scan, Today, Nutrient guide, Recipes, Profile) and shared UI
Dockerfile
render.yaml
start.bat
```

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze` | Start analysing a photo (multipart field `image`); returns `job_id` |
| `GET` | `/api/analyze/{job_id}` | Job status and result |
| `POST` | `/api/describe` | Recalculate a meal after edits |
| `GET` | `/api/foods/search?q=` | Search foods (`branded=true` to include branded products) |
| `GET` | `/api/foods/{fdc_id}` | Food details |
| `GET` | `/api/foods/barcode/{gtin}` | Look up a branded food by barcode |
| `POST` | `/api/recipes` | Search recipes |
| `GET` | `/api/recipes/{id}` | Full recipe |
| `POST` | `/api/meal-plan` | Build a meal plan |
| `GET`, `PUT` | `/api/profile` | User profile |
| `GET`, `POST`, `DELETE` | `/api/meals` | Meal log |
| `GET` | `/api/today` | Today's totals and 7-day history |
| `GET` | `/api/nutrients/{key}` | Sources and dishes for a nutrient, e.g. `iron_mg` |

Full interactive documentation is served at `/docs`.

## Data sources

- [USDA FoodData Central](https://fdc.nal.usda.gov), U.S. Department of Agriculture, Agricultural Research Service
- [Food.com Recipes and Reviews](https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews) on Kaggle.
  Check the dataset's terms before commercial use.

## Disclaimer

NutriLens gives estimates for general wellness and is not medical advice. A photo can't show every ingredient, so
anyone with a severe allergy should confirm with whoever prepared the food.
