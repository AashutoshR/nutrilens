"""NutriLens API."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ai, analysis, db, foods, local, measurements, recipes, samples
from .config import active_model, ai_connected, local_device, local_model, provider, public_mode, set_env, settings
from .knowledge import ALLERGENS, CUISINES, DIETS, GAP_NUTRIENTS, NUTRIENTS, suggestions_for
from .nutrition import evaluate
from .schemas import (
    ApiKeyRequest, DescribeRequest, EvaluateRequest, ItemInput, LocalModelRequest, LogMealRequest, MealPlan,
    MealPlanRequest, Profile, Recipe, RecipeList, RecipeRequest, VisionAnalysis,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nutrilens")

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    if provider() == "local":
        asyncio.create_task(local.warm_up())  # start the AI and load the model in the background
    log.info("NutriLens ready (ai=%s %s, food database=%s, recipes=%s)", provider(), active_model(),
             foods.available(), recipes.available())
    yield


app = FastAPI(title="NutriLens API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

VISITOR_COOKIE = "nl_visitor"


@app.middleware("http")
async def visitor_scope(request: Request, call_next):
    """When hosted, each browser gets an anonymous id so profiles and meal logs stay private to it."""
    if not public_mode():
        return await call_next(request)
    vid = request.cookies.get(VISITOR_COOKIE, "")
    fresh = not re.fullmatch(r"[0-9a-f]{32}", vid)
    if fresh:
        vid = uuid.uuid4().hex
    token = db.visitor.set(vid)
    try:
        response = await call_next(request)
    finally:
        db.visitor.reset(token)
    if fresh:
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"  # Render terminates TLS
        response.set_cookie(VISITOR_COOKIE, vid, max_age=400 * 24 * 3600, httponly=True, samesite="lax", secure=https)
    return response


def require_admin() -> None:
    """Changing the AI or its keys is only possible on the computer running NutriLens, never on a hosted site."""
    if public_mode():
        raise HTTPException(404, "Not found")


# Photo scans per visitor per hour on a hosted site, so one person can't use up the shared AI quota.
SCAN_LIMIT = 30
_scans: dict[str, deque] = defaultdict(deque)


def check_scan_quota() -> None:
    if not public_mode():
        return
    now, recent = time.monotonic(), _scans[db.visitor.get()]
    while recent and now - recent[0] > 3600:
        recent.popleft()
    if len(recent) >= SCAN_LIMIT:
        raise HTTPException(429, "You've scanned a lot of photos in the last hour. Please try again a little later.")
    recent.append(now)


@app.exception_handler(ai.AIError)
@app.exception_handler(local.LocalAIError)
async def ai_error_handler(_: Request, exc: ai.AIError | local.LocalAIError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})


def require_ai() -> None:
    """AI features never fall back to canned answers: if no AI is set up they say so."""
    if not ai_connected():
        raise ai.AIError("Photo analysis isn't available right now because the AI service isn't set up.",
                         503, "ai_not_connected")


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_connected": ai_connected(), "provider": provider(), "model": active_model(),
            "device": local_device() if provider() == "local" else None,
            "food_database": foods.available(), "recipe_database": recipes.available(),
            "recipes_available": recipes.available() or (ai_connected() and provider() == "claude")}


@app.get("/api/data/status")
def data_status():
    return {"foods": foods.stats(), "recipes": recipes.stats()}


# ---------------------------------------------------------------------------
# Admin settings (no customer-facing UI; documented in the README)
# ---------------------------------------------------------------------------


@app.put("/api/settings/api-key")
async def connect_claude(req: ApiKeyRequest):
    require_admin()
    key = req.api_key.strip()
    if not key.startswith("sk-ant-"):
        raise HTTPException(400, "That doesn't look like an Anthropic API key. Keys start with \"sk-ant-\".")
    await ai.verify_key(key)
    set_env("ANTHROPIC_API_KEY", key)
    set_env("NUTRILENS_PROVIDER", "claude")
    ai.reset_client()
    return health()


@app.delete("/api/settings/api-key")
def disconnect_claude():
    require_admin()
    set_env("ANTHROPIC_API_KEY", None)
    ai.reset_client()
    return health()


@app.get("/api/settings/local")
async def local_status():
    """Is Ollama running, and which installed models can read photos?"""
    require_admin()
    return {**await local.vision_models(), "selected": local_model(), "device": local_device()}


@app.put("/api/settings/local")
async def use_local_ai(req: LocalModelRequest):
    require_admin()
    status = await local.vision_models()
    if not status["running"]:
        raise HTTPException(503, "Ollama isn't running. Open the Ollama app on this computer, then try again.")
    if req.model not in {m["name"] for m in status["models"]}:
        raise HTTPException(400, f"{req.model} isn't installed or can't read photos.")
    set_env("NUTRILENS_LOCAL_MODEL", req.model)
    set_env("NUTRILENS_LOCAL_DEVICE", req.device)
    set_env("NUTRILENS_PROVIDER", "local")
    return health()


# ---------------------------------------------------------------------------
# Profile and reference data
# ---------------------------------------------------------------------------


@app.get("/api/meta")
def meta():
    return {
        "allergens": ALLERGENS,
        "diets": DIETS,
        "cuisines": CUISINES,
        "nutrients": NUTRIENTS,
        "gap_nutrients": GAP_NUTRIENTS,
    }


@app.get("/api/profile", response_model=Profile)
def get_profile():
    return db.get_profile()


@app.put("/api/profile", response_model=Profile)
def put_profile(profile: Profile):
    return db.save_profile(profile)


# ---------------------------------------------------------------------------
# Photo analysis (RAG: the AI looks, the USDA database supplies the nutrition)
# ---------------------------------------------------------------------------


@app.post("/api/analyze", status_code=202)
async def analyze(image: UploadFile = File(...)):
    if image.content_type not in IMAGE_TYPES:
        raise HTTPException(415, "Please upload a JPEG, PNG, WebP or GIF image.")
    data = await image.read()
    if len(data) > settings.max_image_bytes:
        raise HTTPException(413, "Image is larger than 5 MB. Please use a smaller photo.")
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    require_ai()
    if not foods.available():
        raise HTTPException(503, "The food database isn't installed yet. See the README: \"Build the food database\".")
    check_scan_quota()
    return {"job_id": analysis.start_job(data, image.content_type, db.get_profile())}


@app.get("/api/analyze/{job_id}")
def analyze_status(job_id: str):
    status = analysis.job_status(job_id)
    if status is None:
        raise HTTPException(404, "That analysis has expired. Please scan the photo again.")
    return status


@app.post("/api/describe")
def describe(req: DescribeRequest):
    """Recompute nutrition and insights after the user changes portions or food matches; no AI call."""
    return analysis.describe(req.dish_name, req.cuisine, req.meal_type, req.items, db.get_profile())


def analysis_response(result: VisionAnalysis, profile: Profile, sample: bool) -> dict:
    items = [ItemInput(**i.model_dump()) for i in result.items]
    return {
        "sample": sample,
        "analysis": result.model_dump(),
        "evaluation": evaluate(items, profile, "meal") if result.is_food else None,
    }


@app.get("/api/samples")
def list_samples():
    return samples.catalog()


@app.post("/api/samples/{sample_id}/analyze")
def analyze_sample(sample_id: str):
    """A built-in example meal, only shown when the user explicitly asks for a sample."""
    profile = db.get_profile()
    result = samples.analyze(sample_id, profile)
    if result is None:
        raise HTTPException(404, "Unknown sample meal.")
    return analysis_response(result, profile, sample=True)


# ---------------------------------------------------------------------------
# Food database lookups
# ---------------------------------------------------------------------------


@app.get("/api/foods/search")
def search_foods(q: str, branded: bool = False, limit: int = 12):
    return foods.search(q, limit=min(limit, 30), include_branded=branded)


@app.get("/api/foods/barcode/{gtin}")
def food_by_barcode(gtin: str):
    food = foods.by_barcode(gtin)
    if food is None:
        raise HTTPException(404, "No product with that barcode in the database.")
    return food


@app.get("/api/foods/{fdc_id}")
def get_food(fdc_id: int):
    food = foods.get(fdc_id)
    if food is None:
        raise HTTPException(404, "Food not found.")
    return food


# ---------------------------------------------------------------------------
# Meal log
# ---------------------------------------------------------------------------


@app.post("/api/evaluate")
def evaluate_items(req: EvaluateRequest):
    """Recalculate nutrition after the user edits portions; no AI call."""
    return evaluate(req.items, db.get_profile(), req.scope)


@app.post("/api/meals", status_code=201)
def log_meal(req: LogMealRequest):
    if not req.items:
        raise HTTPException(400, "A meal needs at least one item.")
    calories = evaluate(req.items, db.get_profile())["totals"]["calories"]
    return {"id": db.add_meal(req, calories)}


@app.get("/api/meals")
def list_meals(day: date | None = None):
    return db.meals_on(day or date.today())


@app.delete("/api/meals/{meal_id}", status_code=204)
def remove_meal(meal_id: int):
    if not db.delete_meal(meal_id):
        raise HTTPException(404, "Meal not found.")


@app.get("/api/today")
def today():
    meals = db.meals_on(date.today())
    items = [ItemInput(**i) for m in meals for i in m["items"]]
    return {
        "meals": meals,
        "evaluation": evaluate(items, db.get_profile(), "day"),
        "history": db.history(7),
    }


@app.get("/api/nutrients/{key}")
def nutrient_guide(key: str):
    p = db.get_profile()
    guide = suggestions_for(key, p.diets, p.allergens, p.cuisines, limit_sources=10, limit_dishes=12)
    if guide is None:
        raise HTTPException(404, "No guide for that nutrient.")
    return guide


# ---------------------------------------------------------------------------
# Recipes and meal plans: retrieved from the recipe database when installed, otherwise written by the AI
# ---------------------------------------------------------------------------


def require_recipe_writer() -> None:
    """Writing whole recipes is too slow and unreliable for a small on-device model, so only Claude does it."""
    if not (ai_connected() and provider() == "claude"):
        raise HTTPException(503, "The recipe collection is still being set up. Please check back soon.")


@app.post("/api/recipes", response_model=RecipeList)
async def find_recipes(req: RecipeRequest):
    if recipes.available():
        return recipes.search(req, db.get_profile())
    require_recipe_writer()
    return await ai.generate_recipes(req, db.get_profile())


@app.get("/api/recipes/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: int):
    recipe = recipes.get(recipe_id)
    if recipe is None:
        raise HTTPException(404, "Recipe not found.")
    return measurements.cached(recipe)


@app.post("/api/recipes/{recipe_id}/measurements", response_model=Recipe)
async def complete_measurements(recipe_id: int):
    """Fill in the measurement units the recipe data is missing (AI, once per recipe, then cached)."""
    recipe = recipes.get(recipe_id)
    if recipe is None:
        raise HTTPException(404, "Recipe not found.")
    return await measurements.complete(recipe)


@app.post("/api/meal-plan", response_model=MealPlan)
async def meal_plan(req: MealPlanRequest):
    if recipes.available():
        return recipes.meal_plan(req, db.get_profile())
    require_recipe_writer()
    return await ai.generate_meal_plan(req, db.get_profile())


# Serve the built React app (npm run build) from the same origin in production.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.middleware("http")
    async def cache_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            # Built files have a content hash in their name, so they never change.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif not request.url.path.startswith("/api/"):
            # Always re-check the page itself so a new build shows up on the next load.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = FRONTEND_DIST / path
        if path and file.is_file() and FRONTEND_DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
