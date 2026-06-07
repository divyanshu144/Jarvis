"""Safety policy for model-invoked tool calls."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_ROOT = Path(__file__).parent.parent.parent.resolve()
_SENSITIVE_NAMES = {
    "config.yaml",
    "google_credentials.json",
    "google_token.json",
    "jarvis.db",
}
_SENSITIVE_DIRS = {
    str((_ROOT / "data").resolve()),
    str((_ROOT / "logs").resolve()),
}


@dataclass(frozen=True)
class ToolSafetyResult:
    allowed: bool
    reason: str = ""


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _requires_env(var: str, action: str) -> ToolSafetyResult:
    if _enabled(var):
        return ToolSafetyResult(True)
    return ToolSafetyResult(
        False,
        f"{action} requires explicit approval. Set {var}=1 only for the approved session.",
    )


def _path_from(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        return Path(value).expanduser()


def _is_sensitive_path(path: Path | None) -> bool:
    if path is None:
        return False
    if path.name in _SENSITIVE_NAMES:
        return True
    path_s = str(path)
    return any(path_s == d or path_s.startswith(d + os.sep) for d in _SENSITIVE_DIRS)


def _is_private_or_local_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    host = parsed.hostname
    if not host:
        return True
    if host.lower() in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _dangerous_shell(command: str) -> str | None:
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    checks = [
        (r"(^|[ ;|&])rm\s+(-[^ ]*r[^ ]*f|-rf|-fr)(\s|$)", "recursive force delete"),
        (r"(^|[ ;|&])git\s+push\b[^;&|]*(--force|-f)(\s|$)", "force push"),
        (r"\bdrop\s+(table|database)\b", "destructive SQL drop"),
    ]
    for pattern, label in checks:
        if re.search(pattern, normalized):
            return label
    if re.search(r"\bdelete\s+from\b", normalized) and not re.search(r"\bwhere\b", normalized):
        return "DELETE FROM without WHERE"
    if re.search(r"(^|[ ;|&])truncate\s+", normalized) and re.search(r"\b(prod|production)\b", normalized):
        return "truncate against prod/production"
    return None


def check_tool_safety(tool_name: str, tool_input: dict[str, Any]) -> ToolSafetyResult:
    """Return whether a model-invoked tool call is allowed to execute."""
    params = tool_input or {}

    if tool_name == "shell_exec":
        command = str(params.get("command", ""))
        danger = _dangerous_shell(command)
        if danger:
            return ToolSafetyResult(False, f"Blocked shell command: {danger}.")
        return _requires_env("JARVIS_ALLOW_SHELL_EXEC", "shell execution")

    if tool_name == "code_exec":
        return _requires_env("JARVIS_ALLOW_CODE_EXEC", "Python code execution")

    if tool_name == "file_manager":
        action = str(params.get("action", ""))
        path = _path_from(params.get("path", ""))
        destination = _path_from(params.get("destination", ""))
        search_dir = _path_from(params.get("search_dir", ""))
        if any(_is_sensitive_path(p) for p in (path, destination, search_dir)):
            return ToolSafetyResult(False, "Blocked file access to sensitive project runtime paths.")
        if action in {"write", "append", "move", "delete"}:
            return _requires_env("JARVIS_ALLOW_FILE_MUTATION", f"file_manager action '{action}'")
        return ToolSafetyResult(True)

    if tool_name == "gmail" and params.get("action") in {"send", "reply", "mark_read"}:
        return _requires_env("JARVIS_ALLOW_EMAIL_MUTATION", f"gmail action '{params.get('action')}'")

    if tool_name == "google_calendar" and params.get("action") in {"create_event", "delete_event"}:
        return _requires_env("JARVIS_ALLOW_CALENDAR_MUTATION", f"google_calendar action '{params.get('action')}'")

    if tool_name in {"screenshot", "screen_vision"}:
        return _requires_env("JARVIS_ALLOW_SCREEN_CAPTURE", f"{tool_name} screen capture")

    if tool_name == "browser_control":
        url = str(params.get("url", ""))
        if url and _is_private_or_local_url(url):
            return ToolSafetyResult(False, f"Blocked browser access to local/private URL: {url}")
        return ToolSafetyResult(True)

    if tool_name == "system_control":
        action = params.get("action")
        risky = {
            "send_imessage",
            "empty_trash",
            "sleep_computer",
            "lock_screen",
            "facetime_call",
            "add_reminder",
            "add_note",
        }
        if action in risky:
            return _requires_env("JARVIS_ALLOW_SYSTEM_MUTATION", f"system_control action '{action}'")

    return ToolSafetyResult(True)
