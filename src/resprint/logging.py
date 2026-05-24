from __future__ import annotations

import logging

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def configure_logging(level: str = "error") -> None:
    logging.basicConfig(
        level=LOG_LEVELS[level],
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("resprint").setLevel(LOG_LEVELS[level])


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
