"""Complete recipe ingredient amounts whose units were lost in the recipe dataset ("1/2 olive oil" → "1/2 cup olive oil").

Done once per recipe, the first time someone opens it, and cached in the app database.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from . import ai, db, gemini, local
from .config import ai_connected, provider
from .schemas import Recipe

log = logging.getLogger("nutrilens.measurements")


class MeasuredIngredients(BaseModel):
    lines: list[str]


SYSTEM = """You fix recipe ingredient lists whose measurement units were lost.
Each line has the right number but no unit, e.g. "1/2 olive oil" or "3 feta cheese".
Rewrite every line as a complete ingredient line with the most likely unit, using the method, the servings and the calories
per serving as clues, e.g. "1/2 cup olive oil", "3 oz feta cheese", "2 tsp dried oregano", "1 (6 oz) can tuna in water".
Rules:
- Keep the same order and the same numbers. Return exactly one line per ingredient. Never add or remove ingredients.
- Countable items keep no unit: "2 eggs", "1 red onion", "3 garlic cloves".
- Use common US kitchen units: cup, tbsp, tsp, oz, lb, can, package, clove, pinch, dash."""


def _prompt(recipe: Recipe) -> str:
    ingredients = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(recipe.ingredients))
    method = "\n".join(f"- {s}" for s in recipe.steps)
    return (f"Recipe: {recipe.name}\nServes: {recipe.servings}\nCalories per serving: {recipe.per_serving.calories:.0f}\n\n"
            f"Ingredients ({len(recipe.ingredients)}):\n{ingredients}\n\nMethod:\n{method}")


def cached(recipe: Recipe) -> Recipe:
    lines = db.get_measurements(recipe.id) if recipe.id else None
    if lines and len(lines) == len(recipe.ingredients):
        return recipe.model_copy(update={"ingredients": lines, "measurements_estimated": True})
    return recipe


async def complete(recipe: Recipe) -> Recipe:
    """Ask the AI for the missing units (once per recipe). Returns the recipe unchanged if that isn't possible."""
    done = cached(recipe)
    if done.measurements_estimated or not ai_connected() or not recipe.ingredients:
        return done
    try:
        if provider() == "local":
            result = await local.structured(SYSTEM, _prompt(recipe), MeasuredIngredients, max_tokens=900)
        elif provider() == "gemini":
            result = await gemini.structured(SYSTEM, _prompt(recipe), MeasuredIngredients, max_tokens=900)
        else:
            result = await ai._structured(SYSTEM, _prompt(recipe), MeasuredIngredients)
    except (ai.AIError, local.LocalAIError) as e:
        log.warning("Couldn't complete measurements for recipe %s: %s", recipe.id, e.message)
        return recipe
    lines = [line.strip() for line in result.lines if line.strip()]
    if len(lines) != len(recipe.ingredients):  # the model dropped or invented a line: don't trust it
        log.warning("Measurement lines for recipe %s didn't match (%d vs %d)", recipe.id, len(lines), len(recipe.ingredients))
        return recipe
    db.save_measurements(recipe.id, lines)
    return recipe.model_copy(update={"ingredients": lines, "measurements_estimated": True})
