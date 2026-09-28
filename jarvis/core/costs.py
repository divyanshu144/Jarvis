"""Best-effort model usage and cost monitoring for JARVIS."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger
from jarvis.core.tracing import sanitize_value

log = get_logger(__name__)

_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_COST_PATH = _ROOT / "jarvis" / "data" / "model_costs.json"
_LOCAL_PROVIDERS = {"ollama", "local"}
_LOCAL_MODEL_PREFIXES = ("qwen", "llama", "mistral", "phi", "gemma")


@dataclass(frozen=True)
class UsageTotals:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    usage_source: str = "sdk_usage"


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else cfg.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_usage (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id          TEXT,
            provider            TEXT NOT NULL,
            model               TEXT NOT NULL,
            input_tokens        INTEGER NOT NULL,
            output_tokens       INTEGER NOT NULL,
            total_tokens        INTEGER NOT NULL,
            estimated_cost_usd  REAL NOT NULL,
            pricing_source      TEXT NOT NULL,
            source              TEXT NOT NULL,
            usage_source        TEXT NOT NULL DEFAULT 'estimated_chars',
            created_at          REAL NOT NULL
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(model_usage)")}
    if "usage_source" not in columns:
        conn.execute(
            "ALTER TABLE model_usage "
            "ADD COLUMN usage_source TEXT NOT NULL DEFAULT 'estimated_chars'"
        )
    conn.commit()


def init_cost_monitoring(db_path: str | Path | None = None) -> None:
    """Create cost monitoring tables. Safe to call repeatedly."""
    try:
        conn = _connect(db_path)
        conn.close()
    except Exception as exc:
        log.debug(f"Cost monitoring init failed: {exc}")


def estimate_tokens(text: str | None) -> int:
    """Cheap fallback token estimate for local monitoring."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _token_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer():
        return int(value) if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def extract_sdk_usage(response: Any, provider: str | None = None) -> UsageTotals | None:
    """Extract exact token usage from Anthropic or OpenAI-compatible responses."""
    usage = _field(response, "usage")
    if usage is None:
        return None

    input_tokens = _token_int(_field(usage, "input_tokens"))
    output_tokens = _token_int(_field(usage, "output_tokens"))

    if input_tokens is None or output_tokens is None:
        input_tokens = _token_int(_field(usage, "prompt_tokens"))
        output_tokens = _token_int(_field(usage, "completion_tokens"))

    if input_tokens is None or output_tokens is None:
        return None

    return UsageTotals(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        usage_source="sdk_usage",
    )


def infer_provider(tier: int | None, model: str | None) -> str:
    """Infer provider from current tier/model naming without changing routing."""
    model_l = (model or "").lower()
    if tier == 1 or model_l.startswith(_LOCAL_MODEL_PREFIXES):
        return "ollama"
    if "claude" in model_l:
        return "anthropic"
    if "llama-4" in model_l or "groq" in model_l or "meta-llama" in model_l:
        return "groq"
    if tier == 2:
        return "groq"
    if tier == 3:
        return "anthropic"
    return "unknown"


def load_model_costs(cost_path: str | Path | None = None) -> dict[str, Any]:
    """Load user-editable model pricing metadata."""
    path = Path(cost_path) if cost_path else _DEFAULT_COST_PATH
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.debug(f"Cost pricing load failed: {exc}")
        return {}


def _pricing_entry(provider: str, model: str, costs: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    providers = costs.get("providers", {}) if isinstance(costs, dict) else {}
    provider_block = providers.get(provider, {}) if isinstance(providers, dict) else {}
    models = provider_block.get("models", {}) if isinstance(provider_block, dict) else {}
    if isinstance(models, dict):
        if model in models and isinstance(models[model], dict):
            return models[model], f"model_costs:{provider}:{model}"
        for key, value in models.items():
            if key and key in model and isinstance(value, dict):
                return value, f"model_costs:{provider}:{key}"
    if provider in _LOCAL_PROVIDERS:
        return {"input_per_million": 0.0, "output_per_million": 0.0}, "local_zero_cost"
    return None, "missing_price"


def estimate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_path: str | Path | None = None,
) -> tuple[float, str]:
    """Estimate request cost from configurable per-million token prices."""
    costs = load_model_costs(cost_path)
    entry, source = _pricing_entry(provider, model, costs)
    if not entry:
        return 0.0, source
    input_rate = float(entry.get("input_per_million", 0.0) or 0.0)
    output_rate = float(entry.get("output_per_million", 0.0) or 0.0)
    cost = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
    return round(cost, 8), source


