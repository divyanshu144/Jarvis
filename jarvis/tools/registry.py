"""Tool registry — maps tool names to definitions and executor functions."""

from __future__ import annotations

from typing import Any, Callable

from jarvis.core.tool_safety import check_tool_safety
from jarvis.tools import (
    apple_music,
    app_control,
    browser,
    calendar_tool,
    clipboard,
    code_exec,
    file_manager,
    fde_tool,
    gmail,
    google_calendar,
    screen_vision,
    screenshot,
    shell,
    spotlight,
    system_control,
    system_info,
    timer_tool,
    weather,
    web_search,
)

# All tool definitions sent to LLMs
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    apple_music.DEFINITION,
    app_control.DEFINITION,
    browser.DEFINITION,
    calendar_tool.DEFINITION,
    clipboard.DEFINITION,
    code_exec.DEFINITION,
    file_manager.DEFINITION,
    fde_tool.DEFINITION,
    gmail.DEFINITION,
    google_calendar.DEFINITION,
    screen_vision.DEFINITION,
    screenshot.DEFINITION,
    shell.DEFINITION,
    spotlight.DEFINITION,
    system_control.DEFINITION,
    system_info.DEFINITION,
    timer_tool.DEFINITION,
    weather.DEFINITION,
    web_search.DEFINITION,
]

# Map tool name → executor function
_EXECUTORS: dict[str, Callable[..., str]] = {
    "apple_music":      apple_music.execute,
    "app_control":      app_control.execute,
    "browser_control":  browser.execute,
    "calendar":         calendar_tool.execute,
    "clipboard":        clipboard.execute,
    "code_exec":        code_exec.execute,
    "file_manager":     file_manager.execute,
    "fde_tracker":      fde_tool.execute,
    "gmail":            gmail.execute,
    "google_calendar":  google_calendar.execute,
    "screen_vision":    screen_vision.execute,
    "screenshot":       screenshot.execute,
    "shell_exec":       shell.execute,
    "spotlight":        spotlight.execute,
    "system_control":   system_control.execute,
    "system_info":      system_info.execute,
    "timer":            timer_tool.execute,
    "weather":          weather.execute,
    "web_search":       web_search.execute,
}


def dispatch(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool by name with the given input dict. Always returns a string."""
    executor = _EXECUTORS.get(tool_name)
    if executor is None:
        return f"Error: unknown tool '{tool_name}'."
    safety = check_tool_safety(tool_name, tool_input)
    if not safety.allowed:
        return f"Safety blocked {tool_name}: {safety.reason}"
    try:
        return executor(**tool_input)
    except TypeError as e:
        return f"Error calling {tool_name}: bad arguments — {e}"
    except Exception as e:
        return f"Error in {tool_name}: {e}"
