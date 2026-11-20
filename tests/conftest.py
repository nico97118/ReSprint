"""Keep language-dependent tests independent of collection/execution order."""

import pytest

from resprint.frontend.i18n import configure_language, current_language


@pytest.fixture(autouse=True)
def restore_frontend_language():
    previous = current_language()
    try:
        yield
    finally:
        configure_language(previous)


@pytest.fixture(autouse=True)
def restore_logging_levels():
    import logging

    root = logging.getLogger()
    application = logging.getLogger("resprint")
    previous = root.level, application.level
    try:
        yield
    finally:
        root.setLevel(previous[0])
        application.setLevel(previous[1])
