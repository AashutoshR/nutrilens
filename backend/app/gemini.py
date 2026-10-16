"""Google Gemini (https://ai.google.dev) for hosted deployments: fast, with a free tier.

Used for the same narrow jobs as the local model: listing the foods in a photo and completing recipe
measurements. Nutrition still comes from the USDA data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import gemini_key, gemini_model
from .local import LocalAIError

log = logging.getLogger("nutrilens.gemini")

T = TypeVar("T", bound=BaseModel)

API = "https://generativelanguage.googleapis.com/v1beta/models"
UNAVAILABLE = "Photo analysis isn't available right now. Please try again in a minute."
BUSY = "Lots of people are scanning right now. Please try again in a minute."


def _inline_refs(schema: dict) -> dict:
    """Pydantic puts nested models in $defs; inline them so the schema stands on its own."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "title", "default")}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


async def structured(system: str, text: str, output: type[T], image_b64: str | None = None,
                     media_type: str = "image/jpeg", max_tokens: int = 1200) -> T:
    """One call whose answer must match `output`'s JSON schema."""
    key = gemini_key()
    if not key:
        log.error("GEMINI_API_KEY isn't set")
        raise LocalAIError(UNAVAILABLE, 503, "gemini_no_key")
    schema = _inline_refs(output.model_json_schema())
    parts = [{"inline_data": {"mime_type": media_type, "data": image_b64}}] if image_b64 else []
    parts.append({"text": text})
    config = {"responseMimeType": "application/json", "responseJsonSchema": schema,
              "temperature": 0.1, "maxOutputTokens": max_tokens}
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}], "generationConfig": config}

    for attempt in range(3):
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=90) as http:
                r = await http.post(f"{API}/{gemini_model()}:generateContent", json=body,
                                    headers={"x-goog-api-key": key})
        except httpx.TimeoutException as e:
            raise LocalAIError("The AI took too long to look at this photo. Please try again.", 504) from e
        except httpx.HTTPError as e:
            log.error("Can't reach Gemini: %r", e)
            raise LocalAIError(UNAVAILABLE, 503, "gemini_offline") from e

        if r.status_code == 400 and "responseJsonSchema" in config and attempt == 0:
            # Older models only take the schema in the prompt: ask for JSON and describe the shape instead.
            log.warning("Gemini rejected the JSON schema (%s); retrying with the schema in the prompt", r.text[:300])
            config.pop("responseJsonSchema")
            parts[-1] = {"text": f"{text}\n\nReply with JSON matching this schema:\n{json.dumps(schema)}"}
            continue
        if r.status_code == 429:
            log.warning("Gemini rate limit: %s", r.text[:300])
            raise LocalAIError(BUSY, 503, "gemini_rate_limited")
        if r.status_code in (401, 403):
            log.error("Gemini refused the API key: %s", r.text[:300])
            raise LocalAIError(UNAVAILABLE, 503, "gemini_bad_key")
        if r.status_code != 200:
            log.error("Gemini error %d: %s", r.status_code, r.text[:500])
            if r.status_code >= 500 and attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))  # "high demand" spells are usually brief
                continue
            raise LocalAIError("The AI couldn't look at this photo. Please try again.", 502)

        data = r.json()
        log.info("Gemini answered in %.1f s", time.monotonic() - started)
        try:
            candidate = data["candidates"][0]
            answer = "".join(p.get("text", "") for p in candidate["content"]["parts"])
            return output.model_validate_json(answer)
        except (KeyError, IndexError, ValidationError, ValueError):
            log.warning("Gemini returned an unreadable answer (attempt %d): %s", attempt + 1, str(data)[:500])
    raise LocalAIError("The AI gave an answer NutriLens couldn't read. Please try again.", 502)
