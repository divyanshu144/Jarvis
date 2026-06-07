"""Shell command execution with captured output."""

from __future__ import annotations

import os
import re
import subprocess
import urllib.parse

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "shell_exec",
    "description": (
        "Run any shell command in zsh and return stdout + stderr. "
        "Use for system administration, git, brew, npm, etc. "
        "For Spotify: use open \"spotify:search:Artist+Song\" then "
        "osascript -e 'tell application \"Spotify\" to play'"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
        },
        "required": ["command"],
    },
}

# Patterns Tier-1 hallucinates for Spotify — all rewritten to URI scheme
_SPOTIFY_BAD = [
    # osascript: play file POSIX path "/path/to/song.mp3"
    re.compile(
        r'tell\s+application\s+"Spotify"\s+to\s+play\s+(?:file\s+POSIX\s+path|track\s+named)\s+"([^"]+)"',
        re.IGNORECASE,
    ),
    # open "file:///path/song.mp3" (wrong URI for Spotify)
    re.compile(r'open\s+"file:///([^"]+\.(mp3|wav|flac|m4a|aac|ogg))"', re.IGNORECASE),
]


def _fix_spotify(cmd: str) -> str:
    """Rewrite hallucinated Spotify file-path commands to the spotify:search: URI scheme."""
    for pattern in _SPOTIFY_BAD:
        m = pattern.search(cmd)
        if m:
            raw = m.group(1)
            # Strip file:// prefix if present, take basename, remove extension
            raw = raw.replace("file://", "").replace("file:", "")
            name = os.path.basename(raw)
            name = re.sub(r"\.(mp3|wav|flac|m4a|aac|ogg)$", "", name, flags=re.IGNORECASE)
            name = re.sub(r"[_\-]+", " ", name)
            name = re.sub(r"\s+", " ", name).strip()
            encoded = name.replace(" ", "+")
            fixed = (
                f'open "spotify:search:{encoded}" && '
                f"sleep 2 && "
                f"osascript -e 'tell application \"Spotify\" to play'"
            )
            log.info(f"Rewrote Spotify hallucination → spotify:search:{encoded}")
            return fixed
    return cmd


def execute(command: str, cwd: str | None = None, timeout: int | str = 30) -> str:
    timeout = int(timeout)
    command = _fix_spotify(command)
    log.info(f"shell_exec: {command!r}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/zsh",
            capture_output=True,
            text=True,
            cwd=cwd or None,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s."
    except Exception as e:
        log.error(f"shell_exec failed: {e}")
        return f"Error: {e}"
