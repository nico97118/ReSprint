"""Production WSGI application factory for Gunicorn."""

from flask import Flask

from resprint.config import Settings
from resprint.frontend.app import create_app
from resprint.logging import configure_logging, get_logger, log_failure

logger = get_logger(__name__)


def create_application() -> Flask:
    """Load runtime configuration and create the web application."""
    try:
        settings = Settings.from_sources()
        configure_logging(settings.log_level)
        logger.info("Creating WSGI application")
        app = create_app(settings)
    except (ValueError, OSError) as exc:
        log_failure(logger, "error", "WSGI application startup failed", exc)
        raise
    logger.info("WSGI application ready")
    return app
