import logging

from resprint.logging import configure_logging, get_logger


def test_configure_logging_sets_resprint_logger_level() -> None:
    configure_logging("debug")

    assert logging.getLogger("resprint").level == logging.DEBUG


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("resprint.report")

    assert logger.name == "resprint.report"
