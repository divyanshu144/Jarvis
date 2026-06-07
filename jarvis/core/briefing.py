"""
Morning briefing — delivered automatically at startup or on request.
Composes: greeting + weather + calendar + email count + FDE readiness + battery.
"""

from __future__ import annotations

import datetime
import threading
from typing import Callable

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)


class MorningBriefing:
    """
    Delivers a personalised morning (or any-time) briefing.
    Auto-delivers once per day at startup if the hour is 6–11.
    """

    def __init__(
        self,
        speak_fn: Callable[[str], None],
        is_busy: Callable[[], bool],
    ) -> None:
        self._speak   = speak_fn
        self._is_busy = is_busy
        self._delivered_date: datetime.date | None = None

    def check_startup(self) -> None:
        """Call once at startup — delivers briefing if it's morning and not yet delivered today."""
        now = datetime.datetime.now()
        today = now.date()
        if self._delivered_date == today:
            return
        if not (6 <= now.hour <= 11):
            return
        self._delivered_date = today
        threading.Thread(target=self._deliver_async, daemon=True).start()

    def deliver_now(self) -> str:
        """Build and return briefing text (blocking). Also sets delivered flag."""
        self._delivered_date = datetime.datetime.now().date()
        return self._compose()

    # ── Delivery ──────────────────────────────────────────────────────────────

    def _deliver_async(self) -> None:
        import time
        time.sleep(3)  # let startup TTS finish first
        while self._is_busy():
            time.sleep(0.5)
        text = self._compose()
        log.info(f"[Briefing] {text}")
        self._speak(text)

    def _compose(self) -> str:
        now  = datetime.datetime.now()
        hour = now.hour
        name = cfg.user_name

        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        parts = [f"{greeting}{', ' + name if name else ''}."]

        # Weather
        try:
            from jarvis.tools.weather import execute as wx
            w = wx()
            # Trim to one line
            parts.append(w.split("\n")[0])
        except Exception:
            pass

        # Calendar
        try:
            from jarvis.tools._google_auth import TOKEN_PATH
            if TOKEN_PATH.exists():
                from jarvis.tools.google_calendar import execute as cal
                events_txt = cal(action="get_today")
                if "No events" in events_txt or "clear" in events_txt.lower():
                    parts.append("Your schedule is clear today.")
                else:
                    count = events_txt.count("•")
                    parts.append(f"You have {count} event{'s' if count != 1 else ''} on your calendar today.")
        except Exception:
            pass

        # Email
        try:
            from jarvis.tools._google_auth import TOKEN_PATH
            if TOKEN_PATH.exists():
                from jarvis.tools.gmail import execute as gm
                count_txt = gm(action="get_unread_count")
                parts.append(count_txt)
        except Exception:
            pass

        fde_section = self._fde_section()
        if fde_section:
            parts.append(fde_section)

        # Battery
        try:
            import psutil
            b = psutil.sensors_battery()
            if b and not b.power_plugged and b.percent < 30:
                parts.append(f"Battery is at {b.percent:.0f}%, you may want to plug in.")
        except Exception:
            pass

        return " ".join(parts)

    def _fde_section(self) -> str:
        try:
            from jarvis.core.fde_tracker import FDETracker

            tracker = FDETracker()
            tracker.load_gaps()

            now = datetime.datetime.now()
            if now.weekday() == 6 and not self._has_current_weekly_analysis(tracker):
                try:
                    from jarvis.core.fde_analyser import FDEAnalyser

                    result = FDEAnalyser(tracker=tracker).run_weekly_analysis()
                    score = result.get("overall_readiness")
                    top_gap_name = self._fde_gap_name(tracker, str(result.get("top_priority_gap") or ""))
                    summary = str(result.get("analysis_summary", "")).strip()
                    if score is not None and top_gap_name:
                        return f"Your FDE readiness is {float(score):.0f}%. This week's focus: {top_gap_name}. {summary}".strip()
                except Exception as e:
                    log.debug(f"FDE weekly analysis for briefing failed: {e}")

            summary_data = tracker.get_summary()
            latest = tracker._latest_progress()
            top_gap = summary_data.get("top_priority_gap") or {}
            analysis_summary = str(latest["analysis_summary"] if latest else "").strip()
            score = float(summary_data.get("overall_score", 0))
            top_name = str(top_gap.get("name") or "no active gap")
            return f"Your FDE readiness is {score:.0f}%. This week's focus: {top_name}. {analysis_summary}".strip()
        except Exception as e:
            log.debug(f"FDE briefing section skipped: {e}")
            return ""

    def _has_current_weekly_analysis(self, tracker) -> bool:
        start = self._start_of_current_week()
        row = tracker._conn.execute(
            """
            SELECT 1 FROM fde_build_plans
            WHERE weekly_analysis=1 AND generated_at >= ?
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (start,),
        ).fetchone()
        return row is not None

    def _start_of_current_week(self) -> float:
        today = datetime.date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        sunday = today - datetime.timedelta(days=days_since_sunday)
        return datetime.datetime.combine(sunday, datetime.time.min).timestamp()

    def _fde_gap_name(self, tracker, gap_id: str) -> str:
        if not gap_id:
            return ""
        data = tracker._read_json()
        for gap in data.get("gaps", []):
            if str(gap.get("id")) == gap_id:
                return str(gap.get("name", gap_id))
        return gap_id
