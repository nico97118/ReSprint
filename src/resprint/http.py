from __future__ import annotations

import logging

import requests

from resprint.logging import exception_summary, log_failure


def log_request_error(
    logger: logging.Logger,
    level: str,
    message: str,
    exc: requests.RequestException,
    *args: object,
) -> None:
    log_failure(logger, level, message, exc, *args, stacklevel=3)


def request_error_summary(exc: requests.RequestException) -> str:
    return exception_summary(exc)
