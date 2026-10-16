"""On-device AI through Ollama (https://ollama.com): free, private and offline.

Used only for the "look" step of photo analysis (see analysis.py); everything else comes from data.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

from .config import local_device, local_model, settings

log = logging.getLogger("nutrilens.local")

T = TypeVar("T", bound=BaseModel)

# When the GPU runs out of memory (e.g. a game is using it), run on the CPU for a while instead.
_GPU_COOLDOWN_SECONDS = 15 * 60
_gpu_failed_at = 0.0


class LocalAIError(Exception):
    def __init__(self, message: str, status: int = 502, code: str = "ai_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


# What customers see when the AI service can't be reached; the technical reason goes to the server log.
UNAVAILABLE = "Photo analysis isn't available right now. Please try again in a minute."


def _ollama_exe() -> str | None:
    """The Ollama desktop app (which runs the AI service) or its command-line server."""
    app = Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
    if app.is_file():
        return str(app)
    return shutil.which("ollama")


async def _reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as http:
            return (await http.get(f"{settings.ollama_host}/api/version")).status_code == 200
    except httpx.HTTPError:
        return False


_start_lock = asyncio.Lock()
# One request at a time: two scans loading the model together on an 8 GB GPU make both fail or crawl.
_busy = asyncio.Semaphore(1)
# Keep the model loaded between scans so only the first one pays the ~1 minute load.
KEEP_ALIVE = "30m"


def _options(max_tokens: int) -> dict:
    options = {
        "temperature": 0.1,
        # 4096 tokens fits the task; a larger context can fail to load on an 8 GB laptop GPU that is also running a game.
        "num_ctx": 4096,
        "num_predict": max_tokens,
        "repeat_penalty": 1.1,
        # Gemma 4 bundles a speculative "draft" model; in Ollama 0.40.2-0.40.3 it crashes the load on a busy GPU
        # (ollama/ollama#18898), and it only saves time when there is spare GPU memory anyway.
        "draft_num_predict": 0,
    }
    if _use_cpu():
        options["num_gpu"] = 0
    return options


async def warm_up() -> None:
    """Start the AI service and load the model in the background, so the first scan doesn't wait for it."""
    if not await ensure_running():
        return
    body = {"model": local_model(), "stream": False, "think": False, "keep_alive": KEEP_ALIVE,
            "messages": [{"role": "user", "content": "Reply OK"}], "options": _options(2)}
    started = time.monotonic()
    async with _busy:
        try:
            async with httpx.AsyncClient(timeout=600) as http:
                r = await http.post(f"{settings.ollama_host}/api/chat", json=body)
            log.info("AI model warmed up in %.0f s (HTTP %d)", time.monotonic() - started, r.status_code)
        except httpx.HTTPError as e:
            log.warning("AI warm-up failed: %r", e)


