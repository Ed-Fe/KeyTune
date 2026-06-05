"""Logging bootstrap for KeyTune.

All application loggers live under the "keytune" root logger so that a
single call to setup_logging() controls every module at once.

Usage inside any player module::

    from .log import get_logger
    logger = get_logger(__name__)
    logger.warning("Something went wrong: %s", detail)
"""

import logging
import logging.handlers
import os

_LOGGER_ROOT = "keytune"
_LOG_FILE_NAME = "keytune.log"
_LOG_DIR_NAME = "logs"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file
_BACKUP_COUNT = 3              # keep up to 3 rotated files


def get_log_dir() -> str:
    """Return the directory where log files are stored."""
    from .session import get_app_storage_dir

    return os.path.join(get_app_storage_dir(), _LOG_DIR_NAME)


def setup_logging(enabled: bool, level: str) -> None:
    """Configure (or tear down) the application-wide logging system.

    This function is idempotent and safe to call multiple times — e.g. once
    at startup with default settings and again after the user changes
    preferences.

    Args:
        enabled: When False all logging is silenced via NullHandler.
        level:   One of "DEBUG", "INFO", "WARNING", "ERROR".
                 Unknown values fall back to WARNING.
    """
    root = logging.getLogger(_LOGGER_ROOT)

    # Remove every existing handler before reconfiguring.
    for handler in list(root.handlers):
        try:
            handler.close()
        except Exception:
            pass
        root.removeHandler(handler)

    if not enabled:
        root.addHandler(logging.NullHandler())
        # Disable propagation so nothing leaks to the Python root logger.
        root.propagate = False
        # Use CRITICAL+1 so that even CRITICAL records are silenced.
        root.setLevel(logging.CRITICAL + 1)
        return

    log_level = getattr(logging, level.upper(), logging.WARNING)
    root.setLevel(log_level)
    root.propagate = False

    log_dir = get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, _LOG_FILE_NAME)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the keytune namespace.

    Pass ``__name__`` so the logger path mirrors the module path, e.g.
    ``keytune.player.frames.playback``.
    """
    # Strip the leading "player." package prefix that appears when modules are
    # imported as "player.xxx" so names stay readable in log files.
    short_name = name.removeprefix("player.")
    return logging.getLogger(f"{_LOGGER_ROOT}.{short_name}")
