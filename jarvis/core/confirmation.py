"""Per-action user confirmation for high-impact tool calls.

A tool call that `tool_safety.requires_confirmation` flags is not executed.
It is parked here and only runs when the user's *next* message is an explicit
confirmation. The check happens in `Agent.chat` on raw user input, so the model
(or text injected into tool output) can never confirm on the user's behalf.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

_TTL_SECONDS = 120

_CONFIRM_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|confirm(?:ed)?|do it|go ahead|send it|proceed|approved?)"
    r"(?:\s*,?\s*(?:please|jarvis|confirm|do it|send it|go ahead))*\s*[.!]*\s*$",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^\s*(?:no|nope|cancel|stop|abort|don'?t|do not|never ?mind|forget it)\b",
    re.IGNORECASE,
)


@dataclass
class PendingAction:
    tool_name: str
    tool_input: dict[str, Any]
    description: str
    request_id: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def prompt(self) -> str:
        return f"Please confirm: {self.description}. Say confirm to proceed, or cancel."


def describe_action(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Return a short, spoken description of what a tool call would do."""
    p = tool_input or {}
    action = p.get("action", "")

    def _short(value: Any, limit: int = 60) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    if tool_name == "gmail" and action == "send":
        return f"send an email to {_short(p.get('to')) or 'an unknown recipient'} with subject \"{_short(p.get('subject'))}\""
    if tool_name == "gmail" and action == "reply":
        return f"send a reply to email {_short(p.get('email_id'), 24)}"
    if tool_name == "system_control" and action == "send_imessage":
        return f"send an iMessage to {_short(p.get('contact'))} saying \"{_short(p.get('message'))}\""
    if tool_name == "system_control" and action == "facetime_call":
        return f"start a FaceTime call with {_short(p.get('contact'))}"
    if tool_name == "system_control" and action == "empty_trash":
        return "permanently empty the Trash"
    if tool_name == "google_calendar" and action == "delete_event":
        return f"delete calendar event {_short(p.get('event_id'), 24)}"
    if tool_name == "google_calendar" and action == "create_event":
        return f"create \"{_short(p.get('title'))}\" and send invites to {_short(p.get('attendees'))}"
    if tool_name == "file_manager" and action == "delete":
        return f"delete {_short(p.get('path'), 120)}"
    if tool_name == "file_manager" and action == "move":
        return f"move {_short(p.get('path'), 120)} to {_short(p.get('destination'), 120)}"
    if tool_name == "file_manager" and action == "write":
        return f"overwrite the existing file {_short(p.get('path'), 120)}"
    if tool_name == "shell_exec":
        return f"run the shell command {_short(p.get('command'), 120)}"
    if tool_name == "code_exec":
        return f"run a {len(str(p.get('code') or '').splitlines())}-line Python script"
    if tool_name == "privacy" and action == "forget":
        return "permanently delete all conversation memory, profile facts, traces and logs"
    return f"run {tool_name} {action}".strip()


class ConfirmationStore:
    """Holds at most one pending action awaiting user confirmation."""

    def __init__(self, ttl_seconds: float = _TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._pending: PendingAction | None = None

    def request(self, tool_name: str, tool_input: dict[str, Any], request_id: str | None = None) -> str:
        """Park a tool call and return the message the model should relay."""
        with self._lock:
            self._expire_locked()
            if self._pending is not None and self._pending.request_id == request_id:
                return (
                    "Confirmation required, but another action is already awaiting confirmation. "
                    "This action has NOT been performed. Tell the user to confirm the first action, "
                    "then ask again."
                )
            self._pending = PendingAction(
                tool_name=tool_name,
                tool_input=dict(tool_input or {}),
                description=describe_action(tool_name, tool_input),
                request_id=request_id,
            )
            return (
                f"Confirmation required before this action runs: {self._pending.description}. "
                "It has NOT been performed. Tell the user it is waiting for their confirmation."
            )

    def pending(self) -> PendingAction | None:
        with self._lock:
            self._expire_locked()
            return self._pending

    def take(self) -> PendingAction | None:
        with self._lock:
            self._expire_locked()
            action, self._pending = self._pending, None
            return action

    def clear(self) -> None:
        with self._lock:
            self._pending = None

    def _expire_locked(self) -> None:
        if self._pending and time.time() - self._pending.created_at > self._ttl:
            self._pending = None


def is_confirmation(text: str) -> bool:
    return bool(_CONFIRM_RE.match(text or ""))


def is_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text or ""))


store = ConfirmationStore()
