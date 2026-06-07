"""
Routing metrics logger — persists per-query routing decisions to SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

from jarvis.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class RoutingResult:
    """Returned by the Router for every query."""
    response: str
    tier_used: int                          # 1, 2, or 3
    tiers_attempted: list[int]              # e.g. [1, 2] if Tier 1 failed
    escalation_reason: Optional[str]        # None if Tier 1 succeeded
    wall_time_ms: float                     # total time from route() call to return
    query: str


class MetricsLogger:
    """Logs routing results to the jarvis.db SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self._db, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS routing_metrics (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp          REAL NOT NULL,
                query              TEXT NOT NULL,
                tier_used          INTEGER NOT NULL,
                tiers_attempted    TEXT NOT NULL,
                escalation_reason  TEXT,
                wall_time_ms       REAL NOT NULL,
                success            INTEGER NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def log(self, result: RoutingResult) -> None:
        try:
            conn = sqlite3.connect(self._db, check_same_thread=False)
            conn.execute(
                "INSERT INTO routing_metrics VALUES (NULL,?,?,?,?,?,?,?)",
                (
                    time.time(),
                    result.query,
                    result.tier_used,
                    json.dumps(result.tiers_attempted),
                    result.escalation_reason,
                    result.wall_time_ms,
                    1,
                ),
            )
            conn.commit()
            conn.close()
            log.debug(
                f"Metrics: tier={result.tier_used} "
                f"escalation={result.escalation_reason} "
                f"time={result.wall_time_ms:.0f}ms"
            )
        except Exception as e:
            log.warning(f"Metrics log failed: {e}")

    def summary(self, n: int = 20) -> list[dict]:
        """Return last N routing decisions for debugging."""
        try:
            conn = sqlite3.connect(self._db, check_same_thread=False)
            cur = conn.execute(
                "SELECT * FROM routing_metrics ORDER BY timestamp DESC LIMIT ?", (n,)
            )
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []
