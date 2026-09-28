"""Log privacy tests: redaction, content placeholders, shared rotating handler."""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.core import logger as logger_module
from jarvis.core.logger import RedactingFilter, content_preview, get_logger


def _record(msg, *args):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_filter_redacts_secrets_in_message_and_args():
    record = _record("key %s and ANTHROPIC_API_KEY=%s", "sk-ant-api03-abcdefghijklmnopqrstuv", "abc123")
    RedactingFilter().filter(record)
    text = record.getMessage()
    assert "sk-ant-api03" not in text
    assert "abc123" not in text
    assert "[REDACTED]" in text


def test_content_preview_hides_conversation_by_default(monkeypatch):
    monkeypatch.setattr(type(logger_module.cfg), "log_conversation_content", property(lambda self: False))
    preview = content_preview("my bank PIN is 4321")
    assert "4321" not in preview
    assert "19 chars" in preview


def test_content_preview_opt_in_truncates(monkeypatch):
    monkeypatch.setattr(type(logger_module.cfg), "log_conversation_content", property(lambda self: True))
    preview = content_preview("x" * 500)
    assert preview.count("x") == 200


def test_loggers_share_one_rotating_file_handler():
    a = get_logger("privacy.test.a")
    b = get_logger("privacy.test.b")
    file_handlers = [h for h in a.handlers if isinstance(h, TimedRotatingFileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0] in b.handlers
    assert file_handlers[0].backupCount >= 1
    assert any(isinstance(f, RedactingFilter) for f in file_handlers[0].filters)
