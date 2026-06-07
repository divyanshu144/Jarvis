"""
macOS system control — volume, brightness, DND, iMessage, contacts, screen lock.
No API keys required — pure AppleScript + shell.
"""

from __future__ import annotations

import subprocess
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "system_control",
    "description": (
        "Control macOS system settings and built-in apps. "
        "Volume: set/get/mute/unmute. "
        "Brightness: set screen brightness. "
        "Focus/DND: enable or disable Do Not Disturb. "
        "Screen: lock screen, sleep display, sleep computer. "
        "iMessage: send iMessages or SMS by contact name or phone number. "
        "Contacts: look up phone/email for a person. "
        "Media: pause/play/next/previous system media. "
        "Reminders: add a reminder with optional due date. "
        "Notes: create a new note. "
        "Maps: open a location or get directions. "
        "FaceTime: start a FaceTime call with a contact. "
        "Actions: set_volume, get_volume, mute, unmute, set_brightness, "
        "do_not_disturb, lock_screen, sleep_display, sleep_computer, "
        "send_imessage, lookup_contact, media_play, media_pause, "
        "media_next, media_previous, get_wifi, empty_trash, "
        "add_reminder, add_note, open_maps, facetime_call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "set_volume", "get_volume", "mute", "unmute",
                    "set_brightness", "do_not_disturb",
                    "lock_screen", "sleep_display", "sleep_computer",
                    "send_imessage", "lookup_contact",
                    "media_play", "media_pause", "media_next", "media_previous",
                    "get_wifi", "empty_trash",
                    "add_reminder", "add_note", "open_maps", "facetime_call",
                ],
                "description": "Action to perform.",
            },
            "value": {
                "type": "number",
                "description": "Volume level 0–100, or brightness 0–100.",
            },
            "enabled": {
                "type": "boolean",
                "description": "For Do Not Disturb: true=enable, false=disable.",
            },
            "contact": {
                "type": "string",
                "description": "Contact name or phone number for iMessage/lookup/FaceTime.",
            },
            "message": {
                "type": "string",
                "description": "Message text for send_imessage, or note/reminder body.",
            },
            "title": {
                "type": "string",
                "description": "Title for reminders and notes.",
            },
            "due_date": {
                "type": "string",
                "description": "Due date for reminder: 'YYYY-MM-DD HH:MM' or natural time.",
            },
            "location": {
                "type": "string",
                "description": "Place name or address for open_maps.",
            },
        },
        "required": ["action"],
    },
}


