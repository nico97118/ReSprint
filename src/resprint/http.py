from __future__ import annotations

import logging

import requests


def log_request_error(
    logger: logging.Logger,
    level: str,
    message: str,
    exc: requests.RequestException,
    *args: object,
) -> None:
    rendered_message = message % args if args else message
    log_method = getattr(logger, level)
    log_method("%s: %s", rendered_message, request_error_summary(exc))


def request_error_summary(exc: requests.RequestException) -> str:
    parts = [type(exc).__name__]
    if str(exc):
        parts.append(str(exc))
    if exc.response is not None:
        parts.append(f"status={exc.response.status_code}")
    return ": ".join(parts)
