"""Claude-backed weekly analyser for FDE readiness."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jarvis.core.config import cfg
from jarvis.core.fde_tracker import FDETracker


_ROOT = Path(__file__).parent.parent.parent
_GAPS_JSON = _ROOT / "jarvis" / "data" / "fde_gaps.json"
_RESUME_PATH = Path.home() / "Desktop" / "all projects" / "FDE-learning" / "Div_FDE_resume.pdf"
_SYSTEM_PROMPT = (
    "You are analysing a developer's readiness for a Forward Deployed Engineer role. "
    "Be specific — cite actual commits and files, not generalities."
)


class FDEAnalyser:
    """Gather FDE readiness context and ask Claude for scoring/build plans."""

    def __init__(
        self,
        tracker: FDETracker | None = None,
        db_path: str | Path | None = None,
        gaps_json: str | Path | None = None,
        resume_path: str | Path | None = None,
        projects_dir: str | Path | None = None,
    ) -> None:
        self.gaps_json = Path(gaps_json) if gaps_json else _GAPS_JSON
        self.resume_path = Path(resume_path).expanduser() if resume_path else _RESUME_PATH
        self.projects_dir = Path(projects_dir).expanduser() if projects_dir else cfg.projects_root
        self.tracker = tracker or FDETracker(
            db_path=db_path,
            gaps_json=self.gaps_json,
            projects_dir=self.projects_dir,
        )
        self.db_path = Path(db_path) if db_path else cfg.db_path
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def gather_context(self) -> dict[str, Any]:
        """Collect resume, project, gap, and current-week git activity context."""
        projects = self._project_summaries()
        since = self._last_sunday()
        return {
            "generated_at": dt.datetime.now().astimezone().isoformat(),
            "resume_path": str(self.resume_path),
            "resume_text": self._resume_text(),
            "projects_dir": str(self.projects_dir),
            "projects": projects,
            "gap_statuses": self._gap_statuses(),
            "git_activity_since_last_sunday": {
                "since": since.isoformat(),
                "projects": self._weekly_git_activity(projects, since),
            },
        }

    def run_weekly_analysis(self, dry_run: bool = False) -> dict[str, Any]:
        """Run the weekly Claude analysis and persist the structured result."""
        context = self.gather_context()
        user_message = self._weekly_user_message(context)
        if dry_run:
            return self._dry_run_payload("weekly_analysis", user_message, context)

        result = self._call_claude_json(user_message)
        self._apply_score_updates(result.get("updated_scores", {}))
        self._store_build_plan(
            gap_id=str(result.get("top_priority_gap") or "weekly"),
            plan_text=str(result.get("build_plan", "")),
            triggered_by="weekly_analysis",
            weekly_analysis=True,
        )
        self._store_progress(result)
        return result

    def generate_build_plan(self, gap_id: str, dry_run: bool = False) -> str | dict[str, Any]:
        """Generate and store a focused day-by-day build plan for one gap."""
        data = self._read_gaps_json()
        gap = self._find_gap(data, gap_id)
        if gap is None:
            raise ValueError(f"Unknown FDE gap_id: {gap_id}")

        resume_text = self._resume_text()
        projects = self._project_summaries()
        relevant_project = self._most_relevant_project(gap, projects)
        context = {
            "generated_at": dt.datetime.now().astimezone().isoformat(),
            "gap": gap,
            "resume_skills_section": self._resume_skills_section(resume_text),
            "relevant_project": relevant_project,
        }
        user_message = self._build_plan_user_message(context)
        if dry_run:
            return self._dry_run_payload("build_plan", user_message, context)

        plan = self._call_claude_text(user_message)
        self._store_build_plan(
            gap_id=gap_id,
            plan_text=plan,
            triggered_by=f"gap:{gap_id}",
            weekly_analysis=False,
        )
        return plan

    def _read_gaps_json(self) -> dict[str, Any]:
        return json.loads(self.gaps_json.read_text(encoding="utf-8"))

    def _write_gaps_json(self, data: dict[str, Any]) -> None:
        self.gaps_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _resume_text(self) -> str:
        if not self.resume_path.exists():
            return f"[missing resume: {self.resume_path}]"
        from pypdf import PdfReader

        reader = PdfReader(str(self.resume_path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(page for page in pages if page)

    def _project_summaries(self) -> list[dict[str, Any]]:
        if not self.projects_dir.exists():
            return [{"note": f"{self.projects_dir} not found"}]

        projects: list[dict[str, Any]] = []
        aliases = cfg.project_aliases
        for project in sorted(p for p in self.projects_dir.iterdir() if p.is_dir()):
            if not (project / ".git").is_dir():
                continue
            claude_md = project / "CLAUDE.md"
            projects.append(
                {
                    "name": aliases.get(project.name, project.name),
                    "directory_name": project.name,
                    "path": str(project),
                    "claude_md": self._read_text_if_exists(claude_md),
                    "last_20_commits": self._git_log(project, ["--oneline", "-20"]),
                }
            )
        return projects

    def _gap_statuses(self) -> list[dict[str, Any]]:
        gaps = self._read_gaps_json().get("gaps", [])
        fields = (
            "id",
            "name",
            "status",
            "score",
            "weight",
            "linked_project",
            "deliverable",
            "detection_signals",
            "notes",
        )
        return [{field: gap.get(field) for field in fields} for gap in gaps]

    def _weekly_git_activity(
        self,
        projects: list[dict[str, Any]],
        since: dt.date,
    ) -> list[dict[str, Any]]:
        activity: list[dict[str, Any]] = []
        for project in projects:
            path = project.get("path")
            if not path:
                continue
            commits = self._git_log(Path(path), ["--oneline", "--since", since.isoformat()])
            activity.append(
                {
                    "name": project.get("name"),
                    "path": path,
                    "commits_since_last_sunday": commits,
                }
            )
        return activity

    def _last_sunday(self) -> dt.date:
        today = dt.date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        return today - dt.timedelta(days=days_since_sunday)

    def _git_log(self, project: Path, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(project), "log", *args],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception as exc:
            return f"[git log failed: {exc}]"
        if result.returncode != 0:
            return f"[git log failed: {result.stderr.strip()}]"
        return result.stdout.strip()

    def _read_text_if_exists(self, path: Path, max_chars: int = 8000) -> str:
        if not path.exists():
            return f"[missing: {path.name}]"
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def _weekly_user_message(self, context: dict[str, Any]) -> str:
        schema = {
            "updated_scores": {"gap_id": "new_score"},
            "overall_readiness": "int",
            "weekly_delta": "int",
            "top_priority_gap": "gap_id",
            "build_plan": "day by day plan as markdown",
            "analysis_summary": "2-3 sentences",
            "regressing_gaps": ["gap_id"],
        }
        return (
            "Analyse this FDE readiness context and return only valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Context:\n"
            f"{json.dumps(context, indent=2, ensure_ascii=False)}"
        )

    def _build_plan_user_message(self, context: dict[str, Any]) -> str:
        return (
            "Create a focused day-by-day markdown build plan for this single FDE gap. "
            "Use the resume skills and project evidence; cite concrete files or commits when available.\n\n"
            f"{json.dumps(context, indent=2, ensure_ascii=False)}"
        )

    def _dry_run_payload(
        self,
        operation: str,
        user_message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "dry_run": True,
            "operation": operation,
            "model": cfg.claude_model,
            "system_prompt": _SYSTEM_PROMPT,
            "user_message": user_message,
            "context": context,
        }

    def _call_claude_json(self, user_message: str) -> dict[str, Any]:
        text = self._call_claude_text(user_message)
        return self._parse_json_response(text)

    def _call_claude_text(self, user_message: str) -> str:
        if not cfg.anthropic_key:
            raise RuntimeError("ANTHROPIC_API_KEY or config.yaml api_keys.anthropic is required.")
        from anthropic import Anthropic

        client = Anthropic(api_key=cfg.anthropic_key)
        response = client.messages.create(
            model=cfg.claude_model,
            max_tokens=cfg.claude_max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return "\n".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ).strip()

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(text[start:end + 1])

    def _apply_score_updates(self, updated_scores: dict[str, Any]) -> list[dict[str, Any]]:
        if not updated_scores:
            return []

        data = self._read_gaps_json()
        changes: list[dict[str, Any]] = []
        now = time.time()
        for gap_id, raw_score in updated_scores.items():
            gap = self._find_gap(data, str(gap_id))
            if gap is None:
                continue
            new_score = int(raw_score)
            old_score = int(gap.get("score", 0))
            if new_score == old_score:
                continue

            gap["score"] = max(0, min(100, new_score))
            self._conn.execute(
                """
                UPDATE fde_gaps
                SET score=?, last_updated=?
                WHERE gap_id=?
                """,
                (gap["score"], now, str(gap_id)),
            )
            status_result = self.tracker.update_gap_status(
                str(gap_id),
                str(gap.get("status", "not_in_plan")),
                "weekly_analysis_score_change",
            )
            changes.append(
                {
                    "gap_id": str(gap_id),
                    "old_score": old_score,
                    "new_score": gap["score"],
                    "status_update": status_result,
                }
            )

        self._write_gaps_json(data)
        self._conn.commit()
        return changes

    def _store_build_plan(
        self,
        gap_id: str,
        plan_text: str,
        triggered_by: str,
        weekly_analysis: bool,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO fde_build_plans(
                gap_id, plan_text, generated_at, triggered_by, weekly_analysis
            ) VALUES(?,?,?,?,?)
            """,
            (gap_id, plan_text, time.time(), triggered_by, int(weekly_analysis)),
        )
        self._conn.commit()

    def _store_progress(self, result: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO fde_progress(
                overall_score, gap_scores_json, calculated_at,
                weekly_delta, analysis_summary
            ) VALUES(?,?,?,?,?)
            """,
            (
                float(result.get("overall_readiness", 0)),
                json.dumps(result.get("updated_scores", {}), sort_keys=True),
                time.time(),
                float(result.get("weekly_delta", 0)),
                str(result.get("analysis_summary", "")),
            ),
        )
        self._conn.commit()

    def _find_gap(self, data: dict[str, Any], gap_id: str) -> dict[str, Any] | None:
        return next((gap for gap in data.get("gaps", []) if gap.get("id") == gap_id), None)

    def _resume_skills_section(self, resume_text: str) -> str:
        lower = resume_text.lower()
        start = lower.find("technical skills")
        if start == -1:
            return resume_text[:2500]
        end_candidates = [
            idx for marker in ("education", "experience", "projects")
            if (idx := lower.find(marker, start + 1)) != -1
        ]
        end = min(end_candidates) if end_candidates else min(len(resume_text), start + 2500)
        return resume_text[start:end].strip()

    def _most_relevant_project(
        self,
        gap: dict[str, Any],
        projects: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        real_projects = [project for project in projects if project.get("path")]
        if not real_projects:
            return None

        linked = str(gap.get("linked_project") or "").lower()
        if linked:
            for project in real_projects:
                if linked in str(project.get("name", "")).lower():
                    return project

        signals = [str(signal).lower() for signal in gap.get("detection_signals", [])]
        best_project = real_projects[0]
        best_score = -1
        for project in real_projects:
            haystack = json.dumps(project, ensure_ascii=False).lower()
            score = sum(1 for signal in signals if signal and signal in haystack)
            if score > best_score:
                best_project = project
                best_score = score
        return best_project


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run FDE readiness analysis.")
    parser.add_argument("--dry-run", action="store_true", help="Print Claude payload without API call.")
    parser.add_argument("--gap-id", help="Generate a focused build plan for this gap instead of weekly analysis.")
    args = parser.parse_args()

    analyser = FDEAnalyser()
    if args.gap_id:
        result = analyser.generate_build_plan(args.gap_id, dry_run=args.dry_run)
    else:
        result = analyser.run_weekly_analysis(dry_run=args.dry_run)
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
