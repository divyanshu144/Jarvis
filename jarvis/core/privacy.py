"""User data rights and privacy housekeeping (docs/privacy/DPIA.md actions A2, A3, A8).

- export_user_data:      everything JARVIS stores about the user, as one JSON file
- forget_user_data:      delete conversation memory, profile, traces, derived tables, logs
- redact_existing_data:  one-off pass that runs pre-hardening rows and logs through the redactor
- capture listeners:     let the HUD show when the screen is captured
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger
from jarvis.core.tracing import redact_text, sanitize_value

log = get_logger(__name__)

_ROOT = Path(__file__).parent.parent.parent
_LOG_DIR = _ROOT / "logs"

# Tables that hold user or third-party content. The FDE career tracker is left alone.
USER_TABLES = (
    "conversations", "user_profile", "agent_runs", "tool_runs", "model_usage",
    "routing_metrics", "validation_failures", "corrections", "tool_failures", "routing_memory",
)

# Free-text columns that may predate write-time redaction.
_TEXT_COLUMNS: dict[str, tuple[str, ...]] = {
    "conversations": ("user_msg", "assistant", "summary"),
    "routing_metrics": ("query",),
    "corrections": ("bad_response", "user_query", "correction"),
    "tool_failures": ("query_context",),
    "validation_failures": ("raw_params", "raw_response"),
    "agent_runs": ("user_message", "final_answer", "error", "tools_executed", "safety_blocks"),
    "tool_runs": ("tool_args_json", "result_summary", "error"),
}

_LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[\w+\] [^:]+: )(.*)$")
_CONTENT_MARKERS = (
    "User: ", "JARVIS: ", "JARVIS (text): ", "Transcribed: ", "Wake word detected (Whisper): ",
    "[Proactive] ", "[Briefing] ", "[Learning] Correction recorded: ",
)
_PLACEHOLDER_RE = re.compile(r"^<\d+ chars, content not logged>$")

_capture_listeners: list[Callable[[], None]] = []


# ── Screen-capture indicator hook ────────────────────────────────────────────

def add_capture_listener(fn: Callable[[], None]) -> None:
    _capture_listeners.append(fn)


def notify_capture() -> None:
    """Call right after the screen is actually captured."""
    for fn in list(_capture_listeners):
        try:
            fn()
        except Exception as e:
            log.debug(f"capture listener failed: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or cfg.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _vacuum(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("VACUUM")
    except sqlite3.OperationalError as e:
        # Another connection (the running app) may hold the DB; rows are deleted either way.
        log.info(f"VACUUM skipped: {e}")


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _open_chroma(chroma_path: str | Path | None):
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(chroma_path or cfg.chroma_path))
        return client.get_or_create_collection(name="conversations", metadata={"hnsw:space": "cosine"})
    except Exception as e:
        log.info(f"Chroma unavailable for privacy operation: {e}")
        return None


def _log_files(log_dir: Path) -> list[Path]:
    if not log_dir.exists():
        return []
    return sorted(p for p in log_dir.glob("jarvis.log*") if p.is_file())


# ── A2: export ───────────────────────────────────────────────────────────────

def export_user_data(db_path: str | Path | None = None, out_dir: str | Path | None = None) -> Path:
    """Write every stored user-data row to a private JSON file and return its path."""
    out = Path(out_dir) if out_dir else Path(cfg.db_path).parent / "exports"
    out.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(out, 0o700)
    except OSError:
        pass

    conn = _connect(db_path)
    try:
        present = _existing_tables(conn)
        payload: dict[str, Any] = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tables": {},
        }
        for table in USER_TABLES:
            if table in present:
                payload["tables"][table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()

    path = out / f"jarvis-export-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.chmod(path, 0o600)
    log.info(f"Privacy export written ({sum(len(v) for v in payload['tables'].values())} rows)")
    return path


# ── A2: forget ───────────────────────────────────────────────────────────────

def forget_user_data(
    db_path: str | Path | None = None,
    chroma_path: str | Path | None = None,
    log_dir: str | Path | None = None,
    semantic: Any = None,
) -> dict[str, int]:
    """Delete stored conversation memory, profile, traces, derived tables, embeddings and logs.

    `semantic` is the running app's SemanticMemory, reused so an open Chroma client is not bypassed.
    """
    counts: dict[str, int] = {}
    conn = _connect(db_path)
    try:
        present = _existing_tables(conn)
        for table in USER_TABLES:
            if table in present:
                counts[table] = int(conn.execute(f"DELETE FROM {table}").rowcount or 0)
        if "conversations_fts" in present:
            conn.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('delete-all')")
        conn.commit()
        _vacuum(conn)  # drop deleted pages so content is not recoverable from the file
    finally:
        conn.close()

    collection = getattr(semantic, "_collection", None) if semantic is not None else None
    if collection is None:
        collection = _open_chroma(chroma_path)
    if collection is not None:
        try:
            ids = collection.get().get("ids", [])
            if ids:
                collection.delete(ids=ids)
            counts["chroma"] = len(ids)
        except Exception as e:
            log.warning(f"Chroma forget failed: {e}")

    removed_logs = 0
    for path in _log_files(Path(log_dir) if log_dir else _LOG_DIR):
        if path.name == "jarvis.log":
            path.write_text("", encoding="utf-8")  # the live handler keeps writing here
        else:
            path.unlink(missing_ok=True)
        removed_logs += 1
    counts["log_files"] = removed_logs
    log.info("Privacy forget completed")
    return counts


# ── A8: redact data written before write-time redaction existed ─────────────

def _redact_cell(table: str, column: str, value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    if table == "validation_failures" and column == "raw_params":
        try:
            return json.dumps(sanitize_value(json.loads(value), limit=200))
        except Exception:
            pass
    return redact_text(value)


def redact_log_text(text: str) -> tuple[str, int]:
    """Replace conversation content in legacy log text with placeholders and redact secrets."""
    out: list[str] = []
    changed = 0
    pending: tuple[str, str, list[str]] | None = None  # (prefix+marker, first body line, continuation)

    def flush() -> None:
        nonlocal pending, changed
        if pending is None:
            return
        head, first, cont = pending
        body = "\n".join([first, *cont])
        if _PLACEHOLDER_RE.match(first.strip()) and not cont:
            out.append(head + first)
        else:
            out.append(f"{head}<{len(body)} chars, content not logged>")
            changed += 1
        pending = None

    for line in text.splitlines():
        m = _LOG_LINE_RE.match(line)
        if m is None:
            if pending is not None:
                pending[2].append(line)  # continuation of a multi-line transcript/reply
                continue
            red = redact_text(line)
            changed += red != line
            out.append(red)
            continue
        flush()
        prefix, message = m.groups()
        marker = next((mk for mk in _CONTENT_MARKERS if message.startswith(mk)), None)
        if marker:
            pending = (prefix + marker, message[len(marker):], [])
            continue
        red = redact_text(line)
        changed += red != line
        out.append(red)
    flush()
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), changed


def redact_existing_data(
    db_path: str | Path | None = None,
    chroma_path: str | Path | None = None,
    log_dir: str | Path | None = None,
) -> dict[str, int]:
    """Rewrite existing DB rows, Chroma documents and log files through the redactor. Keeps history."""
    counts: dict[str, int] = {}
    conn = _connect(db_path)
    try:
        present = _existing_tables(conn)
        for table, columns in _TEXT_COLUMNS.items():
            if table not in present:
                continue
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            cols = [c for c in columns if c in have]
            if not cols:
                continue
            updated = 0
            rows = conn.execute(f"SELECT rowid AS _rid, {', '.join(cols)} FROM {table}").fetchall()
            for row in rows:
                new = {c: _redact_cell(table, c, row[c]) for c in cols}
                if any(new[c] != row[c] for c in cols):
                    sets = ", ".join(f"{c} = ?" for c in cols)
                    conn.execute(f"UPDATE {table} SET {sets} WHERE rowid = ?", [*new.values(), row["_rid"]])
                    updated += 1
            counts[table] = updated
        if "conversations_fts" in present:
            conn.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')")
        conn.commit()
        _vacuum(conn)
    finally:
        conn.close()

    collection = _open_chroma(chroma_path)
    if collection is not None:
        try:
            got = collection.get(include=["documents", "embeddings"])
            ids, docs, embs = got.get("ids", []), got.get("documents", []), got.get("embeddings", [])
            changed_ids, changed_docs, changed_embs = [], [], []
            for i, doc in enumerate(docs or []):
                red = redact_text(doc or "")
                if red != doc:
                    changed_ids.append(ids[i])
                    changed_docs.append(red)
                    changed_embs.append(list(embs[i]))
            if changed_ids:
                collection.update(ids=changed_ids, documents=changed_docs, embeddings=changed_embs)
            counts["chroma"] = len(changed_ids)
        except Exception as e:
            log.warning(f"Chroma redaction failed: {e}")

    changed_lines = 0
    for path in _log_files(Path(log_dir) if log_dir else _LOG_DIR):
        original = path.read_text(encoding="utf-8", errors="replace")
        redacted, n = redact_log_text(original)
        if n:
            tmp = path.with_suffix(path.suffix + ".redacting")
            tmp.write_text(redacted, encoding="utf-8")
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        changed_lines += n
    counts["log_lines"] = changed_lines
    return counts
