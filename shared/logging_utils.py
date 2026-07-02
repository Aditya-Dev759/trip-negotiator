import logging
import os
import sys

_CONFIGURED = False


def configure_logging(level: str = None) -> None:
    """Configure root logging once for the whole process.

    Reads LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR) if `level` isn't
    passed explicitly; defaults to INFO. Safe to call repeatedly -- only
    configures once per process.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level_value = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(level_value)
    root.handlers = [handler]

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
