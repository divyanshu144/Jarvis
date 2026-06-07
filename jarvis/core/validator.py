"""
Tool call schema validator.
Validates tool name and parameters against the registered tool schemas
before any tool is executed. Logs all failures to SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from jarvis.core.logger import get_logger
from jarvis.tools.registry import TOOL_DEFINITIONS

log = get_logger(__name__)

# Build a lookup: tool_name → input_schema
_SCHEMAS: dict[str, dict] = {
    d["name"]: d["input_schema"] for d in TOOL_DEFINITIONS
}
_TOOL_NAMES: set[str] = set(_SCHEMAS.keys())

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _check_type(value: Any, schema_type: str) -> bool:
    expected = _TYPE_MAP.get(schema_type)
    if expected is None:
        return True  # unknown type — don't reject
    # Coerce numeric strings for integer params (model quirk)
    if schema_type == "integer" and isinstance(value, str):
        try:
            int(value)
            return True
        except ValueError:
            return False
    return isinstance(value, expected)


def validate_tool_call(tool_name: str, params: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate a tool call against the registered schema.
    Returns (is_valid, errors). Empty errors list means valid.
    """
    errors: list[str] = []

    if tool_name not in _TOOL_NAMES:
        errors.append(f"Unknown tool: '{tool_name}'. Valid tools: {sorted(_TOOL_NAMES)}")
        return False, errors

    schema = _SCHEMAS[tool_name]
    properties: dict = schema.get("properties", {})
    required: list[str] = schema.get("required", [])

    # Check required params are present
    for req in required:
        if req not in params:
            errors.append(f"Missing required parameter: '{req}'")

    # Check types of provided params
    for param_name, value in params.items():
        if param_name not in properties:
            continue  # extra params are fine — just ignore
        prop_schema = properties[param_name]
        expected_type = prop_schema.get("type")
        if expected_type and not _check_type(value, expected_type):
            errors.append(
                f"Parameter '{param_name}': expected {expected_type}, got {type(value).__name__}"
            )
        # Validate enum if present
        allowed = prop_schema.get("enum")
        if allowed and value not in allowed:
            errors.append(f"Parameter '{param_name}': '{value}' not in allowed values {allowed}")

    return len(errors) == 0, errors


def log_failure(
    db_path: str,
    tool_name: str,
    raw_params: dict,
    errors: list[str],
    tier: int,
    raw_response: str = "",
) -> None:
    """Persist a validation failure to SQLite for debugging."""
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_failures (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL NOT NULL,
                tool_name    TEXT NOT NULL,
                raw_params   TEXT NOT NULL,
                errors       TEXT NOT NULL,
                tier         INTEGER NOT NULL,
                raw_response TEXT
            )
        """)
        conn.execute(
            "INSERT INTO validation_failures VALUES (NULL,?,?,?,?,?,?)",
            (
                time.time(),
                tool_name,
                json.dumps(raw_params),
                json.dumps(errors),
                tier,
                raw_response,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Could not log validation failure: {e}")
