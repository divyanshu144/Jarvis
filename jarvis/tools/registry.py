"""Tool registry — maps tool names to definitions and executor functions."""

from __future__ import annotations

from typing import Any, Callable

from jarvis.core.tool_safety import check_tool_safety
from jarvis.core.tracing import record_safety_block, record_tool_run, summarize_tool_result
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


def dispatch(tool_name: str, tool_input: dict[str, Any], request_id: str | None = None) -> str:
    """Execute a tool by name with the given input dict. Always returns a string."""
    import time

    started = time.monotonic()
    executor = _EXECUTORS.get(tool_name)
    if executor is None:
        result = f"Error: unknown tool '{tool_name}'."
        if request_id:
            record_tool_run(
                request_id,
                tool_name,
                tool_input,
                status="error",
                result_summary=result,
                error=result,
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return result

    safety = check_tool_safety(tool_name, tool_input)
    if not safety.allowed:
        result = f"Safety blocked {tool_name}: {safety.reason}"
        if request_id:
            record_safety_block(request_id, tool_name, tool_input, safety.reason)
        return result

    try:
        result = executor(**tool_input)
        status = "error" if str(result).startswith("Error") else "ok"
        if request_id:
            record_tool_run(
                request_id,
                tool_name,
                tool_input,
                status=status,
                result_summary=summarize_tool_result(tool_name, result),
                error=str(result) if status == "error" else "",
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return result
    except TypeError as e:
        result = f"Error calling {tool_name}: bad arguments — {e}"
        if request_id:
            record_tool_run(
                request_id,
                tool_name,
                tool_input,
                status="error",
                result_summary=result,
                error=str(e),
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return result
    except Exception as e:
        result = f"Error in {tool_name}: {e}"
        if request_id:
            record_tool_run(
                request_id,
                tool_name,
                tool_input,
                status="error",
                result_summary=result,
                error=str(e),
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return result
