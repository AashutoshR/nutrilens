"""Photo analysis as retrieval-augmented generation (RAG).

  1. look      the AI lists the foods it can see, with a generic name and a portion (its only job)
  2. retrieve  each food is matched to a USDA FoodData Central record by full-text search
  3. compute   nutrients come from the matched records; allergens, diet checks, score, summary and
               swaps are calculated by rules (insights.py), so they are instant and repeatable

Analyses run as background jobs so the user can keep using the app while the AI looks.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from . import ai, foods, gemini, insights, local
from .config import provider
from .knowledge import ALLERGENS
from .nutrition import daily_targets, evaluate
from .schemas import DetectedItem, ItemInput, Nutrients, Profile

log = logging.getLogger("nutrilens.analysis")


# ---------------------------------------------------------------------------
# Step 1: the AI looks
# ---------------------------------------------------------------------------


# Length limits become part of the JSON grammar the local model must follow, so it can't ramble or repeat itself
# for minutes (which is what made some scans take several minutes).
class SeenItem(BaseModel):
    name: str = Field(max_length=60)
    generic_name: str = Field(max_length=60)
    portion_description: str = Field(max_length=40)
    estimated_grams: float
    confidence: float


class Perception(BaseModel):
    is_food: bool
    dish_name: str = Field(max_length=60)
    cuisine: str = Field(max_length=30)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "dessert", "drink"]
    servings: int = Field(default=1, ge=1, le=20)
    items: list[SeenItem] = Field(max_length=12)


LOOK_SYSTEM = """You identify food in photos for a nutrition app.
List every distinct food and drink that is clearly visible in the photo. Look carefully at colours, shapes and textures.
Only list things you can actually see. Never add foods that are not in the photo.
For each item give:
- name: a short specific name, e.g. "Prosciutto slices", "Brie wedge", "Tangerines"
- generic_name: the plain food a nutrition database would list, e.g. "ham", "brie cheese", "tangerine", "french bread"
- portion_description: the amount in everyday words with a number, e.g. "3 slices", "1 cup", "2 fruits"
- estimated_grams: estimated weight of the amount shown in the photo
servings: how many people the food shown would feed. 1 for a single plate or bowl; more for a shared platter,
board, buffet, family-style table or several plates.
- confidence: 0 to 1
Ignore plates, cutlery, glasses of water, decorations, and any text or labels drawn on the image.
dish_name: a short name for the whole meal. cuisine: the closest cuisine, or "Mixed" if unclear.
If there is no food or drink in the photo, set is_food to false and return no items."""


async def look(image: bytes, media_type: str) -> Perception:
    b64 = base64.standard_b64encode(image).decode("ascii")
    if provider() == "local":
        return await local.structured(LOOK_SYSTEM, "What foods are in this photo?", Perception, b64, max_tokens=900)
    if provider() == "gemini":
        return await gemini.structured(LOOK_SYSTEM, "What foods are in this photo?", Perception, b64, media_type, 900)
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
        {"type": "text", "text": "What foods are in this photo?"},
    ]
    return await ai.structured_claude(LOOK_SYSTEM, content, Perception)


# ---------------------------------------------------------------------------
# Steps 2 and 3: retrieve and compute
# ---------------------------------------------------------------------------


def _match_item(seen: SeenItem) -> DetectedItem:
    candidates = foods.search(seen.generic_name, limit=6) or foods.search(seen.name, limit=6)
    if not candidates:
        return DetectedItem(
            name=seen.name, portion_description=seen.portion_description,
            estimated_grams=max(0.0, seen.estimated_grams), confidence=min(max(seen.confidence, 0.0), 1.0),
            ingredients=[], allergens=insights.detect_allergens(seen.name),
            per_100g=Nutrients(**{k: 0.0 for k in Nutrients.model_fields}), match=None, alternatives=[],
        )
    best = candidates[0]
    grams = foods.portion_grams(best["fdc_id"], seen.portion_description) or seen.estimated_grams
    allergens = insights.detect_allergens(seen.name, best["description"], best.get("ingredients"))
    return DetectedItem(
        name=seen.name, portion_description=seen.portion_description,
        estimated_grams=max(0.0, float(grams)), confidence=min(max(seen.confidence, 0.0), 1.0),
        ingredients=[], allergens=[a for a in allergens if a in ALLERGENS],
        per_100g=Nutrients(**best["per_100g"]),
        match={k: best[k] for k in ("fdc_id", "description", "source")},
        alternatives=[{k: c[k] for k in ("fdc_id", "description", "source")} for c in candidates[1:]],
    )


def build_result(seen: Perception, profile: Profile) -> dict:
    if not seen.is_food or not seen.items:
        return {
            "analysis": {"is_food": False, "dish_name": "", "cuisine": "", "meal_type": "snack", "items": [],
                         "health_summary": "No food or drink was found in this photo. Try a clearer, closer photo of your meal."},
            "evaluation": None,
        }
    share, note = _one_serving(seen)
    items = [_match_item(s) for s in seen.items]
    result = describe(seen.dish_name, seen.cuisine, seen.meal_type, items, profile)
    if note:
        result["analysis"]["serving_note"] = note
    return result


# A single person rarely eats more than this; above it the photo is almost certainly a shared spread.
MAX_ITEM_GRAMS = 450
MAX_MEAL_GRAMS = 1000


def _one_serving(seen: Perception) -> tuple[int, str]:
    """Scale a shared spread down to one person's share, so a party board isn't logged as 5,000 kcal."""
    total = sum(max(s.estimated_grams, 0) for s in seen.items)
    share = max(seen.servings, 1)
    if total / share > MAX_MEAL_GRAMS:
        share = total / MAX_MEAL_GRAMS
    for s in seen.items:
        s.estimated_grams = round(min(max(s.estimated_grams, 0) / share, MAX_ITEM_GRAMS))
    if share <= 1.05:
        return 1, ""
    people = max(2, round(share))
    return people, (f"This looks like a shared spread for about {people} people, so the numbers show one person's share. "
                    "Adjust the portions below to match what you ate.")


def describe(dish_name: str, cuisine: str, meal_type: str, items: list[DetectedItem | ItemInput], profile: Profile) -> dict:
    """Everything the results screen shows, computed from the (possibly user-corrected) items."""
    inputs = []
    for i in items:
        item = ItemInput(**i.model_dump())
        if item.match:  # the user may have picked a different food: allergens follow the match
            food = foods.get(item.match.fdc_id)
            found = insights.detect_allergens(item.name, item.match.description, food and food.get("ingredients"))
            item.allergens = [a for a in found if a in ALLERGENS]
        inputs.append(item)
    items = inputs
    evaluation = evaluate(inputs, profile, "meal")
    texts = [t for i in items for t in (i.name, i.match.description if i.match else "")]
    totals = evaluation["totals"]
    meal_kcal = daily_targets(profile)["calories"] / 3
    found = {a["key"] for a in evaluation["allergens"]}
    analysis = {
        "is_food": True,
        "dish_name": dish_name,
        "cuisine": cuisine,
        "cuisine_confidence": 0.7,
        "meal_type": meal_type,
        "items": [i.model_dump() for i in items],
        "hidden_allergen_warnings": insights.hidden_warnings(texts, found),
        "diet_compatibility": insights.diet_checks(profile.diets, texts, totals),
        "health_score": insights.score_meal(totals, texts, meal_kcal),
        "health_summary": insights.summarize(totals, evaluation["nutrients"], texts),
        "healthier_swaps": insights.swaps(totals, texts, profile.diets),
        "data_source": "USDA FoodData Central",
    }
    return {"analysis": analysis, "evaluation": evaluation}


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_JOB_TTL_SECONDS = 3600


def start_job(image: bytes, media_type: str, profile: Profile) -> str:
    now = time.time()
    for job_id in [j for j, v in _jobs.items() if now - v["created"] > _JOB_TTL_SECONDS]:
        _jobs.pop(job_id, None)
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"id": job_id, "status": "looking", "created": now, "result": None, "error": None, "items_seen": []}
    asyncio.create_task(_run(job_id, image, media_type, profile))
    return job_id


async def _run(job_id: str, image: bytes, media_type: str, profile: Profile) -> None:
    job = _jobs[job_id]
    try:
        seen = await look(image, media_type)
        job["items_seen"] = [s.name for s in seen.items]
        job["status"] = "matching"
        result = await asyncio.to_thread(build_result, seen, profile)
        job["result"] = {"sample": False, **result}
        job["status"] = "done"
    except (ai.AIError, local.LocalAIError) as e:
        job.update(status="error", error={"detail": e.message, "code": e.code})
    except Exception:  # noqa: BLE001 - report any failure to the waiting user instead of hanging
        log.exception("Analysis job %s failed", job_id)
        job.update(status="error", error={"detail": "Something went wrong while analysing this photo. Please try again.",
                                          "code": "ai_error"})
    job["finished"] = time.time()


def job_status(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    if job is None:
        return None
    end = job.get("finished", time.time())
    return {
        "id": job_id,
        "status": job["status"],
        "elapsed": round(end - job["created"]),
        "items_seen": job["items_seen"],
        "result": job["result"],
        "error": job["error"],
    }
