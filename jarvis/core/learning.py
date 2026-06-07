"""
Self-learning engine — JARVIS learns from its own mistakes and user corrections.

Three learning loops:
  1. Routing memory   — tracks which tier handles which query types best
  2. Correction store — user says "no/wrong/I meant" → stores the fix
  3. Pattern advisor  — feeds corrections back into the system prompt
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from pathlib import Path

from jarvis.core.logger import get_logger

log = get_logger(__name__)

_CORRECTION_TRIGGERS = {
    "no,", "no that", "no i", "not that", "i meant", "i mean",
    "wrong", "that's wrong", "that's not", "that's not what",
    "actually,", "actually i", "correction:", "you got it wrong",
    "not what i asked", "misunderstood",
}

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "can", "you", "i", "me", "my", "your", "it", "this", "that",
    "and", "or", "but", "not", "no", "yes", "please", "hey", "jarvis",
    "what", "who", "when", "where", "how", "why", "could", "would",
    "should", "will", "do", "did", "does", "have", "has", "had", "get",
}


class LearningEngine:
    """
    Persistent self-learning layer backed by SQLite.
    Thread-safe. Zero external dependencies.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS routing_memory (
                    id            INTEGER PRIMARY KEY,
                    keywords      TEXT NOT NULL,
                    tier          INTEGER NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    fail_count    INTEGER DEFAULT 0,
                    last_seen     REAL NOT NULL,
                    UNIQUE(keywords, tier)
                );
                CREATE TABLE IF NOT EXISTS corrections (
                    id            INTEGER PRIMARY KEY,
                    bad_response  TEXT,
                    user_query    TEXT,
                    correction    TEXT NOT NULL,
                    timestamp     REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_failures (
                    id            INTEGER PRIMARY KEY,
                    tool_name     TEXT NOT NULL,
                    query_context TEXT,
                    failure_type  TEXT,
                    timestamp     REAL NOT NULL
                );
            """)
            self._conn.commit()

    # ── Keyword helpers ───────────────────────────────────────────────────────

    def _keywords(self, text: str) -> frozenset[str]:
        words = re.findall(r"[a-z]{3,}", text.lower())
        return frozenset(w for w in words if w not in _STOP_WORDS)

    def _kw_str(self, text: str) -> str:
        return " ".join(sorted(self._keywords(text)))

    # ── Routing memory ────────────────────────────────────────────────────────

    def record_routing(self, query: str, tier: int, success: bool) -> None:
        """Call after each routing decision completes."""
        kw = self._kw_str(query)
        if not kw:
            return
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM routing_memory WHERE keywords=? AND tier=?", (kw, tier)
            ).fetchone()
            if row:
                col = "success_count" if success else "fail_count"
                self._conn.execute(
                    f"UPDATE routing_memory SET {col}={col}+1, last_seen=? WHERE id=?",
                    (now, row["id"]),
                )
            else:
                sc, fc = (1, 0) if success else (0, 1)
                self._conn.execute(
                    "INSERT INTO routing_memory(keywords,tier,success_count,fail_count,last_seen) "
                    "VALUES(?,?,?,?,?)",
                    (kw, tier, sc, fc, now),
                )
            self._conn.commit()

    def suggest_tier(self, query: str) -> int | None:
        """Return the tier that historically works best for this query, or None."""
        kws = self._keywords(query)
        if not kws:
            return None

        cutoff = time.time() - 14 * 86400  # last 14 days
        with self._lock:
            rows = self._conn.execute(
                "SELECT keywords, tier, success_count, fail_count FROM routing_memory WHERE last_seen > ?",
                (cutoff,),
            ).fetchall()

        best_tier, best_score = None, 0.0
        for row in rows:
            stored = frozenset(row["keywords"].split())
            overlap = len(kws & stored)
            if overlap == 0:
                continue
            total = row["success_count"] + row["fail_count"]
            if total < 2:
                continue
            rate  = row["success_count"] / total
            score = overlap * rate * min(total, 20)
            if score > best_score and rate >= 0.65:
                best_score = score
                best_tier  = row["tier"]

        if best_tier:
            log.info(f"[Learning] Suggesting Tier {best_tier} based on history (score={best_score:.1f})")
        return best_tier

    # ── Correction detection & storage ────────────────────────────────────────

    def is_correction(self, text: str) -> bool:
        """Return True if the user message looks like a correction."""
        t = text.lower().strip()
        return any(t.startswith(trigger) or trigger in t for trigger in _CORRECTION_TRIGGERS)

    def record_correction(self, user_query: str, bad_response: str, correction: str) -> None:
        """Store a user-provided correction for future learning."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO corrections(bad_response,user_query,correction,timestamp) VALUES(?,?,?,?)",
                (bad_response[:800], user_query[:400], correction[:800], time.time()),
            )
            self._conn.commit()
        log.info(f"[Learning] Correction recorded: {correction[:80]}")

    def get_recent_corrections(self, limit: int = 3) -> list[dict]:
        """Return recent corrections to inject into the system prompt."""
        cutoff = time.time() - 7 * 86400  # last 7 days
        with self._lock:
            rows = self._conn.execute(
                "SELECT user_query, correction FROM corrections WHERE timestamp>? ORDER BY timestamp DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [{"query": r["user_query"], "correction": r["correction"]} for r in rows]

    def corrections_context(self) -> str:
        """Build a system-prompt snippet from recent corrections."""
        corrections = self.get_recent_corrections()
        if not corrections:
            return ""
        lines = ["[SELF-LEARNING — past mistakes to avoid]"]
        for c in corrections:
            lines.append(f"  When asked '{c['query']}', the previous answer was wrong. Correct approach: {c['correction']}")
        lines.append("[End corrections]")
        return "\n".join(lines)

    # ── Tool failure tracking ─────────────────────────────────────────────────

    def record_tool_failure(self, tool_name: str, query_context: str, failure_type: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO tool_failures(tool_name,query_context,failure_type,timestamp) VALUES(?,?,?,?)",
                (tool_name, query_context[:400], failure_type, time.time()),
            )
            self._conn.commit()

    def common_failures(self, days: int = 7) -> list[dict]:
        """Return tools that are failing most often — useful for diagnostics."""
        cutoff = time.time() - days * 86400
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT tool_name, failure_type, COUNT(*) as cnt
                FROM tool_failures WHERE timestamp > ?
                GROUP BY tool_name, failure_type
                ORDER BY cnt DESC LIMIT 10
                """,
                (cutoff,),
            ).fetchall()
        return [{"tool": r["tool_name"], "type": r["failure_type"], "count": r["cnt"]} for r in rows]
