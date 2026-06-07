"""Timer and alarm — macOS notification after a delay. No external dependencies."""

from __future__ import annotations

import re
import subprocess
import threading
import time

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "timer",
    "description": (
        "Set a countdown timer or alarm. Fires a macOS notification with sound when done. "
        "Use for: 'set a 10 minute timer', 'remind me in 30 seconds', 'alarm in 2 hours'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "duration": {
                "type": "string",
                "description": "How long: '5 minutes', '30 seconds', '1 hour 20 minutes'.",
            },
            "label": {
                "type": "string",
                "description": "Timer label, e.g. 'Pasta', 'Meeting prep'. Default: Timer.",
            },
        },
        "required": ["duration"],
    },
}

# Active timers: label → (thread, cancel_event)
_active: dict[str, threading.Event] = {}


def _parse_duration(text: str) -> int:
    """Convert natural duration text to seconds."""
    text = text.lower()
    total = 0
    for val, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(hour|hr|minute|min|second|sec)s?", text):
        v = float(val)
        if "hour" in unit or unit == "hr":
            total += int(v * 3600)
        elif "min" in unit:
            total += int(v * 60)
        else:
            total += int(v)
    return total if total > 0 else 60


def _notify(label: str) -> None:
    subprocess.run([
        "osascript", "-e",
        f'display notification "{label} is done!" with title "JARVIS Timer" sound name "Glass"',
    ], capture_output=True)
    # Also speak via macOS say
    subprocess.run(["say", "-r", "175", f"{label} timer is done."], capture_output=True)


def execute(duration: str = "1 minute", label: str = "Timer") -> str:
    try:
        secs = _parse_duration(duration)
        cancel_ev = threading.Event()
        _active[label] = cancel_ev

        mins, sec = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        parts = []
        if hrs:
            parts.append(f"{hrs} hour{'s' if hrs > 1 else ''}")
        if mins:
            parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
        if sec and not hrs:
            parts.append(f"{sec} second{'s' if sec > 1 else ''}")
        human = " and ".join(parts) or "1 minute"

        def _run():
            cancel_ev.wait(timeout=secs)
            if not cancel_ev.is_set():
                _notify(label)
            _active.pop(label, None)

        threading.Thread(target=_run, daemon=True).start()
        return f"{label} timer set for {human}. I'll notify you when it's done."

    except Exception as e:
        log.error(f"timer failed: {e}")
        return f"Timer error: {e}"
