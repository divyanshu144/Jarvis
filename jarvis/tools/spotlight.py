"""Spotlight file search via mdfind — instant, no indexing needed."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "spotlight",
    "description": (
        "Search for files on this Mac using Spotlight (mdfind). "
        "Use for: 'find my resume', 'where is the Q3 report', 'search for budget.xlsx', "
        "'find photos from last week', 'open the project file'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for — filename, content, or type.",
            },
            "kind": {
                "type": "string",
                "enum": ["any", "document", "image", "pdf", "spreadsheet", "presentation", "code", "folder"],
                "description": "Limit to a file type. Default: any.",
            },
            "open_first": {
                "type": "boolean",
                "description": "Open the top result in its default app. Default false.",
            },
        },
        "required": ["query"],
    },
}

_KIND_FILTER = {
    "document":     "kMDItemKind == 'Microsoft Word Document' || kMDItemKind == 'Plain Text'",
    "image":        "kMDItemContentTypeTree == 'public.image'",
    "pdf":          "kMDItemContentTypeTree == 'com.adobe.pdf'",
    "spreadsheet":  "kMDItemKind == 'Microsoft Excel Spreadsheet'",
    "presentation": "kMDItemKind == 'Microsoft PowerPoint Presentation'",
    "code":         "kMDItemContentTypeTree == 'public.source-code'",
    "folder":       "kMDItemContentTypeTree == 'public.folder'",
}


def execute(query: str, kind: str = "any", open_first: bool = False) -> str:
    try:
        cmd = ["mdfind", "-onlyin", str(Path.home()), query]
        if kind != "any" and kind in _KIND_FILTER:
            cmd = ["mdfind", "-onlyin", str(Path.home()),
                   "-interpret", f"({query}) AND ({_KIND_FILTER[kind]})"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        paths = [p for p in result.stdout.strip().splitlines() if p][:10]

        if not paths:
            return f"No files found for '{query}'."

        if open_first:
            subprocess.Popen(["open", paths[0]])
            name = Path(paths[0]).name
            return f"Opening {name}. Found {len(paths)} match{'es' if len(paths) > 1 else ''}."

        lines = [f"Found {len(paths)} result{'s' if len(paths) > 1 else ''} for '{query}':"]
        for p in paths:
            lines.append(f"  {Path(p).name}  ({p})")
        return "\n".join(lines)

    except Exception as e:
        log.error(f"spotlight failed: {e}")
        return f"Search error: {e}"
