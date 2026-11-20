import logging

import pytest

from resprint.logging import configure_logging, get_logger


def test_configure_logging_sets_resprint_logger_level() -> None:
    configure_logging("debug")

    assert logging.getLogger("resprint").level == logging.DEBUG


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("resprint.report")

    assert logger.name == "resprint.report"


def test_failure_logs_context_type_and_status_without_remote_details(caplog):
    import requests

    from resprint.logging import log_failure

    response = requests.Response()
    response.status_code = 401
    error = requests.HTTPError(
        "https://user:secret@jira.test/?api.token=secret\nAuthorization: Bearer secret",
        response=response,
    )
    with caplog.at_level(logging.WARNING, logger="resprint.test"):
        log_failure(
            get_logger("resprint.test"),
            "warning",
            "Issue %s incomplete",
            error,
            "ABC-1",
        )
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.message == "Issue ABC-1 incomplete: HTTPError: status=401"
    assert (
        record.funcName
        == "test_failure_logs_context_type_and_status_without_remote_details"
    )
    assert record.exc_info is None
    assert "secret" not in caplog.text
    assert "https://" not in caplog.text


def test_configure_logging_keeps_host_handlers_and_scopes_verbosity():
    import json
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json, logging
from resprint.logging import configure_logging
configure_logging('debug')
root = logging.getLogger()
handler = root.handlers[0]
configure_logging('info')
print(json.dumps({
    'root': root.level,
    'app': logging.getLogger('resprint').level,
    'same_handler': root.handlers == [handler],
}))
logging.getLogger('resprint.test').info('application event')
logging.getLogger('urllib3.connectionpool').debug('third party detail')
""",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout) == {
        "root": logging.WARNING,
        "app": logging.INFO,
        "same_handler": True,
    }
    assert "application event" in result.stderr
    assert "third party detail" not in result.stderr


@pytest.mark.parametrize("client_name", ["jira", "tempo", "phorge"])
def test_client_debug_logs_never_include_credentials_or_query_values(
    client_name, monkeypatch, caplog
):
    from unittest.mock import Mock

    from resprint.helpers.jira import JiraClient
    from resprint.helpers.phorge import PhorgeClient
    from resprint.helpers.tempo import TempoTeamWorklogClient

    clients = {
        "jira": JiraClient,
        "tempo": TempoTeamWorklogClient,
        "phorge": PhorgeClient,
    }
    secret = "credential-that-must-stay-private"
    with caplog.at_level(logging.DEBUG, logger="resprint"):
        client = clients[client_name](f"https://user:{secret}@service.test", secret)
        response = Mock()
        response.json.return_value = {"ok": True}
        if client_name == "phorge":
            monkeypatch.setattr(client.session, "post", Mock(return_value=response))
            client._post("/api/query", {"api.token": secret, "query": secret})
        else:
            monkeypatch.setattr(client.session, "get", Mock(return_value=response))
            client._get("/api/query", params={"jql": secret, "username": secret})
    assert "DEBUG" in caplog.text
    assert "api/query" in caplog.text
    assert secret not in caplog.text
    assert "https://user:" not in caplog.text


@pytest.mark.parametrize(
    "level, expected", [("warning", logging.WARNING), ("error", logging.ERROR)]
)
def test_failure_severity_belongs_to_the_calling_operation(level, expected, caplog):
    from resprint.logging import log_failure

    with caplog.at_level(logging.WARNING, logger="resprint.test"):
        log_failure(
            get_logger("resprint.test"),
            level,
            "Operation unavailable",
            RuntimeError("private payload"),
        )
    (record,) = caplog.records
    assert record.levelno == expected
    assert record.message == "Operation unavailable: RuntimeError"
    assert record.exc_info is None
    assert "private payload" not in caplog.text
