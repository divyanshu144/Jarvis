"""Structured logging setup for the entire application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


_ROOT = Path(__file__).parent.parent.parent
_LOG_FILE = _ROOT / "logs" / "jarvis.log"
_LOG_FILE.parent.mkdir(exist_ok=True)

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to both console and logs/jarvis.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(_FMT, _DATE))

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE))

    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.propagate = False  # prevent double-logging via root logger
    return logger