def _osascript(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return r.stdout.strip()


def _shell(cmd: str, timeout: int = 15) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def execute(
    action: str,
    value: float | None = None,
    enabled: bool | None = None,
    contact: str = "",
    message: str = "",
    title: str = "",
    due_date: str = "",
    location: str = "",
) -> str:
    try:
        # ── Volume ────────────────────────────────────────────────────────────
        if action == "get_volume":
            vol = _osascript("output volume of (get volume settings)")
            muted = _osascript("output muted of (get volume settings)")
            return f"Volume: {vol}% {'(muted)' if muted == 'true' else '(unmuted)'}"

        if action == "set_volume":
            v = int(max(0, min(100, value or 50)))
            _osascript(f"set volume output volume {v}")
            return f"Volume set to {v}%."

        if action == "mute":
            _osascript("set volume with output muted")
            return "Muted."

        if action == "unmute":
            _osascript("set volume without output muted")
            vol = _osascript("output volume of (get volume settings)")
            return f"Unmuted. Volume is {vol}%."

        # ── Brightness ────────────────────────────────────────────────────────
        if action == "set_brightness":
            v = max(0.0, min(1.0, (value or 50) / 100))
            # Try brightness CLI first, fall back to osascript
            result = _shell(f"brightness {v:.2f} 2>/dev/null || true")
            script = f"""
            tell application "System Events"
                tell process "SystemUIServer"
                    set value of slider 1 of menu bar item "Brightness" of menu bar 1 to {v}
                end tell
            end tell
            """
            _osascript(script)
            return f"Brightness set to {int(v*100)}%."

        # ── Do Not Disturb ────────────────────────────────────────────────────
        if action == "do_not_disturb":
            on = enabled if enabled is not None else True
            # macOS Ventura+ uses Focus mode via shortcuts
            if on:
                _shell("shortcuts run 'Do Not Disturb' 2>/dev/null || true")
                # Fallback: use defaults
                _shell("defaults -currentHost write ~/Library/Preferences/ByHost/com.apple.notificationcenterui doNotDisturb -boolean true 2>/dev/null || true")
                return "Do Not Disturb enabled."
            else:
                _shell("shortcuts run 'Turn Off Do Not Disturb' 2>/dev/null || true")
                _shell("defaults -currentHost write ~/Library/Preferences/ByHost/com.apple.notificationcenterui doNotDisturb -boolean false 2>/dev/null || true")
                return "Do Not Disturb disabled."

        # ── Screen ────────────────────────────────────────────────────────────
        if action == "lock_screen":
            _shell("/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend")
            return "Screen locked."

        if action == "sleep_display":
            _shell("pmset displaysleepnow")
            return "Display sleeping."

        if action == "sleep_computer":
            _shell("pmset sleepnow")
            return "Going to sleep."

        # ── iMessage ─────────────────────────────────────────────────────────
        if action == "send_imessage":
            if not contact or not message:
                return "Error: contact and message are required."
            safe_msg = message.replace('"', '\\"')
            safe_contact = contact.replace('"', '\\"')
            script = f"""
            tell application "Messages"
                set targetService to 1st service whose service type = iMessage
                set targetBuddy to buddy "{safe_contact}" of targetService
                send "{safe_msg}" to targetBuddy
            end tell
            """
            result = _osascript(script)
            if not result or result.strip() == "":
                return f"Message sent to {contact} via iMessage."
            return f"iMessage result: {result}"

        # ── Contacts ─────────────────────────────────────────────────────────
        if action == "lookup_contact":
            if not contact:
                return "Error: contact name required."
            safe = contact.replace('"', '\\"')
            script = f"""
            tell application "Contacts"
                set results to ""
                set matches to (every person whose name contains "{safe}")
                repeat with p in matches
                    set results to results & name of p & ": "
                    set phones to phones of p
                    repeat with ph in phones
                        set results to results & (value of ph) & ", "
                    end repeat
                    set emails to emails of p
                    repeat with em in emails
                        set results to results & (value of em) & ", "
                    end repeat
                    set results to results & linefeed
                end repeat
                return results
            end tell
            """
            result = _osascript(script)
            return result if result else f"No contact found for '{contact}'."

        # ── Media controls ────────────────────────────────────────────────────
        _MEDIA = {
            "media_play": "play",
            "media_pause": "pause",
            "media_next": "next track",
            "media_previous": "previous track",
        }
        if action in _MEDIA:
            cmd = _MEDIA[action]
            # Try Spotify first, then system media key
            spotify_result = _osascript(f'tell application "Spotify" to {cmd}')
            if not spotify_result or "error" not in spotify_result.lower():
                return f"Media: {action.replace('_', ' ')}."
            _shell(f"osascript -e 'tell application \"System Events\" to key code {cmd}'")
            return f"Media: {action.replace('_', ' ')}."

        # ── WiFi ─────────────────────────────────────────────────────────────
        if action == "get_wifi":
            result = _shell("networksetup -getairportnetwork en0 2>/dev/null || networksetup -getairportnetwork en1 2>/dev/null")
            return result or "WiFi info unavailable."

        # ── Empty Trash ───────────────────────────────────────────────────────
        if action == "empty_trash":
            _osascript('tell application "Finder" to empty trash')
            return "Trash emptied."

        # ── Reminders ─────────────────────────────────────────────────────────
        if action == "add_reminder":
            name = title or message or "Reminder"
            safe_name = name.replace('"', '\\"')
            if due_date:
                safe_due = due_date.replace('"', '\\"')
                script = f"""
                tell application "Reminders"
                    set r to make new reminder with properties {{name:"{safe_name}"}}
                    set due date of r to date "{safe_due}"
                end tell
                """
            else:
                script = f"""
                tell application "Reminders"
                    make new reminder with properties {{name:"{safe_name}"}}
                end tell
                """
            _osascript(script)
            due_str = f" due {due_date}" if due_date else ""
            return f"Reminder set: {name}{due_str}."

        # ── Notes ─────────────────────────────────────────────────────────────
        if action == "add_note":
            note_title = title or "JARVIS Note"
            note_body  = message or ""
            safe_title = note_title.replace('"', '\\"')
            safe_body  = note_body.replace('"', '\\"')
            script = f"""
            tell application "Notes"
                tell account "iCloud"
                    make new note with properties {{name:"{safe_title}", body:"{safe_body}"}}
                end tell
            end tell
            """
            _osascript(script)
            return f"Note created: {note_title}."

        # ── Maps ──────────────────────────────────────────────────────────────
        if action == "open_maps":
            dest = location or message or ""
            if not dest:
                return "Error: location required."
            import urllib.parse
            encoded = urllib.parse.quote_plus(dest)
            # Use daddr for turn-by-turn navigation, then bring Maps to front
            _shell(f'open -a Maps "maps://?daddr={encoded}"')
            import time
            time.sleep(0.8)
            _osascript('tell application "Maps" to activate')
            return f"Opening Maps with directions to {dest}."

        # ── FaceTime ──────────────────────────────────────────────────────────
        if action == "facetime_call":
            if not contact:
                return "Error: contact required."
            safe = contact.replace('"', '\\"')
            script = f"""
            tell application "FaceTime"
                activate
            end tell
            delay 0.5
            tell application "System Events"
                tell process "FaceTime"
                    keystroke "n" using command down
                    delay 0.3
                    keystroke "{safe}"
                    delay 0.5
                    key code 36
                end tell
            end tell
            """
            _osascript(script)
            return f"Starting FaceTime call with {contact}."

        return f"Unknown action: {action}"

    except Exception as e:
        log.error(f"system_control failed: {e}")
        return f"System control error: {e}"
