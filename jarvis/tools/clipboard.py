"""macOS clipboard read/write via pyperclip."""

from __future__ import annotations

import pyperclip
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "clipboard",
    "description": "Read from or write text to the macOS clipboard.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "read=get clipboard content, write=set clipboard content.",
            },
            "text": {
                "type": "string",
                "description": "Text to write to clipboard (only for 'write' action).",
            },
        },
        "required": ["action"],
    },
}


def execute(action: str, text: str = "") -> str:
    try:
        if action == "read":
            content = pyperclip.paste()
            return f"Clipboard content: {content}" if content else "Clipboard is empty."
        if action == "write":
            pyperclip.copy(text)
            return f"Copied {len(text)} characters to clipboard."
        return f"Unknown action: {action}"
    except Exception as e:
        log.error(f"clipboard failed: {e}")
        return f"Error: {e}"
