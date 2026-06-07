"""macOS Calendar integration via AppleScript."""

from __future__ import annotations

import subprocess
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "calendar",
    "description": "Read upcoming calendar events or create new events in macOS Calendar.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create"],
                "description": "list=show upcoming events, create=add a new event.",
            },
            "days_ahead": {
                "type": "integer",
                "description": "For 'list': how many days ahead to look (default 7).",
            },
            "title": {"type": "string", "description": "Event title for 'create'."},
            "start_date": {
                "type": "string",
                "description": "ISO date-time for event start, e.g. '2025-06-01 14:00'.",
            },
            "end_date": {
                "type": "string",
                "description": "ISO date-time for event end.",
            },
            "calendar_name": {
                "type": "string",
                "description": "Calendar name to create in (default: first available).",
            },
        },
        "required": ["action"],
    },
}


def _run(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def execute(
    action: str,
    days_ahead: int = 7,
    title: str = "",
    start_date: str = "",
    end_date: str = "",
    calendar_name: str = "",
) -> str:
    try:
        if action == "list":
            script = f"""
            tell application "Calendar"
                set theEvents to ""
                set d to current date
                set endD to d + ({days_ahead} * days)
                repeat with cal in calendars
                    repeat with ev in (events of cal whose start date >= d and start date <= endD)
                        set theEvents to theEvents & (summary of ev) & " @ " & (start date of ev as string) & linefeed
                    end repeat
                end repeat
                return theEvents
            end tell
            """
            result = _run(script)
            return result if result else f"No events in the next {days_ahead} days."

        if action == "create":
            if not title or not start_date:
                return "Error: title and start_date are required."
            end = end_date or start_date
            cal_clause = f'calendar "{calendar_name}"' if calendar_name else "first calendar"
            script = f"""
            tell application "Calendar"
                tell {cal_clause}
                    set startD to date "{start_date}"
                    set endD to date "{end}"
                    make new event with properties {{summary:"{title}", start date:startD, end date:endD}}
                end tell
            end tell
            """
            _run(script)
            return f"Created event '{title}' on {start_date}."

        return f"Unknown action: {action}"
    except Exception as e:
        log.error(f"calendar failed: {e}")
        return f"Error: {e}"
