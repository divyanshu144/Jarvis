"""FDE readiness tracker tool for JARVIS."""

from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jarvis.core.config import cfg
from jarvis.core.fde_analyser import FDEAnalyser
from jarvis.core.fde_tracker import FDETracker


_ROOT = Path(__file__).parent.parent.parent
_GAPS_JSON = _ROOT / "jarvis" / "data" / "fde_gaps.json"

DEFINITION = {
    "name": "fde_tracker",
    "description": (
        "Track FDE readiness, get build plans, update gap progress, and check what "
        "to work on next for Forward Deployed Engineer preparation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_status",
                    "get_build_plan",
                    "mark_done",
                    "what_to_work_on",
                    "weekly_summary",
                ],
            },
            "gap_name": {
                "type": "string",
                "description": "Fuzzy gap name such as 'MCP gap', 'auth', or 'LLM security'.",
            },
            "confirmed": {
                "type": "boolean",
                "description": "Set true after the user answers the recall quiz for voice/both gaps.",
            },
        },
        "required": ["action"],
    },
}


_QUIZ_BY_GAP_ID = {
    "01": "Quick check: what is the difference between a workflow and an agent, and when would you choose each?",
    "03": "Quick check: name two context-engineering tactics that reduce hallucination or improve retrieval grounding.",
    "05": "Quick check: explain how chunking, embedding search, and reranking work together in a RAG pipeline.",
    "07": "Quick check: what is prompt injection, and what are two practical mitigations for tool-using LLM apps?",
    "08": "Quick check: in a regulated financial-services AI pilot, what model-risk or compliance concerns would you raise first?",
    "11": "Quick check: how would you scope a four-week FDE pilot from a vague customer problem?",
}


