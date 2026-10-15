"""Runtime settings, read from environment variables (or backend/.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Settings:
    model: str
    effort: str
    ollama_host: str
    db_path: Path
    max_image_bytes: int
    cors_origins: list[str]


settings = Settings(
    model=os.getenv("NUTRILENS_MODEL", "claude-opus-5-5"),
    effort=os.getenv("NUTRILENS_EFFORT", "medium"),
    ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
    db_path=Path(os.getenv("NUTRILENS_DB", BACKEND_DIR / "nutrilens.db")),
    # The Claude API accepts base64 images up to 5 MB; the frontend downsizes before upload.
    max_image_bytes=5 * 1024 * 1024,
    cors_origins=os.getenv("NUTRILENS_CORS", "http://localhost:5173").split(","),
)


def provider() -> str:
    """Which AI looks at photos: "claude" (Anthropic API), "gemini" (Google, for hosting) or "local" (Ollama)."""
    chosen = os.getenv("NUTRILENS_PROVIDER", "claude").lower()
    return chosen if chosen in ("local", "gemini") else "claude"


def gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def public_mode() -> bool:
    """Hosted for anyone to use: each visitor gets private data and the admin settings are switched off."""
    return os.getenv("NUTRILENS_PUBLIC", "").lower() in ("1", "true", "yes")


def local_model() -> str:
    return os.getenv("NUTRILENS_LOCAL_MODEL", "gemma4:e4b")


def claude_credentials() -> bool:
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return True
    # Profile created by `ant auth login`, which the SDK also reads.
    return (Path.home() / ".config" / "anthropic").exists()


def local_device() -> str:
    """Where the local model runs: "gpu" (fast) or "cpu" (slower, but leaves the graphics card free for games)."""
    return "cpu" if os.getenv("NUTRILENS_LOCAL_DEVICE", "gpu").lower() == "cpu" else "gpu"


def ai_connected() -> bool:
    """Checked live, so a newly chosen AI takes effect at once. A local model's reachability is checked per call."""
    if provider() == "gemini":
        return bool(gemini_key())
    return provider() == "local" or claude_credentials()


def active_model() -> str:
    return {"local": local_model(), "gemini": gemini_model()}.get(provider(), settings.model)


def set_env(name: str, value: str | None) -> None:
    """Persist (or remove, with None) a setting in backend/.env and the running process."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.strip().startswith(f"{name}=")]
    if value:
        lines.insert(0, f"{name}={value}")
        os.environ[name] = value
    else:
        os.environ.pop(name, None)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
