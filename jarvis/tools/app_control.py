"""macOS app control via AppleScript."""

from __future__ import annotations

import subprocess
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "app_control",
    "description": (
        "Open, close, hide, or switch to a macOS application. "
        "Also can list running applications."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "close", "hide", "switch", "list"],
                "description": "The action to perform.",
            },
            "app_name": {
                "type": "string",
                "description": "Name of the application (e.g. 'Safari', 'Terminal'). Not needed for 'list'.",
            },
        },
        "required": ["action"],
    },
}


def _run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def execute(action: str, app_name: str = "") -> str:
    """Execute an app control action and return a status string."""
    try:
        if action == "list":
            out = _run_applescript(
                'tell application "System Events" to get name of every process '
                "where background only is false"
            )
            return f"Running apps: {out}"

        if not app_name:
            return "Error: app_name is required for this action."

        if action == "open":
            _run_applescript(f'tell application "{app_name}" to activate')
            return f"Opened {app_name}."

        if action == "switch":
            _run_applescript(f'tell application "{app_name}" to activate')
            return f"Switched to {app_name}."

        if action == "close":
            _run_applescript(f'tell application "{app_name}" to quit')
            return f"Closed {app_name}."

        if action == "hide":
            _run_applescript(
                f'tell application "System Events" to set visible of process "{app_name}" to false'
            )
            return f"Hid {app_name}."

        return f"Unknown action: {action}"
    except Exception as e:
        log.error(f"app_control failed: {e}")
        return f"Error: {e}"
