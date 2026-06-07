"""Best-effort observability tracing for JARVIS agent and tool runs."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)

_MAX_TEXT = 2000
_MAX_RESULT = 1500
_REDACTED = "[REDACTED]"
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|password|authorization|cookie|session|client[_-]?secret|access[_-]?token|refresh[_-]?token)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(sk-ant-api\w*[-_A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{8,})",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b((?:OPENAI|ANTHROPIC|GROQ|GEMINI|ELEVENLABS|TAVILY|PICOVOICE)_API_KEY|"
    r"api[_ -]?key|x-api-key|password|secret|token|authorization|cookie|session|"
    r"client[_ -]?secret|access[_ -]?token|refresh[_ -]?token)"
    r"(\s*(?:=|:|is)\s*)([^\s,;]+)",
    re.IGNORECASE,
)
_COOKIE_PAIR_RE = re.compile(
    r"\b((?:session|sid|csrf|xsrf|auth|jwt)[-_]?(?:id|token)?)(=)([^\s,;]+)",
    re.IGNORECASE,
)
_SENSITIVE_TOOLS = {
    "gmail",
    "google_calendar",
    "calendar",
    "screen_vision",
    "screenshot",
    "browser_control",
    "file_manager",
    "clipboard",
    "shell_exec",
    "code_exec",
    "system_control",
    "spotlight",
}


def new_request_id() -> str:
    """Return a short unique id for one user request."""
    return uuid.uuid4().hex


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else cfg.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id      TEXT NOT NULL UNIQUE,
            user_message    TEXT,
            route           TEXT,
            intent          TEXT,
            chosen_tier     INTEGER,
            chosen_model    TEXT,
            tools_requested TEXT,
            tools_executed  TEXT,
            safety_blocks   TEXT,
            fallback_path   TEXT,
            final_answer    TEXT,
            error           TEXT,
            latency_ms      REAL,
            created_at      REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id      TEXT,
            tool_name       TEXT NOT NULL,
            tool_args_json  TEXT,
            status          TEXT NOT NULL,
            result_summary  TEXT,
            error           TEXT,
            latency_ms      REAL,
            created_at      REAL NOT NULL
        );
        """
    )
    conn.commit()


def init_tracing(db_path: str | Path | None = None) -> None:
    """Create tracing tables. Safe to call repeatedly."""
    try:
        conn = _connect(db_path)
        conn.close()
    except Exception as exc:
        log.debug(f"Tracing init failed: {exc}")


def _truncate(value: str, limit: int = _MAX_TEXT) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"...[truncated {len(value) - limit} chars]"


def _redact_text(text: str) -> str:
    text = _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", text)
    text = _COOKIE_PAIR_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", text)
    return _SECRET_VALUE_RE.sub(_REDACTED, text)


def is_sensitive_tool(tool_name: str) -> bool:
    return tool_name in _SENSITIVE_TOOLS


def _sensitive_tool_summary(tool_name: str, result: Any) -> str:
    text = str(result or "")
    size = len(text)
    lowered = tool_name.lower()
    if lowered == "gmail":
        count = len(re.findall(r"(?:^|\n)\s*(?:[-*•]|\d+\.|Email ID:|From:)", text))
        detail = f" returned {count} item{'s' if count != 1 else ''}" if count else " completed"
        return f"Gmail tool{detail}; content redacted for privacy. Output length: {size} chars."
    if lowered in {"google_calendar", "calendar"}:
        count = len(re.findall(r"(?:^|\n)\s*(?:[-*•]|\d+\.|Event ID:)", text))
        detail = f" returned {count} item{'s' if count != 1 else ''}" if count else " completed"
        return f"Calendar tool{detail}; content redacted for privacy. Output length: {size} chars."
    if lowered in {"screen_vision", "screenshot"}:
        return f"Screen output redacted for privacy. Output length: {size} chars."
    if lowered == "browser_control":
        return f"Browser output redacted for privacy. Output length: {size} chars."
    if lowered == "file_manager":
        return f"File tool output redacted for privacy. Output length: {size} chars."
    if lowered == "clipboard":
        return f"Clipboard output redacted for privacy. Output length: {size} chars."
    if lowered in {"shell_exec", "code_exec"}:
        return f"Execution output redacted for privacy. Output length: {size} chars."
    if lowered == "system_control":
        return f"System control output redacted for privacy. Output length: {size} chars."
    if lowered == "spotlight":
        return f"File search output redacted for privacy. Output length: {size} chars."
    return f"Sensitive tool output redacted for privacy. Output length: {size} chars."


