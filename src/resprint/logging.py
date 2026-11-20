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
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s:%(funcName)s] %(message)s",
    )
    logging.getLogger("resprint").setLevel(LOG_LEVELS[level])


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def exception_summary(exc: BaseException) -> str:
    """Describe failures without remote messages, URLs, payloads or credentials."""
    summary = type(exc).__name__
    response = getattr(exc, "response", None)
    if response is not None:
        summary += f": status={response.status_code}"
    return summary


def log_failure(
    logger: logging.Logger,
    level: str,
    message: str,
    exc: BaseException,
    *args: object,
    stacklevel: int = 2,
) -> None:
    """Log a contextual failure once, using only a safe exception summary.

    The caller owns severity: warning for a partial result, error when the
    operation cannot complete. Context must not contain request/response bodies.
    """
    logger.log(
        LOG_LEVELS[level],
        "%s: %s",
        message % args if args else message,
        exception_summary(exc),
        stacklevel=stacklevel,
    )
