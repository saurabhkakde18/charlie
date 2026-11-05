"""
core/logger.py — Rotating file logger for Charlie.

Logs to logs/charlie.log with a rotating file handler (max 5 MB, 5 backups).
Ensures all file writes use UTF-8 and never raises on logging errors.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Force UTF-8 on stdout and stderr with replace errors so emojis/non-Latin never crash logging
for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "charlie.log"

_logger: logging.Logger | None = None


def get_logger(name: str = "charlie") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger.getChild(name) if name != "charlie" else _logger

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("charlie")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid adding duplicate handlers if re-imported
    if not logger.handlers:
        # Rotating File Handler (UTF-8, 5 MB, 5 backups)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Stream Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "[%(levelname)s] %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    _logger = logger
    return logger.getChild(name) if name != "charlie" else _logger


def log_exception(exc: BaseException, context: str = "") -> None:
    """Safe exception logging with traceback."""
    lg = get_logger("exception")
    msg = f"Exception in {context}: {exc}" if context else f"Exception: {exc}"
    lg.error(msg, exc_info=exc)

