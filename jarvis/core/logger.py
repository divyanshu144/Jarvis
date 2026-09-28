"""Structured logging setup for the entire application.

Privacy defaults (see docs/privacy/DPIA.md):
  - every record is secret-redacted before it reaches console or file
  - conversation content is logged as a length placeholder unless
    `logging.conversation_content: true` is set in config.yaml
  - logs/jarvis.log rotates daily and keeps `logging.retention_days` files
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from jarvis.core.config import cfg


_ROOT = Path(__file__).parent.parent.parent
_LOG_FILE = _ROOT / "logs" / "jarvis.log"
_LOG_FILE.parent.mkdir(exist_ok=True)
try:
    os.chmod(_LOG_FILE.parent, 0o700)
except OSError:
    pass

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"
_PREVIEW_CHARS = 200


class RedactingFilter(logging.Filter):
    """Redact API keys, tokens, and cookies from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Lazy import: tracing itself uses get_logger.
            from jarvis.core.tracing import redact_text

            record.msg = redact_text(record.getMessage())
            record.args = None
        except Exception:
            pass
        return True


def content_preview(text: object) -> str:
    """Return what may be logged for user/assistant content (transcripts, replies)."""
    value = str(text or "")
    if cfg.log_conversation_content:
        return repr(value[:_PREVIEW_CHARS] + ("…" if len(value) > _PREVIEW_CHARS else ""))
    return f"<{len(value)} chars, content not logged>"


def _build_handlers() -> tuple[logging.Handler, logging.Handler]:
    redact = RedactingFilter()

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(_FMT, _DATE))
    sh.addFilter(redact)

    # One shared file handler: per-logger handlers on the same file break rotation.
    fh = TimedRotatingFileHandler(
        _LOG_FILE,
        when="midnight",
        backupCount=max(1, cfg.log_retention_days),
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE))
    fh.addFilter(redact)
    try:
        os.chmod(_LOG_FILE, 0o600)
    except OSError:
        pass
    return sh, fh


_STREAM_HANDLER, _FILE_HANDLER = _build_handlers()


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to both console and logs/jarvis.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addHandler(_STREAM_HANDLER)
    logger.addHandler(_FILE_HANDLER)
    logger.propagate = False  # prevent double-logging via root logger
    return logger