class FDETool:
    """High-level tool facade over FDETracker and FDEAnalyser."""

    def __init__(self) -> None:
        self.tracker = FDETracker()
        self.analyser = FDEAnalyser(tracker=self.tracker)
        self.tracker.load_gaps()

    def execute(self, action: str, gap_name: str = "", confirmed: bool = False) -> str:
        if action == "get_status":
            return self._json(self.get_status())
        if action == "get_build_plan":
            return self.get_build_plan(gap_name)
        if action == "mark_done":
            return self._json(self.mark_done(gap_name, confirmed=confirmed))
        if action == "what_to_work_on":
            return self._json(self.what_to_work_on())
        if action == "weekly_summary":
            return self._json(self.weekly_summary())
        return f"Unknown fde_tracker action: {action}"

    def get_status(self) -> dict[str, Any]:
        summary = self.tracker.get_summary()
        gaps = self._read_gaps()
        return {
            "overall_score": summary.get("overall_score"),
            "weekly_delta": summary.get("weekly_delta"),
            "top_3_open_gaps": [self._gap_brief(gap) for gap in self._top_open_gaps(gaps, limit=3)],
            "this_weeks_recommended_focus": self._latest_focus(),
        }

    def get_build_plan(self, gap_name: str) -> str:
        gap = self._match_gap(gap_name)
        try:
            plan = self.analyser.generate_build_plan(gap["id"])
            return str(plan)
        except Exception as exc:
            plan = self._fallback_build_plan(gap, exc)
            self._store_fallback_plan(gap["id"], plan)
            return plan

    def mark_done(self, gap_name: str, confirmed: bool = False) -> dict[str, Any]:
        gap = self._match_gap(gap_name)
        detection_type = str(gap.get("detection_type", "auto"))
        if detection_type in {"voice", "both"} and not confirmed:
            return {
                "marked_done": False,
                "gap_id": gap["id"],
                "gap_name": gap.get("name"),
                "requires_confirmation": True,
                "quiz_question": _QUIZ_BY_GAP_ID.get(
                    gap["id"],
                    f"Quick check: explain the core idea behind {gap.get('name', 'this FDE gap')} in your own words.",
                ),
            }

        result = self.tracker.mark_reading_gap_done(gap["id"])
        new_score = self.tracker.calculate_overall_score()
        return {
            "marked_done": True,
            "gap_id": gap["id"],
            "gap_name": gap.get("name"),
            "tracker_result": result,
            "overall_score": new_score,
            "message": f"Marked reading progress for {gap.get('name')} and recalculated FDE readiness to {new_score}.",
        }

    def what_to_work_on(self) -> dict[str, Any]:
        summary = self.tracker.get_summary()
        priority = summary.get("top_priority_gap") or {}
        latest_plan = self._latest_plan_for_gap(str(priority.get("id") or ""))
        return {
            "top_priority_gap": priority.get("name"),
            "deliverable": priority.get("deliverable"),
            "day_1": self._extract_day_1(latest_plan.get("plan_text", "")) if latest_plan else "No build plan stored yet. Ask for a build plan for this gap first.",
        }

    def weekly_summary(self) -> dict[str, Any]:
        row = self._current_week_progress_row()
        weekly_plan = self._latest_weekly_plan()
        if row is None:
            return {
                "available": False,
                "message": "No FDE weekly progress row exists for the current week yet.",
                "top_priority_gap": weekly_plan.get("gap_id") if weekly_plan else None,
            }
        return {
            "available": True,
            "score": row["overall_score"],
            "delta": row["weekly_delta"],
            "analysis_summary": row["analysis_summary"],
            "top_priority_gap": weekly_plan.get("gap_id") if weekly_plan else (self.tracker.get_summary().get("top_priority_gap") or {}).get("id"),
            "calculated_at": dt.datetime.fromtimestamp(row["calculated_at"]).isoformat(),
        }


    def _fallback_build_plan(self, gap: dict[str, Any], error: Exception) -> str:
        resources = gap.get("resources", [])
        resource_lines = [
            f"- {resource.get('title', 'Resource')}: {resource.get('url', '')}"
            for resource in resources[:4]
        ] or ["- Review the existing project README, CLAUDE.md, and current implementation evidence."]
        return "\n".join([
            f"Note: Claude build-plan generation failed ({error}). This is a local fallback plan.",
            "",
            f"# {gap.get('name')} Build Plan",
            "",
            f"Target deliverable: {gap.get('deliverable', 'Ship concrete evidence for this gap.')}",
            "",
            "## Day 1 - Scope and evidence audit",
            "Confirm the exact artifact to ship, inspect the linked project, and list the missing files, demos, tests, and README evidence.",
            "",
            "## Day 2 - Build the smallest working slice",
            "Implement the core capability behind the gap with a narrow happy path and one local verification command.",
            "",
            "## Day 3 - Add reliability and safety checks",
            "Add focused tests, error handling, and security notes appropriate to the gap.",
            "",
            "## Day 4 - Package interview-ready evidence",
            "Update README or portfolio notes with screenshots, commands, architecture notes, and a concise demo script.",
            "",
            "## Resources",
            *resource_lines,
        ])

    def _store_fallback_plan(self, gap_id: str, plan_text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO fde_build_plans(
                    gap_id, plan_text, generated_at, triggered_by, weekly_analysis
                ) VALUES(?,?,?,?,0)
                """,
                (gap_id, plan_text, dt.datetime.now().timestamp(), "fde_tool_fallback"),
            )
            conn.commit()

    def _read_gaps(self) -> list[dict[str, Any]]:
        data = json.loads(_GAPS_JSON.read_text(encoding="utf-8"))
        return list(data.get("gaps", []))

    def _match_gap(self, query: str) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("gap_name is required for this action.")

        gaps = self._read_gaps()
        normalized_query = self._normalize(query)
        aliases = {
            "mcp gap": "04",
            "mcp": "04",
            "skills": "04",
            "auth": "09",
            "oauth": "09",
            "saml": "09",
            "oidc": "09",
            "security": "07",
            "prompt injection": "07",
            "owasp": "07",
            "aws": "10",
            "cloud": "10",
            "eval": "06",
            "evaluation": "06",
            "rag": "05",
            "portfolio": "12",
            "consulting": "11",
            "fde motion": "11",
            "enterprise": "08",
        }
        if normalized_query in aliases:
            return self._gap_by_id(gaps, aliases[normalized_query])

        scored: list[tuple[float, dict[str, Any]]] = []
        for gap in gaps:
            haystack_parts = [
                gap.get("id", ""),
                gap.get("name", ""),
                gap.get("deliverable", ""),
                gap.get("linked_project") or "",
                " ".join(str(signal) for signal in gap.get("detection_signals", [])),
            ]
            haystack = self._normalize(" ".join(haystack_parts))
            ratio = difflib.SequenceMatcher(None, normalized_query, haystack).ratio()
            token_hits = sum(1 for token in normalized_query.split() if token in haystack)
            scored.append((ratio + token_hits * 0.25, gap))

        best_score, best_gap = max(scored, key=lambda item: item[0])
        if best_score <= 0:
            raise ValueError(f"No FDE gap matched '{query}'.")
        return best_gap

    def _gap_by_id(self, gaps: list[dict[str, Any]], gap_id: str) -> dict[str, Any]:
        for gap in gaps:
            if gap.get("id") == gap_id:
                return gap
        raise ValueError(f"Unknown FDE gap id: {gap_id}")

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _top_open_gaps(self, gaps: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        open_gaps = [gap for gap in gaps if gap.get("status") not in {"done", "strong"}]
        return sorted(
            open_gaps,
            key=lambda gap: float(gap.get("weight", 0)) * (100 - float(gap.get("score", 0))),
            reverse=True,
        )[:limit]

    def _gap_brief(self, gap: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": gap.get("id"),
            "name": gap.get("name"),
            "status": gap.get("status"),
            "score": gap.get("score"),
            "deliverable": gap.get("deliverable"),
        }

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(cfg.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _latest_plan_for_gap(self, gap_id: str) -> dict[str, Any] | None:
        if not gap_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM fde_build_plans
                WHERE gap_id=?
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (gap_id,),
            ).fetchone()
        return dict(row) if row else None

    def _latest_weekly_plan(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM fde_build_plans
                WHERE weekly_analysis=1
                ORDER BY generated_at DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                row = conn.execute(
                    """
                    SELECT * FROM fde_build_plans
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        return dict(row) if row else None

    def _latest_focus(self) -> dict[str, Any] | None:
        plan = self._latest_weekly_plan()
        if plan is None:
            return None
        gaps = self._read_gaps()
        gap = next((g for g in gaps if g.get("id") == plan.get("gap_id")), None)
        return {
            "gap_id": plan.get("gap_id"),
            "gap_name": gap.get("name") if gap else plan.get("gap_id"),
            "day_1": self._extract_day_1(plan.get("plan_text", "")),
        }

    def _current_week_progress_row(self) -> sqlite3.Row | None:
        start = self._start_of_week_timestamp()
        with self._conn() as conn:
            return conn.execute(
                """
                SELECT * FROM fde_progress
                WHERE calculated_at >= ?
                ORDER BY calculated_at DESC
                LIMIT 1
                """,
                (start,),
            ).fetchone()

    def _start_of_week_timestamp(self) -> float:
        today = dt.date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        sunday = today - dt.timedelta(days=days_since_sunday)
        return dt.datetime.combine(sunday, dt.time.min).timestamp()

    def _extract_day_1(self, plan_text: str) -> str:
        if not plan_text.strip():
            return "No day 1 plan text found."
        lines = [line.strip() for line in plan_text.splitlines() if line.strip()]
        capture: list[str] = []
        capturing = False
        for line in lines:
            lowered = line.lower()
            if re.search(r"\bday\s*1\b|\bday\s*one\b", lowered):
                capturing = True
                capture.append(line)
                continue
            if capturing and re.search(r"\bday\s*[2-9]\b|\bday\s*two\b", lowered):
                break
            if capturing:
                capture.append(line)
        if capture:
            return " ".join(capture[:4])
        return lines[0]

    def _json(self, value: Any) -> str:
        return json.dumps(value, indent=2, ensure_ascii=False)


def execute(action: str, gap_name: str = "", confirmed: bool = False) -> str:
    return FDETool().execute(action=action, gap_name=gap_name, confirmed=confirmed)


def _main() -> None:
    calls = [
        ("get_status", {}, "GET STATUS"),
        ("weekly_summary", {}, "WEEKLY SUMMARY"),
        ("mark_done", {"gap_name": "enterprise", "confirmed": False}, "MARK DONE QUIZ"),
        ("get_build_plan", {"gap_name": "MCP gap"}, "GET BUILD PLAN"),
        ("what_to_work_on", {}, "WHAT TO WORK ON"),
    ]
    for action, params, label in calls:
        print()
        print(f"=== {label} ===")
        try:
            print(execute(action=action, **params))
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    _main()
