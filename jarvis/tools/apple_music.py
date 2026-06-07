"""Apple Music control via AppleScript. No API key required."""

from __future__ import annotations

import subprocess
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "apple_music",
    "description": (
        "Control Apple Music app. "
        "Search and play songs, pause, skip, get current track, "
        "set volume, shuffle, repeat. "
        "Use when user mentions Apple Music explicitly or doesn't have Spotify."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "play", "pause", "next", "previous", "stop",
                    "search_play", "current_track",
                    "set_volume", "shuffle", "repeat",
                ],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Song/artist to search and play for search_play.",
            },
            "value": {
                "type": "number",
                "description": "Volume 0-100 for set_volume.",
            },
            "enabled": {
                "type": "boolean",
                "description": "Enable/disable shuffle or repeat.",
            },
        },
        "required": ["action"],
    },
}


def _osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return r.stdout.strip()


def execute(
    action: str,
    query: str = "",
    value: float | None = None,
    enabled: bool | None = None,
) -> str:
    try:
        if action == "play":
            _osa('tell application "Music" to play')
            return "Resuming Apple Music."

        if action == "pause":
            _osa('tell application "Music" to pause')
            return "Paused Apple Music."

        if action == "stop":
            _osa('tell application "Music" to stop')
            return "Stopped Apple Music."

        if action == "next":
            _osa('tell application "Music" to next track')
            return "Skipped to next track."

        if action == "previous":
            _osa('tell application "Music" to previous track')
            return "Going to previous track."

        if action == "current_track":
            name   = _osa('tell application "Music" to get name of current track')
            artist = _osa('tell application "Music" to get artist of current track')
            album  = _osa('tell application "Music" to get album of current track')
            if name:
                return f"Now playing: {name} by {artist} — {album}."
            return "Nothing is playing in Apple Music."

        if action == "search_play":
            if not query:
                return "Error: query required for search_play."
            safe = query.replace('"', '\\"')
            script = f"""
            tell application "Music"
                activate
                set results to search playlist "Library" for "{safe}"
                if results is not {{}} then
                    play item 1 of results
                    return "Playing: " & (name of item 1 of results) & " by " & (artist of item 1 of results)
                else
                    return "not found"
                end if
            end tell
            """
            result = _osa(script)
            if "not found" in result:
                return f"Could not find '{query}' in your Apple Music library."
            return result or f"Playing {query} in Apple Music."

        if action == "set_volume":
            v = int(max(0, min(100, value or 80)))
            _osa(f'tell application "Music" to set sound volume to {v}')
            return f"Apple Music volume set to {v}%."

        if action == "shuffle":
            on = enabled if enabled is not None else True
            state = "true" if on else "false"
            _osa(f'tell application "Music" to set shuffle enabled to {state}')
            return f"Shuffle {'enabled' if on else 'disabled'}."

        if action == "repeat":
            on = enabled if enabled is not None else True
            mode = "all" if on else "off"
            _osa(f'tell application "Music" to set song repeat to {mode}')
            return f"Repeat {'enabled' if on else 'disabled'}."

        return f"Unknown action: {action}"

    except Exception as e:
        log.error(f"apple_music failed: {e}")
        return f"Apple Music error: {e}"
