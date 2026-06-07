"""File system operations — read, write, move, delete, search."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "file_manager",
    "description": "Read, write, move, delete, or search files anywhere on the system.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "append", "move", "delete", "search", "list"],
            },
            "path": {"type": "string", "description": "Absolute or ~ path."},
            "destination": {"type": "string", "description": "Destination path for move."},
            "content": {"type": "string", "description": "Content to write/append."},
            "pattern": {"type": "string", "description": "Glob pattern for search (e.g. '*.py')."},
            "search_dir": {"type": "string", "description": "Directory to search in."},
        },
        "required": ["action"],
    },
}


def execute(
    action: str,
    path: str = "",
    destination: str = "",
    content: str = "",
    pattern: str = "*",
    search_dir: str = ".",
) -> str:
    try:
        if path:
            path = str(Path(path).expanduser())

        if action == "read":
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            return text[:8000] + ("…" if len(text) > 8000 else "")

        if action == "write":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}."

        if action == "append":
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"Appended to {path}."

        if action == "move":
            dest = str(Path(destination).expanduser())
            shutil.move(path, dest)
            return f"Moved {path} → {dest}."

        if action == "delete":
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(path)
            else:
                p.unlink()
            return f"Deleted {path}."

        if action == "list":
            p = Path(path or ".").expanduser()
            entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
            lines = [f"{'[DIR] ' if e.is_dir() else '      '}{e.name}" for e in entries]
            return "\n".join(lines)

        if action == "search":
            base = Path(search_dir).expanduser()
            matches = list(base.rglob(pattern))[:50]
            if not matches:
                return f"No files matching '{pattern}' in {search_dir}."
            return "\n".join(str(m) for m in matches)

        return f"Unknown action: {action}"
    except Exception as e:
        log.error(f"file_manager failed: {e}")
        return f"Error: {e}"
