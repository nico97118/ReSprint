import requests

from resprint.http import request_error_summary


def test_request_error_summary_includes_type_without_untrusted_message() -> None:
    error = requests.Timeout("Jira serverInfo timed out")

    assert request_error_summary(error) == "Timeout"


def test_request_error_summary_includes_http_status() -> None:
    response = requests.Response()
    response.status_code = 503
    error = requests.HTTPError("Service unavailable", response=response)

    assert request_error_summary(error) == "HTTPError: status=503"
