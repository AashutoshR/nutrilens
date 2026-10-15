"""Claude-powered food recognition, recipe generation and meal planning."""

from __future__ import annotations

import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from . import local
from .config import provider, settings
from .knowledge import ALLERGENS, DIETS, NUTRIENTS
from .schemas import MealPlan, MealPlanRequest, Profile, RecipeList, RecipeRequest

log = logging.getLogger("nutrilens.ai")

T = TypeVar("T", bound=BaseModel)

_client: anthropic.AsyncAnthropic | None = None


class AIError(Exception):
    def __init__(self, message: str, status: int = 502, code: str = "ai_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def reset_client() -> None:
    """Drop the cached client so the next call picks up newly saved credentials."""
    global _client
    _client = None


async def verify_key(key: str) -> None:
    """Check a key with Anthropic (a free model lookup) before saving it."""
    try:
        await anthropic.AsyncAnthropic(api_key=key, max_retries=1).models.retrieve(settings.model)
    except anthropic.AuthenticationError as e:
        raise AIError("Anthropic rejected that key. Copy it again from the Claude Console and paste the whole key.", 400, "invalid_key") from e
    except (anthropic.PermissionDeniedError, anthropic.NotFoundError) as e:
        raise AIError(f"That key works, but it doesn't have access to {settings.model}.", 400, "model_unavailable") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Couldn't reach Anthropic to check the key. Check your internet connection.", 503, "offline") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Anthropic couldn't check the key right now ({e.status_code}). Please try again.", 503) from e


def describe_profile(p: Profile) -> str:
    diets = ", ".join(DIETS[d] for d in p.diets) or "none"
    allergens = ", ".join(ALLERGENS[a]["label"] for a in p.allergens) or "none"
    cuisines = ", ".join(p.cuisines) or "no preference"
    return (
        f"- Sex: {p.sex}, age: {p.age}, goal: {p.goal}, daily calorie target: {p.calorie_target} kcal\n"
        f"- Dietary restrictions: {diets}\n"
        f"- Allergens to avoid: {allergens}\n"
        f"- Favourite cuisines: {cuisines}"
    )


async def _structured(system: str, content: list[dict] | str, output: type[T]) -> T:
    """One structured call: to the free local model if chosen, otherwise to Claude."""
    if provider() == "local" and isinstance(content, str):
        return await local.structured(system, content, output)
    if provider() == "gemini" and isinstance(content, str):
        from . import gemini  # imported here: gemini imports local, which ai doesn't otherwise need
        return await gemini.structured(system, content, output)
    try:
        response = await client().beta.messages.parse(
            model=settings.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": settings.effort},
            output_format=output,
            # If a safety classifier declines, re-run on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Claude rejected your API key. Reconnect Claude with a valid key.", 401, "invalid_key") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude is rate-limiting requests. Please try again in a minute.", 429) from e
    except anthropic.BadRequestError as e:
        raise AIError(f"Claude could not process the request: {e.message}", 400) from e
    except anthropic.APIStatusError as e:
        log.error("Claude API error %s (request %s)", e.status_code, e.request_id)
        raise AIError("Claude is temporarily unavailable. Please try again.", 503) from e
    except anthropic.APIConnectionError as e:
        raise AIError("Could not reach the Claude API. Check your internet connection.", 503) from e

    if response.stop_reason == "refusal":
        raise AIError("Claude declined to analyse this request.", 422)
    if response.stop_reason == "max_tokens":
        raise AIError("The response was too long and got cut off. Try a simpler request.", 502)
    if response.parsed_output is None:
        raise AIError("Claude returned an unexpected response. Please try again.", 502)
    return response.parsed_output


async def structured_claude(system: str, content: list[dict], output: type[T]) -> T:
    """A Claude call with image content (used by the "look" step of photo analysis)."""
    return await _structured(system, content, output)


RECIPE_SYSTEM = f"""You are the recipe developer for NutriLens, a nutrition assistant app.

Write practical home-cooking recipes that strictly follow the user's dietary restrictions and never include their allergens, including hidden sources (stock cubes, sauces, ghee, fish sauce, Worcestershire sauce). Prefer authentic dishes from the requested cuisine and say so when a recipe is an adaptation.
Ingredients need quantities in metric with common measures in brackets. Keep each step to one short action and do not number them (the app numbers steps itself).
Allergens: list every allergen the recipe contains using only these keys: {", ".join(ALLERGENS)}.
Nutrition per serving should be realistic estimates based on the listed quantities."""


async def generate_recipes(req: RecipeRequest, profile: Profile) -> RecipeList:
    asks = [f"Suggest {req.count} recipes."]
    if req.cuisine:
        asks.append(f"Cuisine: {req.cuisine}.")
    elif profile.cuisines:
        asks.append("Spread them across the user's favourite cuisines where it makes sense.")
    if req.focus_nutrient:
        n = NUTRIENTS[req.focus_nutrient]
        asks.append(f"Each recipe should be a strong source of {n['label']} ({n['unit']}); "
                    f"mention in the description how it helps and any absorption tips.")
    if req.meal_type:
        asks.append(f"Meal type: {req.meal_type}.")
    if req.max_minutes:
        asks.append(f"Total time (prep + cook) at most {req.max_minutes} minutes.")
    if req.ingredients_on_hand:
        asks.append(f"Use as many of these ingredients the user already has as you sensibly can: "
                    f"{', '.join(req.ingredients_on_hand)}.")
    prompt = f"The user's profile:\n{describe_profile(profile)}\n\n" + " ".join(asks)
    return await _structured(RECIPE_SYSTEM, prompt, RecipeList)


PLAN_SYSTEM = f"""You are the meal planner for NutriLens, a nutrition assistant app.

Build varied, realistic meal plans (breakfast, lunch, dinner and one snack per day) that hit the user's calorie target within about 10%, strictly follow their dietary restrictions, and never include their allergens, including hidden sources.
Reuse ingredients across days to keep the shopping list short. Give each day a short theme.
Allergens: list each meal's allergens using only these keys: {", ".join(ALLERGENS)}.
Shopping list items should include rough quantities for the whole plan."""


async def generate_meal_plan(req: MealPlanRequest, profile: Profile) -> MealPlan:
    asks = [f"Create a {req.days}-day meal plan."]
    cuisines = req.cuisines or profile.cuisines
    if cuisines:
        asks.append(f"Draw mainly on these cuisines: {', '.join(cuisines)}.")
    if req.focus_nutrients:
        labels = ", ".join(NUTRIENTS[n]["label"] for n in req.focus_nutrients)
        asks.append(f"The user wants to boost: {labels}. Make sure every day is rich in these and use the daily tip to explain how.")
    prompt = f"The user's profile:\n{describe_profile(profile)}\n\n" + " ".join(asks)
    return await _structured(PLAN_SYSTEM, prompt, MealPlan)
