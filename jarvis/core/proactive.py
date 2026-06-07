"""
Proactive monitor — speaks without being asked.
Checks calendar, battery, and email on a schedule.
Announces upcoming meetings, low battery, urgent emails.
"""

from __future__ import annotations

import datetime
import threading
import time
from typing import Callable

from jarvis.core.logger import get_logger

log = get_logger(__name__)

# How often to check each thing
_CALENDAR_INTERVAL = 60       # seconds — check for upcoming meetings
_BATTERY_INTERVAL = 120       # seconds — check battery
_EMAIL_INTERVAL = 300         # seconds — check urgent email
_MEETING_WARN_MINS = 10       # minutes before meeting to announce
_BATTERY_WARN_LEVEL = 15      # % threshold


class ProactiveMonitor:
    """
    Background daemon that watches calendar, battery, and email.
    Calls speak_fn() to announce things proactively.
    Respects is_busy() — never interrupts an active voice cycle.
    """

    def __init__(
        self,
        speak_fn: Callable[[str], None],
        is_busy: Callable[[], bool],
    ) -> None:
        self._speak = speak_fn
        self._is_busy = is_busy

        # Cooldown tracking — don't repeat the same announcement
        self._announced_events: set[str] = set()  # event ids already announced
        self._battery_warned = False
        self._last_email_check = 0.0
        self._last_battery_check = 0.0
        self._last_calendar_check = 0.0
        self._last_fde_weekly_date: datetime.date | None = None
        self._seen_email_ids: set[str] = set()

        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()
        log.info("Proactive monitor started.")

    def _say(self, text: str) -> None:
        """Speak only if JARVIS isn't already handling a voice cycle."""
        if self._is_busy():
            return
        log.info(f"[Proactive] {text}")
        self._speak(text)

    def _check_calendar(self) -> None:
        try:
            from jarvis.tools.google_calendar import execute as cal_exec
            from jarvis.tools._google_auth import TOKEN_PATH, CREDS_PATH
            if not TOKEN_PATH.exists() and not CREDS_PATH.exists():
                return  # Google not set up yet

            result = cal_exec(action="get_today")
            if "No events" in result or "clear" in result.lower():
                return

            now = datetime.datetime.now().astimezone()
            # Parse events from the formatted string to find upcoming ones
            # Re-fetch raw events for timing
            from jarvis.tools._google_auth import get_service
            service = get_service("calendar", "v3")
            end = now + datetime.timedelta(hours=2)
            events = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=5,
            ).execute().get("items", [])

            for ev in events:
                ev_id = ev.get("id", "")
                if ev_id in self._announced_events:
                    continue
                start_str = ev["start"].get("dateTime", "")
                if not start_str:
                    continue
                ev_start = datetime.datetime.fromisoformat(start_str)
                mins_until = (ev_start - now).total_seconds() / 60
                if 0 < mins_until <= _MEETING_WARN_MINS:
                    title = ev.get("summary", "a meeting")
                    mins_int = int(mins_until)
                    attendees = [a.get("displayName") or a.get("email", "")
                                 for a in ev.get("attendees", [])[:2]]
                    att_str = f" with {', '.join(attendees)}" if attendees else ""
                    self._say(
                        f"Heads up, you have {title}{att_str} in {mins_int} minute{'s' if mins_int != 1 else ''}."
                    )
                    self._announced_events.add(ev_id)
        except FileNotFoundError:
            pass  # Google not configured
        except Exception as e:
            log.debug(f"Proactive calendar check failed: {e}")

    def _check_battery(self) -> None:
        try:
            import subprocess
            result = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
            )
            output = result.stdout
            import re
            m = re.search(r"(\d+)%", output)
            if not m:
                return
            level = int(m.group(1))
            charging = "AC Power" in output or "charging" in output.lower()

            if level <= _BATTERY_WARN_LEVEL and not charging and not self._battery_warned:
                self._say(f"Battery is at {level}%. You might want to plug in.")
                self._battery_warned = True
            elif level > _BATTERY_WARN_LEVEL + 5:
                self._battery_warned = False  # reset once charged up
        except Exception as e:
            log.debug(f"Proactive battery check failed: {e}")

    def _check_email(self) -> None:
        try:
            from jarvis.tools._google_auth import TOKEN_PATH, CREDS_PATH
            if not TOKEN_PATH.exists() and not CREDS_PATH.exists():
                return

            from jarvis.tools.gmail import _get_service
            service = _get_service()
            # Check for new important/unread emails in last 5 minutes
            results = service.users().messages().list(
                userId="me",
                q="is:unread is:inbox category:primary newer_than:5m",
                maxResults=5,
            ).execute()
            messages = results.get("messages", [])
            new_msgs = [m for m in messages if m["id"] not in self._seen_email_ids]
            if not new_msgs:
                return

            for m in new_msgs:
                self._seen_email_ids.add(m["id"])

            count = len(new_msgs)
            if count == 1:
                # Get sender name for single email
                msg = service.users().messages().get(
                    userId="me", id=new_msgs[0]["id"], format="metadata",
                    metadataHeaders=["From", "Subject"]
                ).execute()
                headers = msg.get("payload", {}).get("headers", [])
                sender = next((h["value"] for h in headers if h["name"] == "From"), "Someone")
                # Extract display name if available
                sender = sender.split("<")[0].strip().strip('"') or sender
                subject = next((h["value"] for h in headers if h["name"] == "Subject"), "a message")
                self._say(f"You have a new email from {sender}: {subject}")
            else:
                self._say(f"You have {count} new emails in your inbox.")

        except FileNotFoundError:
            pass
        except Exception as e:
            log.debug(f"Proactive email check failed: {e}")

    def _check_fde_weekly_analysis(self) -> None:
        """Run the weekly FDE analysis once each Sunday at 08:00."""
        now = datetime.datetime.now().astimezone()
        if now.weekday() != 6 or now.hour != 8:
            return
        if self._last_fde_weekly_date == now.date():
            return
        if self._is_busy():
            return

        self._last_fde_weekly_date = now.date()
        try:
            from jarvis.core.fde_analyser import FDEAnalyser

            result = FDEAnalyser().run_weekly_analysis()
            summary = result.get("analysis_summary", "Weekly FDE analysis is ready.")
            self._say(f"Weekly FDE analysis is ready. {summary}")
        except Exception as e:
            log.debug(f"Proactive FDE weekly analysis failed: {e}")

    def _loop(self) -> None:
        """Main monitor loop — runs checks on their respective intervals."""
        # Stagger startup so we don't hammer everything at once
        time.sleep(30)

        while True:
            now = time.monotonic()

            self._check_fde_weekly_analysis()

            if now - self._last_calendar_check >= _CALENDAR_INTERVAL:
                self._check_calendar()
                self._last_calendar_check = now

            if now - self._last_battery_check >= _BATTERY_INTERVAL:
                self._check_battery()
                self._last_battery_check = now

            if now - self._last_email_check >= _EMAIL_INTERVAL:
                self._check_email()
                self._last_email_check = now

            time.sleep(15)  # poll cadence — actual work is gated by per-check intervals