def sanitize_value(value: Any, limit: int = _MAX_TEXT) -> Any:
    """Redact obvious secrets and truncate strings recursively."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _SECRET_KEY_RE.search(key_s):
                clean[key_s] = _REDACTED
            else:
                clean[key_s] = sanitize_value(item, limit=limit)
        return clean
    if isinstance(value, list):
        return [sanitize_value(item, limit=limit) for item in value[:50]]
    if isinstance(value, tuple):
        return [sanitize_value(item, limit=limit) for item in list(value)[:50]]
    if isinstance(value, str):
        return _truncate(_redact_text(value), limit)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _truncate(_redact_text(str(value)), limit)


def _json(value: Any, limit: int = _MAX_TEXT) -> str:
    try:
        return json.dumps(sanitize_value(value, limit=limit), ensure_ascii=False, sort_keys=True)
    except Exception:
        return json.dumps(str(sanitize_value(str(value), limit=limit)))


def summarize_tool_result(tool_name: str, result: Any) -> str:
    """Return a safe one-field summary of a tool result."""
    if is_sensitive_tool(tool_name):
        return _sensitive_tool_summary(tool_name, result)
    return str(sanitize_value(str(result), limit=_MAX_RESULT))


def start_agent_run(request_id: str, user_message: str, db_path: str | Path | None = None) -> None:
    try:
        conn = _connect(db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_runs(
                request_id, user_message, tools_requested, tools_executed,
                safety_blocks, created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                request_id,
                sanitize_value(user_message),
                "[]",
                "[]",
                "[]",
                time.time(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug(f"Tracing start_agent_run failed: {exc}")


def finish_agent_run(
    request_id: str,
    *,
    route: str | None = None,
    intent: str | None = None,
    chosen_tier: int | None = None,
    chosen_model: str | None = None,
    tools_requested: Any = None,
    tools_executed: Any = None,
    safety_blocks: Any = None,
    fallback_path: str | None = None,
    final_answer: str | None = None,
    error: str | None = None,
    latency_ms: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    try:
        conn = _connect(db_path)
        conn.execute(
            """
            UPDATE agent_runs
            SET route=?, intent=?, chosen_tier=?, chosen_model=?,
                tools_requested=?, tools_executed=?, safety_blocks=?,
                fallback_path=?, final_answer=?, error=?, latency_ms=?
            WHERE request_id=?
            """,
            (
                sanitize_value(route or ""),
                sanitize_value(intent or ""),
                chosen_tier,
                sanitize_value(chosen_model or ""),
                _json(tools_requested or []),
                _json(tools_executed or []),
                _json(safety_blocks or []),
                sanitize_value(fallback_path or ""),
                sanitize_value(final_answer or ""),
                sanitize_value(error or ""),
                latency_ms,
                request_id,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug(f"Tracing finish_agent_run failed: {exc}")


def record_tool_run(
    request_id: str | None,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    *,
    status: str,
    result_summary: str = "",
    error: str = "",
    latency_ms: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    try:
        conn = _connect(db_path)
        conn.execute(
            """
            INSERT INTO tool_runs(
                request_id, tool_name, tool_args_json, status,
                result_summary, error, latency_ms, created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                request_id,
                sanitize_value(tool_name, limit=200),
                _json(tool_args or {}),
                sanitize_value(status, limit=100),
                summarize_tool_result(tool_name, result_summary),
                sanitize_value(error, limit=500),
                latency_ms,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug(f"Tracing record_tool_run failed: {exc}")


def record_safety_block(
    request_id: str | None,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    reason: str,
    *,
    db_path: str | Path | None = None,
) -> None:
    record_tool_run(
        request_id,
        tool_name,
        tool_args,
        status="safety_blocked",
        result_summary=f"Safety blocked {tool_name}: {reason}",
        error=reason,
        latency_ms=0.0,
        db_path=db_path,
    )


def prune_traces(
    days_to_keep: int = 30,
    max_rows: int | None = None,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Manually prune old trace rows. Does nothing automatically."""
    deleted = {"agent_runs": 0, "tool_runs": 0}
    try:
        conn = _connect(db_path)
        cutoff = time.time() - max(0, days_to_keep) * 86400
        for table in ("tool_runs", "agent_runs"):
            cur = conn.execute(f"DELETE FROM {table} WHERE created_at < ?", (cutoff,))
            deleted[table] += int(cur.rowcount or 0)

        if max_rows is not None and max_rows >= 0:
            for table in ("tool_runs", "agent_runs"):
                cur = conn.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE id NOT IN (
                        SELECT id FROM {table}
                        ORDER BY created_at DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (max_rows,),
                )
                deleted[table] += int(cur.rowcount or 0)

        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug(f"Tracing prune_traces failed: {exc}")
    return deleted
