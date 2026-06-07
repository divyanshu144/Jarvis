"""
Screen vision — captures the screen and asks Claude to describe or answer questions about it.
Requires ANTHROPIC_API_KEY (same key used by Tier 3).
"""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)

_SHOT_PATH = Path("/tmp/jarvis_vision_shot.png")

DEFINITION = {
    "name": "screen_vision",
    "description": (
        "Capture the current screen and use Claude vision to describe what's visible "
        "or answer a specific question about the screen content. "
        "Use for: 'what's on my screen', 'what does this error say', "
        "'read this for me', 'what app is open', 'describe what you see'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "What to ask about the screen. Default: describe what is visible."
                ),
            },
        },
        "required": [],
    },
}


def execute(question: str = "") -> str:
    try:
        # Capture screenshot
        subprocess.run(
            ["screencapture", "-x", str(_SHOT_PATH)],
            check=True, capture_output=True,
        )

        img_data = base64.standard_b64encode(_SHOT_PATH.read_bytes()).decode()
        prompt = question.strip() or "Describe what is currently visible on the screen. Be concise and specific."

        from anthropic import Anthropic
        client = Anthropic(api_key=cfg.anthropic_key)

        response = client.messages.create(
            model=cfg.claude_model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text

    except Exception as e:
        log.error(f"screen_vision failed: {e}")
        return f"Screen vision error: {e}"
