"""Screenshot capture + base64 encoding for Claude vision."""

from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "screenshot",
    "description": (
        "Take a screenshot of the current screen. "
        "Returns the image encoded for Claude's vision, along with a file path."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "enum": ["full", "active_window"],
                "description": "full=entire screen, active_window=front window only.",
            }
        },
        "required": [],
    },
}

_SHOT_PATH = Path("/tmp/jarvis_screenshot.png")


def capture(region: str = "full") -> tuple[str, str]:
    """
    Returns (file_path, base64_data).
    Caller should pass base64_data to Claude as an image content block.
    """
    flag = "-w" if region == "active_window" else ""
    cmd = f"screencapture -x {flag} {_SHOT_PATH}".split()
    subprocess.run(cmd, check=True)
    data = base64.b64encode(_SHOT_PATH.read_bytes()).decode()
    return str(_SHOT_PATH), data


def execute(region: str = "full") -> str:
    try:
        path, _ = capture(region)
        return f"Screenshot saved to {path}. (Vision context will be included automatically.)"
    except Exception as e:
        log.error(f"screenshot failed: {e}")
        return f"Error: {e}"
