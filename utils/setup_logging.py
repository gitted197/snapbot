import logging
import os
from logging.handlers import TimedRotatingFileHandler

DEFAULT_LOGFILE = os.getenv("BOT_LOG_FILE", "botlog.log")

def setup_logging(
    logfile: str = DEFAULT_LOGFILE,
    level: int = logging.INFO,
    when: str = "midnight",
    backup_count: int = 14,
) -> logging.Logger:
    """Configure logging once (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)

    if getattr(root, "_configured_by_app", False):
        return root

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    file_handler = TimedRotatingFileHandler(
        logfile,
        when=when,
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    root._configured_by_app = True
    return root

def setLog(logger: logging.Logger) -> logging.Logger:
    """Backward-compatible wrapper used across the project."""
    setup_logging()
    return logger

# Backward-compatible module-level logger reference
logger = logging.getLogger("discord")
setup_logging()
