import logging
from logging.handlers import RotatingFileHandler

from .config import LOG_FILE, LOG_LEVEL, LOG_DIR

_handler_attached = False

def configure_logging() -> None:
    """
    Attach a rotating file handler so scrape logs land on disk.
    """
    global _handler_attached
    if _handler_attached:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL.upper())
    root_logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root_logger.addHandler(console)
    _handler_attached = True