async def ensure_running(wait_seconds: int = 45) -> bool:
    """Start the AI service on this computer if it isn't running (e.g. after a restart). True once it answers."""
    if await _reachable():
        return True
    if urlparse(settings.ollama_host).hostname not in {"localhost", "127.0.0.1", "::1"}:
        return False  # a remote service can't be started from here
    async with _start_lock:
        if await _reachable():
            return True
        exe = _ollama_exe()
        if not exe:
            log.error("Ollama isn't running and isn't installed (looked for the app and the ollama command)")
            return False
        args = [exe] if exe.endswith("ollama app.exe") else [exe, "serve"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        log.warning("Ollama wasn't running; starting %s", args[0])
        subprocess.Popen(args, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(wait_seconds):
            await asyncio.sleep(1)
            if await _reachable():
                log.info("Ollama is running")
                return True
        log.error("Started Ollama but it didn't answer within %d s", wait_seconds)
        return False


def _use_cpu() -> bool:
    return local_device() == "cpu" or time.monotonic() - _gpu_failed_at < _GPU_COOLDOWN_SECONDS


async def vision_models() -> dict:
    """Ollama status and the installed models that can read images."""
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            tags = (await http.get(f"{settings.ollama_host}/api/tags")).json().get("models", [])
            models = []
            for m in tags:
                info = (await http.post(f"{settings.ollama_host}/api/show", json={"model": m["name"]})).json()
                if "vision" in info.get("capabilities", []):
                    models.append({"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)})
    except (httpx.HTTPError, ValueError):
        return {"running": False, "models": []}
    return {"running": True, "models": models}


# Shown when another app (usually a game) leaves the AI too little of the graphics card to answer in time.
TOO_SLOW = ("Photo analysis is very slow right now because another app, such as a game, is using your graphics card. "
            "Close or pause it, then try again.")


async def structured(system: str, text: str, output: type[T], image_b64: str | None = None,
                     max_tokens: int = 1200, deadline: float = 120) -> T:
    """One call constrained to `output`'s JSON schema.

    Retries once on an unreadable answer, and once on the CPU if the GPU runs out of memory.
    """
    global _gpu_failed_at
    message = {"role": "user", "content": f"{text}\n\nReply with JSON only."}
    if image_b64:
        message["images"] = [image_b64]
    body = {
        "model": local_model(),
        "stream": False,
        "think": False,  # measured: thinking tripled the time without improving what the model saw
        "format": output.model_json_schema(),
        "keep_alive": KEEP_ALIVE,
        "messages": [{"role": "system", "content": system}, message],
    }
    for attempt in range(2):  # a second try only when the first answer was unreadable
        body["options"] = _options(max_tokens)
        try:
            # Past the deadline the request is dropped, which also stops Ollama working on it.
            async with _busy, httpx.AsyncClient(timeout=httpx.Timeout(deadline, connect=10)) as http:
                started = time.monotonic()
                r = await http.post(f"{settings.ollama_host}/api/chat", json=body)
                log.info("AI answered in %.0f s on the %s", time.monotonic() - started, "CPU" if _use_cpu() else "GPU")
        except httpx.ConnectError as e:
            if attempt == 0 and await ensure_running():
                continue  # it was stopped (e.g. after a restart) and is running again now
            log.error("Can't reach Ollama at %s", settings.ollama_host)
            raise LocalAIError(UNAVAILABLE, 503, "local_offline") from e
        except httpx.TimeoutException as e:
            log.warning("Ollama didn't answer within %d s (the GPU is probably busy with another app)", deadline)
            raise LocalAIError(TOO_SLOW, 504, "local_slow") from e
        if r.status_code == 404:
            log.error("The model %s isn't installed in Ollama (run: ollama pull %s)", local_model(), local_model())
            raise LocalAIError(UNAVAILABLE, 503, "local_model_missing")
        if r.status_code != 200:
            if "terminated" in r.text or "memory" in r.text.lower():
                if not _use_cpu():
                    log.warning("GPU couldn't load the model; switching to CPU for %d minutes", _GPU_COOLDOWN_SECONDS // 60)
                    _gpu_failed_at = time.monotonic()
                    continue
                log.error("Ollama ran out of memory on the CPU too: %s", r.text[:300])
                raise LocalAIError("Photo analysis is busy right now. Please try again in a minute.",
                                   503, "local_out_of_memory")
            raise LocalAIError("The AI couldn't look at this photo. Please try again.", 502)
        data = r.json()
        try:
            return output.model_validate_json(data["message"]["content"])
        except (ValidationError, KeyError, ValueError):
            log.warning("Local model returned invalid JSON (attempt %d, done_reason=%s, %s tokens)",
                        attempt + 1, data.get("done_reason"), data.get("eval_count"))
            if data.get("done_reason") == "length":
                max_tokens = min(max_tokens * 2, 1800)  # cut off: a little more room, never minutes of output
    raise LocalAIError("The AI gave an answer NutriLens couldn't read. Please try again.", 502)
