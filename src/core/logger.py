"""
Structured logging with file + console transports.

This replaces the ad-hoc ``print()`` calls scattered across the original code
with a single configured logger. A rotating file handler keeps disk usage
bounded, and the console handler keeps container logs (Railway/Docker) working.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from . import config

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger("travel_agent")
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    root.setLevel(level)
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console transport
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # File transport (best-effort: skip if the directory is not writable)
    try:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        file_path = os.path.join(config.LOG_DIR, config.LOG_FILE)
        file_handler = RotatingFileHandler(
            file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover
        root.warning("File logging disabled (%s)", exc)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger under the ``travel_agent`` root."""
    _configure_root()
    return logging.getLogger(f"travel_agent.{name}")
