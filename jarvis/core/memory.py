"""
Memory system — three layers:
  1. Working memory  : last N conversation turns passed as LLM messages (in-context)
  2. Episodic memory : SQLite full-text search over past sessions (cross-session recall)
  3. User profile    : persistent facts about the user (name, preferences, habits)

Semantic (ChromaDB) is used when available; SQLite keyword search is the fallback.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)


# ── 1. Working memory (in-context rolling buffer) ─────────────────────────────

class ShortTermMemory:
    """Rolling buffer of the last N turns as LLM-ready message dicts."""

    def __init__(self, limit: int = 20) -> None:
        self._buf: deque[dict[str, Any]] = deque(maxlen=limit)

    def add(self, role: str, content: str | list) -> None:
        self._buf.append({"role": role, "content": content})

    def messages(self) -> list[dict[str, Any]]:
        """Return all buffered messages — pass directly to LLM as conversation history."""
        return list(self._buf)

    def recent(self, n: int = 6) -> list[dict[str, Any]]:
        """Return the last n messages (default 6 = 3 user+assistant pairs)."""
        msgs = list(self._buf)
        return msgs[-n:] if len(msgs) > n else msgs

    def clear(self) -> None:
        self._buf.clear()


# ── 2. Episodic + profile memory (SQLite) ────────────────────────────────────

class LongTermMemory:
    """Persistent conversation history and user-profile storage with FTS recall."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or cfg.db_path
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                timestamp   REAL NOT NULL,
                user_msg    TEXT NOT NULL,
                assistant   TEXT NOT NULL,
                summary     TEXT,
                embedding   TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
                USING fts5(user_msg, assistant, content='conversations', content_rowid='rowid');
            CREATE TRIGGER IF NOT EXISTS conv_ai AFTER INSERT ON conversations BEGIN
                INSERT INTO conversations_fts(rowid, user_msg, assistant)
                VALUES (new.rowid, new.user_msg, new.assistant);
            END;
            CREATE TABLE IF NOT EXISTS user_profile (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def save_turn(self, user_msg: str, assistant_msg: str, summary: str = "") -> str:
        turn_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO conversations VALUES (?,?,?,?,?,?)",
            (turn_id, time.time(), user_msg, assistant_msg, summary, None),
        )
        self._conn.commit()
        return turn_id

    def keyword_recall(self, query: str, k: int = 3) -> list[str]:
        """Return up to k past turns whose text matches keywords in query."""
        try:
            # Extract only plain alphabetic words — FTS5 chokes on punctuation/apostrophes
            import re
            words = re.findall(r"[a-zA-Z]{4,}", query)
            if not words:
                return []
            fts_query = " OR ".join(words[:8])
            cur = self._conn.execute(
                """
                SELECT c.user_msg, c.assistant
                FROM conversations_fts f
                JOIN conversations c ON c.rowid = f.rowid
                WHERE conversations_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, k),
            )
            rows = cur.fetchall()
            return [f"User: {r['user_msg']}\nJARVIS: {r['assistant']}" for r in rows]
        except Exception as e:
            log.warning(f"keyword_recall failed: {e}")
            return []

    def get_recent(self, n: int = 10) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?", (n,)
        )
        return cur.fetchall()

    def set_profile(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO user_profile VALUES (?,?)", (key, value)
        )
        self._conn.commit()

    def get_profile(self, key: str) -> str | None:
        cur = self._conn.execute(
            "SELECT value FROM user_profile WHERE key=?", (key,)
        )
        row = cur.fetchone()
        return row["value"] if row else None

    def all_profile(self) -> dict[str, str]:
        cur = self._conn.execute("SELECT key, value FROM user_profile")
        return {r["key"]: r["value"] for r in cur.fetchall()}


# ── 3. Semantic memory (ChromaDB — optional upgrade) ─────────────────────────

class SemanticMemory:
    """Vector-similarity recall over past conversations. Falls back gracefully."""

    def __init__(self) -> None:
        self._ready = False
        self._collection = None
        self._encoder = None
        self._init()

    def _init(self) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            client = chromadb.PersistentClient(path=str(cfg.chroma_path))
            self._collection = client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"},
            )
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self._ready = True
            log.info("Semantic memory ready (ChromaDB + MiniLM)")
        except Exception as e:
            log.warning(f"Semantic memory unavailable: {e}")

    def add(self, turn_id: str, text: str) -> None:
        if not self._ready:
            return
        try:
            emb = self._encoder.encode(text).tolist()
            self._collection.upsert(ids=[turn_id], embeddings=[emb], documents=[text])
        except Exception as e:
            log.warning(f"SemanticMemory.add failed: {e}")

    def query(self, text: str, k: int | None = None) -> list[str]:
        if not self._ready:
            return []
        try:
            k = k or cfg.top_k_similar
            emb = self._encoder.encode(text).tolist()
            results = self._collection.query(
                query_embeddings=[emb],
                n_results=min(k, self._collection.count() or 1),
            )
            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            log.warning(f"SemanticMemory.query failed: {e}")
            return []


# ── Unified facade ────────────────────────────────────────────────────────────

class Memory:
    """Single access point for all memory layers."""

    def __init__(self) -> None:
        self.short = ShortTermMemory(cfg.short_term_limit)
        self.long = LongTermMemory()
        self.semantic = SemanticMemory()

    def add_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Save a completed turn to long-term + semantic memory."""
        turn_id = self.long.save_turn(user_msg, assistant_msg)
        self.semantic.add(turn_id, f"User: {user_msg}\nAssistant: {assistant_msg}")

    def recall_context(self, query: str) -> str:
        """
        Return relevant past turns as a formatted string.
        Uses ChromaDB if available, falls back to SQLite keyword search.
        """
        similar = self.semantic.query(query) or self.long.keyword_recall(query)
        if not similar:
            return ""
        snippets = "\n---\n".join(similar[:cfg.top_k_similar])
        return f"[Relevant past context]\n{snippets}\n[End context]"

    def build_system_prompt(self, base: str) -> str:
        """Inject user profile and any learned preferences into the base prompt."""
        profile = self.long.all_profile()
        name = profile.get("name", cfg.user_name) or "User"
        lines = [f"The user's name is {name}."]
        for key, val in profile.items():
            if key != "name":
                lines.append(f"{key.capitalize()}: {val}")
        return base + "\n\n" + "\n".join(lines)

    def working_messages(self, n: int = 6) -> list[dict]:
        """
        Return last n messages as properly formatted LLM messages.
        Pass these between the system prompt and the current user query.
        """
        return self.short.recent(n)
