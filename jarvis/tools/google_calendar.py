"""
Google Calendar tool — full CRUD + smart scheduling.
Requires data/google_credentials.json (see _google_auth.py).
"""

from __future__ import annotations

import datetime
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "google_calendar",
    "description": (
        "Read and manage Google Calendar. "
        "Use for: getting today's agenda, upcoming events, creating events, "
        "finding free time, checking if you're free at a time, rescheduling. "
        "Actions: get_today, list_events, create_event, delete_event, find_free_time."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_today", "list_events", "create_event", "delete_event", "find_free_time", "get_next_event"],
                "description": "Action to perform.",
            },
            "days_ahead": {"type": "integer", "description": "Days to look ahead for list_events (default 3)."},
            "title": {"type": "string", "description": "Event title for create."},
            "start_time": {"type": "string", "description": "Start time: ISO format or 'YYYY-MM-DD HH:MM'."},
            "end_time": {"type": "string", "description": "End time: ISO format or 'YYYY-MM-DD HH:MM'."},
            "description": {"type": "string", "description": "Event description/notes."},
            "attendees": {"type": "string", "description": "Comma-separated email addresses."},
            "event_id": {"type": "string", "description": "Event ID for delete."},
            "check_date": {"type": "string", "description": "Date to check free time: 'YYYY-MM-DD'."},
        },
        "required": ["action"],
    },
}


def _get_service():
    from jarvis.tools._google_auth import get_service
    return get_service("calendar", "v3")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_time(s: str) -> str:
    """Accept 'YYYY-MM-DD HH:MM' or ISO — return RFC3339 with local offset."""
    if not s:
        return _now_iso()
    s = s.strip()
    if "T" in s and ("+" in s or s.endswith("Z")):
        return s  # already RFC3339
    try:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        if len(s) == 16:  # 'YYYY-MM-DD HH:MM'
            dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
        else:
            dt = datetime.datetime.fromisoformat(s).replace(tzinfo=local_tz)
        return dt.isoformat()
    except Exception:
        return s


def _fmt_event(e: dict) -> str:
    start = e["start"].get("dateTime", e["start"].get("date", ""))
    end = e["end"].get("dateTime", e["end"].get("date", ""))
    # Format nicely
    try:
        dt = datetime.datetime.fromisoformat(start)
        start_fmt = dt.strftime("%a %b %d, %I:%M %p")
    except Exception:
        start_fmt = start
    title = e.get("summary", "(No title)")
    loc = e.get("location", "")
    loc_str = f" @ {loc}" if loc else ""
    attendees = [a.get("email", "") for a in e.get("attendees", [])]
    att_str = f" | with: {', '.join(attendees[:3])}" if attendees else ""
    return f"• {title}{loc_str} — {start_fmt}{att_str}  [id:{e['id'][:12]}]"


def execute(
    action: str,
    days_ahead: int = 3,
    title: str = "",
    start_time: str = "",
    end_time: str = "",
    description: str = "",
    attendees: str = "",
    event_id: str = "",
    check_date: str = "",
) -> str:
    try:
        service = _get_service()
        cal_id = "primary"

        if action in ("get_today", "list_events", "get_next_event"):
            now = datetime.datetime.now(datetime.timezone.utc)
            if action == "get_today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + datetime.timedelta(days=1)
                label = "today"
            elif action == "get_next_event":
                start = now
                end = now + datetime.timedelta(days=7)
                label = "upcoming"
            else:
                start = now
                end = now + datetime.timedelta(days=days_ahead)
                label = f"next {days_ahead} days"

            events = service.events().list(
                calendarId=cal_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            ).execute().get("items", [])

            if not events:
                return f"No events {label}. Schedule is clear."

            if action == "get_next_event":
                return f"Next event:\n{_fmt_event(events[0])}"

            lines = [f"Events {label} ({len(events)}):"]
            for e in events:
                lines.append(_fmt_event(e))
            return "\n".join(lines)

        if action == "create_event":
            if not title or not start_time:
                return "Error: title and start_time are required."
            start_iso = _parse_time(start_time)
            if end_time:
                end_iso = _parse_time(end_time)
            else:
                # Default 1 hour
                dt = datetime.datetime.fromisoformat(start_iso)
                end_iso = (dt + datetime.timedelta(hours=1)).isoformat()

            body: dict = {
                "summary": title,
                "start": {"dateTime": start_iso},
                "end": {"dateTime": end_iso},
            }
            if description:
                body["description"] = description
            if attendees:
                body["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
                body["sendUpdates"] = "all"

            ev = service.events().insert(calendarId=cal_id, body=body).execute()
            return f"Created: '{title}' at {start_time}. Event ID: {ev['id'][:12]}"

        if action == "delete_event":
            if not event_id:
                return "Error: event_id required."
            # Support short IDs from _fmt_event
            if len(event_id) < 20:
                # find by short id prefix
                events = service.events().list(
                    calendarId=cal_id,
                    timeMin=_now_iso(),
                    singleEvents=True,
                    maxResults=50,
                ).execute().get("items", [])
                match = next((e for e in events if e["id"].startswith(event_id)), None)
                if not match:
                    return f"Event not found with id prefix: {event_id}"
                event_id = match["id"]
            service.events().delete(calendarId=cal_id, eventId=event_id).execute()
            return f"Event deleted."

        if action == "find_free_time":
            date_str = check_date or datetime.date.today().isoformat()
            day = datetime.date.fromisoformat(date_str)
            local_tz = datetime.datetime.now().astimezone().tzinfo
            day_start = datetime.datetime(day.year, day.month, day.day, 9, 0, tzinfo=local_tz)
            day_end = datetime.datetime(day.year, day.month, day.day, 18, 0, tzinfo=local_tz)

            events = service.events().list(
                calendarId=cal_id,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute().get("items", [])

            busy = []
            for e in events:
                s = e["start"].get("dateTime", "")
                en = e["end"].get("dateTime", "")
                if s and en:
                    busy.append((datetime.datetime.fromisoformat(s), datetime.datetime.fromisoformat(en)))

            free_slots = []
            cursor = day_start
            for s, en in sorted(busy):
                if cursor < s:
                    free_slots.append(f"{cursor.strftime('%I:%M %p')} – {s.strftime('%I:%M %p')}")
                cursor = max(cursor, en)
            if cursor < day_end:
                free_slots.append(f"{cursor.strftime('%I:%M %p')} – {day_end.strftime('%I:%M %p')}")

            if not free_slots:
                return f"No free slots on {date_str} between 9am–6pm."
            return f"Free slots on {date_str}:\n" + "\n".join(f"• {s}" for s in free_slots)

        return f"Unknown action: {action}"

    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        log.error(f"google_calendar failed: {e}")
        return f"Calendar error: {e}"
