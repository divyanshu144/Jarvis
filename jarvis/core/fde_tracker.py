"""FDE readiness tracker backed by the existing JARVIS SQLite database."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jarvis.core.config import cfg


_ROOT = Path(__file__).parent.parent.parent
_GAPS_JSON = _ROOT / "jarvis" / "data" / "fde_gaps.json"


class FDETracker:
    """Track FDE learning gaps, project evidence, plans, and progress history."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        gaps_json: str | Path | None = None,
        projects_dir: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else cfg.db_path
        self.gaps_json = Path(gaps_json) if gaps_json else _GAPS_JSON
        self.projects_dir = Path(projects_dir).expanduser() if projects_dir else cfg.projects_root
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fde_gaps (
                gap_id               TEXT PRIMARY KEY,
                name                 TEXT NOT NULL,
                status               TEXT NOT NULL,
                score                INTEGER NOT NULL,
                linked_project       TEXT,
                last_signal_detected TEXT,
                last_updated         REAL NOT NULL,
                notes                TEXT
            );

            CREATE TABLE IF NOT EXISTS fde_build_plans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                gap_id          TEXT NOT NULL,
                plan_text       TEXT NOT NULL,
                generated_at    REAL NOT NULL,
                triggered_by    TEXT,
                weekly_analysis INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS fde_progress (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                overall_score    REAL NOT NULL,
                gap_scores_json  TEXT NOT NULL,
                calculated_at    REAL NOT NULL,
                weekly_delta     REAL NOT NULL,
                analysis_summary TEXT
            );
            """
        )
        self._conn.commit()

    def _read_json(self) -> dict[str, Any]:
        return json.loads(self.gaps_json.read_text(encoding="utf-8"))

    def _write_json(self, data: dict[str, Any]) -> None:
        self.gaps_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _db_gap_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM fde_gaps").fetchone()
        return int(row["n"])

    def _json_gap(self, data: dict[str, Any], gap_id: str) -> dict[str, Any] | None:
        for gap in data.get("gaps", []):
            if gap.get("id") == gap_id:
                return gap
        return None

    def load_gaps(self) -> dict[str, Any]:
        """Load fde_gaps.json into SQLite on first run."""
        data = self._read_json()
        if self._db_gap_count() > 0:
            return {"loaded": 0, "skipped": True, "reason": "fde_gaps already populated"}

        now = time.time()
        rows = []
        for gap in data.get("gaps", []):
            rows.append(
                (
                    gap["id"],
                    gap.get("name", ""),
                    gap.get("status", "not_in_plan"),
                    int(gap.get("score", 0)),
                    gap.get("linked_project"),
                    None,
                    now,
                    gap.get("notes", ""),
                )
            )
        self._conn.executemany(
            """
            INSERT INTO fde_gaps(
                gap_id, name, status, score, linked_project,
                last_signal_detected, last_updated, notes
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        self._conn.commit()
        return {"loaded": len(rows), "skipped": False}

    def _project_git_log(self, project: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(project), "log", "--oneline", "-50"],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout

    def scan_projects(self) -> dict[str, Any]:
        """Scan project git logs and record matching detection signals."""
        data = self._read_json()
        if not self.projects_dir.exists():
            return {"projects_scanned": 0, "matches": [], "reason": f"{self.projects_dir} not found"}

        projects = [p for p in self.projects_dir.iterdir() if p.is_dir() and (p / ".git").is_dir()]
        now = time.time()
        matches: list[dict[str, str]] = []
        json_changed = False

        for project in projects:
            log_text = self._project_git_log(project)
            if not log_text:
                continue
            haystack = f"{project.name}\n{log_text}".lower()
            for gap in data.get("gaps", []):
                for signal in gap.get("detection_signals", []):
                    needle = str(signal).lower()
                    if needle and needle in haystack:
                        old_status = str(gap.get("status", "not_in_plan"))
                        new_status = "in_progress" if old_status in {"not_started", "not_in_plan", "needs_depth"} else old_status
                        if new_status != old_status:
                            gap["status"] = new_status
                            notes = str(gap.get("notes", "")).rstrip()
                            note = f" Signal '{signal}' detected in {project.name}; moved from {old_status} to in_progress."
                            gap["notes"] = (notes + note).strip()
                            json_changed = True

                        match = {
                            "gap_id": gap["id"],
                            "gap_name": gap.get("name", ""),
                            "project": project.name,
                            "signal": signal,
                        }
                        matches.append(match)
                        self._conn.execute(
                            """
                            UPDATE fde_gaps
                            SET status=?,
                                notes=?,
                                last_signal_detected=?,
                                linked_project=COALESCE(linked_project, ?),
                                last_updated=?
                            WHERE gap_id=?
                            """,
                            (
                                gap.get("status", old_status),
                                gap.get("notes", ""),
                                f"{project.name}: {signal}",
                                project.name,
                                now,
                                gap["id"],
                            ),
                        )
                        break
        if json_changed:
            self._write_json(data)
        self._conn.commit()
        return {"projects_scanned": len(projects), "matches": matches}

    def update_gap_status(self, gap_id: str, new_status: str, source: str) -> dict[str, Any]:
        """Update a gap status in SQLite and JSON; return the exact changes."""
        data = self._read_json()
        gap = self._json_gap(data, gap_id)
        if gap is None:
            return {"updated": False, "error": f"Unknown gap_id: {gap_id}"}

        old_status = gap.get("status")
        old_notes = gap.get("notes", "")
        changed: dict[str, Any] = {
            "updated": old_status != new_status,
            "gap_id": gap_id,
            "old_status": old_status,
            "new_status": new_status,
            "source": source,
        }
        if old_status == new_status:
            return changed

        note_suffix = f" Status changed from {old_status} to {new_status} via {source}."
        gap["status"] = new_status
        gap["notes"] = (old_notes.rstrip() + note_suffix).strip()
        self._write_json(data)

        now = time.time()
        self._conn.execute(
            """
            UPDATE fde_gaps
            SET status=?, notes=?, last_updated=?
            WHERE gap_id=?
            """,
            (new_status, gap["notes"], now, gap_id),
        )
        self._conn.commit()
        changed["notes_appended"] = note_suffix.strip()
        return changed

    def calculate_overall_score(self) -> float:
        """Calculate weighted score across all JSON gaps and store progress."""
        data = self._read_json()
        gaps = data.get("gaps", [])
        total_weight = sum(float(g.get("weight", 0)) for g in gaps) or 1.0
        weighted = sum(float(g.get("weight", 0)) * float(g.get("score", 0)) for g in gaps)
        overall = round(weighted / total_weight, 2)
        scores = {g["id"]: int(g.get("score", 0)) for g in gaps}

        previous = self._conn.execute(
            "SELECT overall_score FROM fde_progress ORDER BY calculated_at DESC LIMIT 1"
        ).fetchone()
        weekly_delta = round(overall - float(previous["overall_score"]), 2) if previous else 0.0

        summary = self._analysis_summary(data, overall, weekly_delta)
        self._conn.execute(
            """
            INSERT INTO fde_progress(
                overall_score, gap_scores_json, calculated_at,
                weekly_delta, analysis_summary
            ) VALUES(?,?,?,?,?)
            """,
            (overall, json.dumps(scores, sort_keys=True), time.time(), weekly_delta, summary),
        )
        self._conn.commit()
        return overall

    def _latest_progress(self) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM fde_progress ORDER BY calculated_at DESC LIMIT 1"
        ).fetchone()

    def _analysis_summary(self, data: dict[str, Any], overall: float, weekly_delta: float) -> str:
        priority = self._top_priority_gap(data)
        name = priority.get("name", "none") if priority else "none"
        return f"Overall FDE readiness is {overall:.2f}. Weekly delta is {weekly_delta:+.2f}. Top priority: {name}."

    def _top_priority_gap(self, data: dict[str, Any]) -> dict[str, Any] | None:
        candidates = [
            g for g in data.get("gaps", [])
            if g.get("status") not in {"done", "strong"}
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda g: float(g.get("weight", 0)) * (100 - float(g.get("score", 0))))

    def get_summary(self) -> dict[str, Any]:
        """Return overall score, weekly delta, status counts, and top priority."""
        data = self._read_json()
        latest = self._latest_progress()
        if latest is None:
            overall = self.calculate_overall_score()
            latest = self._latest_progress()
        else:
            overall = float(latest["overall_score"])
        counts = Counter(g.get("status", "unknown") for g in data.get("gaps", []))
        priority = self._top_priority_gap(data)
        return {
            "overall_score": overall,
            "weekly_delta": float(latest["weekly_delta"]) if latest else 0.0,
            "gaps_by_status": dict(sorted(counts.items())),
            "top_priority_gap": {
                "id": priority.get("id"),
                "name": priority.get("name"),
                "status": priority.get("status"),
                "score": priority.get("score"),
                "weight": priority.get("weight"),
                "deliverable": priority.get("deliverable"),
            } if priority else None,
        }

    def mark_reading_gap_done(self, gap_id: str) -> dict[str, Any]:
        """Mark reading resources for a gap done after a voice check-in."""
        data = self._read_json()
        gap = self._json_gap(data, gap_id)
        if gap is None:
            return {"updated": False, "error": f"Unknown gap_id: {gap_id}"}

        changed_titles = []
        for resource in gap.get("resources", []):
            if resource.get("type") == "read" and not resource.get("done"):
                resource["done"] = True
                changed_titles.append(resource.get("title", ""))

        old_status = gap.get("status")
        if changed_titles and old_status in {"not_in_plan", "needs_depth"}:
            gap["status"] = "in_progress"
        gap["notes"] = (
            gap.get("notes", "").rstrip()
            + f" Reading check-in confirmed via voice for gap {gap_id}."
        ).strip()
        self._write_json(data)

        now = time.time()
        self._conn.execute(
            """
            UPDATE fde_gaps
            SET status=?, notes=?, last_updated=?
            WHERE gap_id=?
            """,
            (gap.get("status"), gap.get("notes", ""), now, gap_id),
        )
        self._conn.commit()
        return {
            "updated": bool(changed_titles),
            "gap_id": gap_id,
            "marked_done": changed_titles,
            "old_status": old_status,
            "new_status": gap.get("status"),
        }


if __name__ == "__main__":
    tracker = FDETracker()
    tracker.load_gaps()
    tracker.scan_projects()
    print(tracker.get_summary())
