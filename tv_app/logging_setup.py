"""Application logging to a persistent error log file."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .paths import ERROR_LOG_FILE

_CONFIGURED = False
_LOG_PATH: Optional[Path] = None

# Keep enough history for diagnosing intermittent device issues.
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def setup_logging(log_path: Path = ERROR_LOG_FILE) -> Path:
    """Configure root logging once; returns the error log path."""
    global _CONFIGURED, _LOG_PATH
    if _CONFIGURED:
        return _LOG_PATH or log_path

    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Unexpected crashes also land in the same file.
    sys.excepthook = _excepthook

    _CONFIGURED = True
    _LOG_PATH = log_path
    logging.getLogger(__name__).info("Logging initialized (%s)", log_path)
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call setup_logging() at process start."""
    return logging.getLogger(name)


def log_path() -> Path:
    return _LOG_PATH or ERROR_LOG_FILE


def _excepthook(exc_type, exc, tb) -> None:
    try:
        logging.getLogger("tv_app").error(
            "Unhandled exception",
            exc_info=(exc_type, exc, tb),
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)
