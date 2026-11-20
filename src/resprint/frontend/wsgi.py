"""Production WSGI application factory for Gunicorn."""

from flask import Flask

from resprint.config import Settings
from resprint.frontend.app import create_app
from resprint.logging import configure_logging


def create_application() -> Flask:
    """Load runtime configuration and create the web application."""
    settings = Settings.from_sources()
    configure_logging(settings.log_level)
    return create_app(settings)
