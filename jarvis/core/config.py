"""Configuration loader — reads config.yaml, falls back to environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


_ROOT = Path(__file__).parent.parent.parent


def _load_env_file() -> None:
    """Load local .env values into os.environ without overriding the shell."""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_raw() -> dict[str, Any]:
    config_path = _ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _get(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)  # type: ignore[assignment]
    return d


class Config:
    """Central config object. Access via the module-level `cfg` singleton."""

    def __init__(self) -> None:
        _load_env_file()
        self._raw = _load_raw()

    # ── API keys ──────────────────────────────────────────────────────────────

    @property
    def anthropic_key(self) -> str:
        return (
            os.getenv("ANTHROPIC_API_KEY")
            or _get(self._raw, "api_keys", "anthropic")
            or ""
        )

    @property
    def gemini_key(self) -> str:
        return (
            os.getenv("GEMINI_API_KEY")
            or _get(self._raw, "api_keys", "gemini")
            or ""
        )

    @property
    def groq_key(self) -> str:
        return (
            os.getenv("GROQ_API_KEY")
            or _get(self._raw, "api_keys", "groq")
            or ""
        )

    @property
    def elevenlabs_key(self) -> str:
        return (
            os.getenv("ELEVENLABS_API_KEY")
            or _get(self._raw, "api_keys", "elevenlabs")
            or ""
        )

    @property
    def tavily_key(self) -> str:
        return (
            os.getenv("TAVILY_API_KEY")
            or _get(self._raw, "api_keys", "tavily")
            or ""
        )

    @property
    def picovoice_key(self) -> str:
        return (
            os.getenv("PICOVOICE_ACCESS_KEY")
            or _get(self._raw, "api_keys", "picovoice")
            or ""
        )

    # ── Groq ──────────────────────────────────────────────────────────────────

    @property
    def groq_model(self) -> str:
        return _get(self._raw, "groq", "model", default="meta-llama/llama-4-scout-17b-16e-instruct")

    @property
    def groq_max_tokens(self) -> int:
        return _get(self._raw, "groq", "max_tokens", default=4096)

    # ── Routing ───────────────────────────────────────────────────────────────

    @property
    def tier1_model(self) -> str:
        return _get(self._raw, "routing", "tier1_model", default="qwen2.5:3b")

    @property
    def tier1_timeout_ms(self) -> int:
        return _get(self._raw, "routing", "tier1_timeout_ms", default=5000)

    @property
    def tier2_timeout_ms(self) -> int:
        return _get(self._raw, "routing", "tier2_timeout_ms", default=8000)

    @property
    def tier3_patterns(self) -> list[str]:
        return _get(self._raw, "routing", "tier3_patterns", default=[
            "screenshot", "look at my screen", "what do you see", "vision",
        ])

    @property
    def auto_escalate(self) -> bool:
        return _get(self._raw, "routing", "auto_escalate", default=True)

    # ── Claude ────────────────────────────────────────────────────────────────

    @property
    def claude_model(self) -> str:
        return _get(self._raw, "claude", "model", default="claude-sonnet-4-20250514")

    @property
    def claude_max_tokens(self) -> int:
        return _get(self._raw, "claude", "max_tokens", default=4096)

    # ── ElevenLabs ────────────────────────────────────────────────────────────

    @property
    def el_voice_id(self) -> str:
        return _get(self._raw, "elevenlabs", "voice_id", default="JBFqnCBsd6RMkjVDRZzb")

    @property
    def el_model_id(self) -> str:
        return _get(self._raw, "elevenlabs", "model_id", default="eleven_turbo_v2_5")

    @property
    def el_stability(self) -> float:
        return _get(self._raw, "elevenlabs", "stability", default=0.5)

    @property
    def el_similarity(self) -> float:
        return _get(self._raw, "elevenlabs", "similarity_boost", default=0.75)


    # ── TTS routing ──────────────────────────────────────────────────────────────

    @property
    def tts_provider(self) -> str:
        return (
            os.getenv("JARVIS_TTS_PROVIDER")
            or _get(self._raw, "tts", "provider", default="auto")
            or "auto"
        ).lower()

    @property
    def local_tts_provider(self) -> str:
        return (
            os.getenv("LOCAL_TTS_PROVIDER")
            or _get(self._raw, "tts", "local_provider", default="auto")
            or "auto"
        ).lower()

    @property
    def piper_command(self) -> str:
        return os.getenv("PIPER_COMMAND") or _get(self._raw, "tts", "piper_command", default="piper")

    @property
    def piper_model_path(self) -> str:
        return os.getenv("PIPER_MODEL_PATH") or _get(self._raw, "tts", "piper_model_path", default="")

    @property
    def kokoro_command(self) -> str:
        return os.getenv("KOKORO_COMMAND") or _get(self._raw, "tts", "kokoro_command", default="kokoro")

    # ── Whisper ───────────────────────────────────────────────────────────────

    @property
    def whisper_model(self) -> str:
        return _get(self._raw, "whisper", "model", default="base")

    @property
    def whisper_language(self) -> str:
        return _get(self._raw, "whisper", "language", default="en")

    # ── Voice recording ───────────────────────────────────────────────────────

    @property
    def silence_threshold(self) -> int:
        return _get(self._raw, "voice", "silence_threshold", default=500)

    @property
    def silence_duration(self) -> float:
        return _get(self._raw, "voice", "silence_duration", default=1.5)

    @property
    def sample_rate(self) -> int:
        return _get(self._raw, "voice", "sample_rate", default=16000)

    # ── Memory ────────────────────────────────────────────────────────────────

    @property
    def short_term_limit(self) -> int:
        return _get(self._raw, "memory", "short_term_limit", default=20)

    @property
    def top_k_similar(self) -> int:
        return _get(self._raw, "memory", "top_k_similar", default=3)

    @property
    def db_path(self) -> Path:
        p = _get(self._raw, "memory", "db_path", default="data/jarvis.db")
        path = _ROOT / p
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def chroma_path(self) -> Path:
        p = _get(self._raw, "memory", "chroma_path", default="data/chroma")
        path = _ROOT / p
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── HUD ───────────────────────────────────────────────────────────────────

    @property
    def hud_width(self) -> int:
        return _get(self._raw, "hud", "width", default=340)

    @property
    def hud_height(self) -> int:
        return _get(self._raw, "hud", "height", default=180)

    @property
    def hud_opacity(self) -> float:
        return _get(self._raw, "hud", "opacity", default=0.92)

    @property
    def hud_accent(self) -> str:
        return _get(self._raw, "hud", "accent_color", default="#00d4ff")

    # ── User ──────────────────────────────────────────────────────────────────

    @property
    def user_name(self) -> str:
        return _get(self._raw, "user", "name", default="")

    @property
    def projects_root(self) -> Path:
        p = _get(self._raw, "projects_root", default="~/projects")
        return Path(str(p)).expanduser()

    @property
    def project_aliases(self) -> dict[str, str]:
        aliases = _get(self._raw, "project_aliases", default={})
        if not isinstance(aliases, dict):
            return {}
        return {str(key): str(value) for key, value in aliases.items()}

    def set_user_name(self, name: str) -> None:
        if "user" not in self._raw:
            self._raw["user"] = {}
        self._raw["user"]["name"] = name
        self._save()

    def _save(self) -> None:
        config_path = _ROOT / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(self._raw, f, default_flow_style=False)


cfg = Config()
