"""
Logging for kokoro-dj.

Writes to both stdout and a rotating log file at:
  ~/.kokoro-dj/dj.log  (default)
  or $KOKORO_DJ_LOG if set

Usage:
    from utils.log import get_logger
    log = get_logger()
    log.info("Playing: %s", title)
    log.warning("Sarvam API slow: %s", e)
    log.error("LLM failed: %s", e)

Tail in real time:
    tail -f ~/.kokoro-dj/dj.log
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_logger = None

LOG_DIR = os.path.expanduser("~/.kokoro-dj")
LOG_FILE = os.environ.get("KOKORO_DJ_LOG", os.path.join(LOG_DIR, "dj.log"))
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str = "kokoro-dj") -> logging.Logger:
    """
    Return (and lazily initialise) the shared DJ logger.
    Safe to call multiple times — returns same logger.
    """
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # ── File handler — rotating, max 5MB × 3 files ────────────────────────
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(fh)

    # ── Stdout handler — INFO and above only ──────────────────────────────
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(sh)

    _logger = logger
    return logger


def log_path() -> str:
    return LOG_FILE
