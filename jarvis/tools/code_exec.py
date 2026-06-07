"""Write and execute Python code, return stdout/stderr."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "code_exec",
    "description": (
        "Write a Python script to a temp file and execute it. "
        "Returns stdout and stderr. Use for calculations, data processing, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Valid Python 3 code to execute."},
        },
        "required": ["code"],
    },
}


def execute(code: str, timeout: int | str = 30) -> str:
    timeout = int(timeout)
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp = f.name

        result = subprocess.run(
            ["python3", tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        Path(tmp).unlink(missing_ok=True)

        out = result.stdout
        err = result.stderr
        combined = out
        if err:
            combined += f"\n[stderr]\n{err}"
        return combined.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: code timed out after {timeout}s."
    except Exception as e:
        log.error(f"code_exec failed: {e}")
        return f"Error: {e}"
