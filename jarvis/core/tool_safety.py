"""Safety policy for model-invoked tool calls."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jarvis.core.config import cfg


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


_SECRET_ENV_RE = re.compile(
    r"(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_KEY|^AWS_|^GOOGLE_APPLICATION_)",
    re.IGNORECASE,
)


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
        (r"(^|[ ;|&])rm\s+(-[^ ]+\s+)*-[^ ]*[rR](\s|$)", "recursive delete"),
        (r"(^|[ ;|&])rm\s+[^;&|]*--recursive\b", "recursive delete"),
        (r"(^|[ ;|&])find\b[^;&|]*\s-(delete|exec\s+rm)\b", "find with delete"),
        (r"(^|[ ;|&])git\s+push\b[^;&|]*(--force|-f)(\s|$)", "force push"),
        (r"\bdrop\s+(table|database)\b", "destructive SQL drop"),
        (r"\b(curl|wget)\b[^;&]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "pipe download to shell"),
        (r"\b(curl|wget)\b[^;&]*\|\s*(sudo\s+)?python[0-9.]*\b", "pipe download to python"),
        (r"(^|[ ;|&])sudo\s", "sudo"),
        (r"(^|[ ;|&])(mkfs|newfs)\b", "filesystem format"),
        (r"(^|[ ;|&])diskutil\s+(erase|zerodisk|partitiondisk|secureerase)", "disk erase"),
        (r"(^|[ ;|&])dd\b[^;&|]*\bof=/dev/", "raw disk write"),
        (r">\s*/dev/(r?disk|sd)", "raw disk write"),
        (r"(^|[ ;|&])chmod\s+(-[^ ]+\s+)*-[^ ]*r[^ ]*\s+[0-7]*777\s+/", "recursive world-writable chmod"),
        (r":\(\)\s*\{", "fork bomb"),
        (r"(^|[ ;|&])(shutdown|reboot|halt)\b", "shutdown/reboot"),
        (r"(^|[ ;|&])(security\s+(find|dump)-|security\s+export\b)", "keychain access"),
        (r"\bbase64\b[^;&]*\|\s*(ba|z)?sh\b", "decode to shell"),
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

    if tool_name == "gmail" and params.get("action") in {"send", "reply"}:
        return _requires_env("JARVIS_ALLOW_EMAIL_MUTATION", f"gmail action '{params.get('action')}'")

    if tool_name == "google_calendar" and params.get("action") in {"create_event", "delete_event"}:
        return _requires_env("JARVIS_ALLOW_CALENDAR_MUTATION", f"google_calendar action '{params.get('action')}'")

    if tool_name in {"screenshot", "screen_vision"}:
        if tool_name == "screen_vision" and cfg.privacy_local_only:
            return ToolSafetyResult(
                False, "screen_vision sends the screen to a cloud model; local-only privacy mode is on."
            )
        return _requires_env("JARVIS_ALLOW_SCREEN_CAPTURE", f"{tool_name} screen capture")

    if tool_name == "browser_control":
        url = str(params.get("url", ""))
        if url and _is_private_or_local_url(url):
            return ToolSafetyResult(False, f"Blocked browser access to local/private URL: {url}")
        if params.get("action") == "click":
            return _requires_env("JARVIS_ALLOW_BROWSER_INTERACTION", "browser_control click")
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


def requires_confirmation(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Return whether an allowed tool call must also be confirmed by the user.

    Env flags enable a capability for the session; this is the per-action check
    on top, so injected instructions cannot send, delete, or message on their own.
    """
    params = tool_input or {}
    action = params.get("action")

    if tool_name in {"shell_exec", "code_exec"}:
        return True
    if tool_name == "gmail":
        return action in {"send", "reply"}
    if tool_name == "system_control":
        return action in {"send_imessage", "facetime_call", "empty_trash"}
    if tool_name == "google_calendar":
        if action == "delete_event":
            return True
        return action == "create_event" and bool(str(params.get("attendees", "")).strip())
    if tool_name == "file_manager":
        if action in {"delete", "move"}:
            return True
        if action == "write":
            path = _path_from(params.get("path", ""))
            return bool(path and path.exists())
    return False


def scrubbed_env() -> dict[str, str]:
    """Environment for model-driven subprocesses, without API keys or other secrets."""
    return {k: v for k, v in os.environ.items() if not _SECRET_ENV_RE.search(k)}
