"""API boundaries: partial pages, malformed payloads and legacy review states."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from resprint.helpers.phorge import PhorgeAPIError, PhorgeClient


@pytest.fixture
def client():
    return PhorgeClient("https://phorge.test/", "test-token", request_timeout=4)


def test_empty_queries_never_call_the_api(client, monkeypatch):
    post = Mock(side_effect=AssertionError("No API call expected"))
    monkeypatch.setattr(client, "_post", post)
    assert client.query_revisions(()) == {}
    assert client.query_repository_names(()) == {}
    post.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1])
def test_client_rejects_nonpositive_timeout(timeout):
    with pytest.raises(ValueError, match="request_timeout"):
        PhorgeClient("https://phorge.test", "test", request_timeout=timeout)


@pytest.mark.parametrize("payload", [None, [], {}, {"result": {}}, {"result": None}])
def test_invalid_base_query_is_rejected_instead_of_looking_like_no_reviews(
    client, monkeypatch, payload
):
    monkeypatch.setattr(client, "_post", Mock(return_value=payload))
    with pytest.raises(ValueError, match="Phorge response"):
        client.query_revisions((1,))


@pytest.mark.parametrize(
    "created, expected",
    [
        ("1700000000", datetime.fromtimestamp(1700000000, UTC)),
        (0, None),
        (-1, None),
        (True, None),
        (None, None),
        ("invalid", None),
        ("9" * 100, None),
    ],
)
def test_revision_parsing_skips_invalid_entries_and_handles_bad_dates(
    client, monkeypatch, created, expected
):
    post = Mock(
        side_effect=[
            {
                "result": [
                    None,
                    "invalid",
                    {},
                    {"id": "invalid"},
                    {"id": 0},
                    {"id": "1", "statusName": "Closed", "dateCreated": created},
                ]
            },
            {"result": {"data": []}},
        ]
    )
    monkeypatch.setattr(client, "_post", post)
    statuses = client.query_revisions((1,))
    assert set(statuses) == {1}
    assert statuses[1].state == "closed"
    assert statuses[1].created_at == expected


@pytest.mark.parametrize(
    "payload", [None, {}, {"result": []}, {"result": {"data": {}}}]
)
def test_malformed_reviewer_search_preserves_base_status(client, monkeypatch, payload):
    monkeypatch.setattr(
        client,
        "_post",
        Mock(
            side_effect=[
                {"result": [{"id": 1, "status": "2"}]},
                payload,
            ]
        ),
    )
    status = client.query_revisions((1,))[1]
    assert status.state == "open"
    assert status.validation_count is None
    assert status.ready_to_close is None


@pytest.mark.parametrize("refs", [None, [None], [{"reviewerPHID": "A"}]])
def test_invalid_reviewer_attachment_never_establishes_readiness(
    client, monkeypatch, refs
):
    monkeypatch.setattr(
        client,
        "_post",
        Mock(
            side_effect=[
                {"result": [{"id": 1, "status": "2"}]},
                {
                    "result": {
                        "data": [
                            {"id": 1, "attachments": {"reviewers": {"reviewers": refs}}}
                        ]
                    }
                },
            ]
        ),
    )
    status = client.query_revisions((1,))[1]
    assert status.validation_count is None
    assert status.reviewers is None
    assert status.ready_to_close is None


def test_reviewer_search_ignores_foreign_rows_and_stops_repeated_cursor(
    client, monkeypatch
):
    page = {
        "result": {
            "data": [
                None,
                {"id": 999},
                {"id": 1, "attachments": {"reviewers": {"reviewers": []}}},
            ],
            "cursor": {"after": "same"},
        }
    }
    post = Mock(side_effect=[{"result": [{"id": 1, "status": "2"}]}, page, page])
    monkeypatch.setattr(client, "_post", post)
    statuses = client.query_revisions((1,))
    assert set(statuses) == {1}
    assert statuses[1].validation_count == 0
    assert statuses[1].ready_to_close is False
    assert post.call_count == 3
    assert post.call_args.args[1]["after"] == "same"


@pytest.mark.parametrize("names", [None, [], {}, {"result": []}, {"result": {"A": {}}}])
def test_invalid_name_lookup_keeps_author_phid_and_review_status(
    client, monkeypatch, names
):
    monkeypatch.setattr(
        client,
        "_post",
        Mock(
            side_effect=[
                {"result": [{"id": 1, "status": "3", "authorPHID": "A"}]},
                {"result": {"data": []}},
                names,
            ]
        ),
    )
    status = client.query_revisions((1,))[1]
    assert status.state == "closed"
    assert status.author_phid == "A"
    assert status.author_name is None


@pytest.mark.parametrize(
    "second_page", [requests.Timeout(), None, {"result": {"data": {}}}]
)
def test_repository_lookup_preserves_previous_page_on_failure(
    client, monkeypatch, second_page
):
    post = Mock(
        side_effect=[
            {
                "result": {
                    "data": [None, {}, {"phid": "R1", "fields": {"name": "Core"}}],
                    "cursor": {"after": "next"},
                }
            },
            second_page,
        ]
    )
    monkeypatch.setattr(client, "_post", post)
    assert client.query_repository_names(("R1", "R2")) == {"R1": "Core"}
    assert post.call_count == 2
    assert post.call_args.args[1]["after"] == "next"


def test_repository_lookup_stops_repeated_cursor(client, monkeypatch):
    page = {
        "result": {
            "data": [{"phid": "R1", "fields": {"name": "Core"}}],
            "cursor": {"after": "same"},
        }
    }
    post = Mock(side_effect=[page, page])
    monkeypatch.setattr(client, "_post", post)
    assert client.query_repository_names(("R1",)) == {"R1": "Core"}
    assert post.call_count == 2


@pytest.mark.parametrize(
    "error_code, expected",
    [
        ("ERR-INVALID-AUTH", "ERR-INVALID-AUTH"),
        ("https://secret.test/token", "CONDUIT_ERROR"),
        ({"secret": "token"}, "CONDUIT_ERROR"),
    ],
)
def test_conduit_errors_expose_only_sanitized_codes(
    client, monkeypatch, error_code, expected
):
    response = Mock()
    response.json.return_value = {"error_code": error_code, "error_info": "secret body"}
    post = Mock(return_value=response)
    monkeypatch.setattr(client.session, "post", post)
    with pytest.raises(PhorgeAPIError) as error:
        client.query_revisions((1,))
    assert str(error.value) == expected
    response.raise_for_status.assert_called_once()
    post.assert_called_once_with(
        "https://phorge.test/api/differential.query",
        data={"api.token": "test-token", "ids[0]": 1},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=4,
    )