def record_model_usage(
    request_id: str | None,
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    source: str = "estimated",
    usage_source: str = "estimated_chars",
    db_path: str | Path | None = None,
    cost_path: str | Path | None = None,
) -> None:
    """Persist model usage. Failures are isolated from assistant behavior."""
    try:
        provider = str(sanitize_value(provider or "unknown", limit=100))
        model = str(sanitize_value(model or "unknown", limit=200))
        input_tokens = max(0, int(input_tokens or 0))
        output_tokens = max(0, int(output_tokens or 0))
        total_tokens = input_tokens + output_tokens
        cost, pricing_source = estimate_cost_usd(provider, model, input_tokens, output_tokens, cost_path)
        conn = _connect(db_path)
        conn.execute(
            """
            INSERT INTO model_usage(
                request_id, provider, model, input_tokens, output_tokens,
                total_tokens, estimated_cost_usd, pricing_source, source, usage_source, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                request_id,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                cost,
                pricing_source,
                str(sanitize_value(source, limit=100)),
                str(sanitize_value(usage_source, limit=100)),
                time.time(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug(f"Cost monitoring record_model_usage failed: {exc}")


def record_chat_usage(
    request_id: str | None,
    *,
    tier: int | None,
    model: str | None,
    user_message: str,
    final_answer: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    usage_source: str | None = None,
    db_path: str | Path | None = None,
    cost_path: str | Path | None = None,
) -> None:
    """Record one usage row for a completed Agent.chat request."""
    provider = infer_provider(tier, model)
    exact_input = _token_int(input_tokens)
    exact_output = _token_int(output_tokens)
    if exact_input is not None and exact_output is not None and usage_source == "sdk_usage":
        chosen_input = exact_input
        chosen_output = exact_output
        chosen_usage_source = "sdk_usage"
    else:
        chosen_input = estimate_tokens(user_message)
        chosen_output = estimate_tokens(final_answer)
        chosen_usage_source = "estimated_chars"

    record_model_usage(
        request_id,
        provider=provider,
        model=model or "unknown",
        input_tokens=chosen_input,
        output_tokens=chosen_output,
        source="agent_chat",
        usage_source=chosen_usage_source,
        db_path=db_path,
        cost_path=cost_path,
    )


def get_cost_summary(days: int = 7, db_path: str | Path | None = None) -> dict[str, Any]:
    """Return aggregate cost and token usage for recent model calls."""
    try:
        conn = _connect(db_path)
        cutoff = time.time() - max(0, days) * 86400
        rows = conn.execute(
            """
            SELECT provider, model, COUNT(*) AS calls,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(total_tokens) AS total_tokens,
                   SUM(estimated_cost_usd) AS estimated_cost_usd
            FROM model_usage
            WHERE created_at >= ?
            GROUP BY provider, model
            ORDER BY estimated_cost_usd DESC, total_tokens DESC
            """,
            (cutoff,),
        ).fetchall()
        totals = conn.execute(
            """
            SELECT COUNT(*) AS calls,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
            FROM model_usage
            WHERE created_at >= ?
            """,
            (cutoff,),
        ).fetchone()
        conn.close()
        return {
            "days": days,
            "calls": int(totals["calls"] or 0),
            "total_tokens": int(totals["total_tokens"] or 0),
            "estimated_cost_usd": round(float(totals["estimated_cost_usd"] or 0.0), 8),
            "by_model": [
                {
                    "provider": row["provider"],
                    "model": row["model"],
                    "calls": int(row["calls"] or 0),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "total_tokens": int(row["total_tokens"] or 0),
                    "estimated_cost_usd": round(float(row["estimated_cost_usd"] or 0.0), 8),
                }
                for row in rows
            ],
        }
    except Exception as exc:
        log.debug(f"Cost monitoring get_cost_summary failed: {exc}")
        return {"days": days, "calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "by_model": []}
