"""Client contracts for incomplete API pages and Jira payload variations."""

from datetime import date
from functools import partial
from unittest.mock import Mock

import pytest

from resprint.helpers.jira import JiraClient, _parse_issue
from resprint.models import Issue


@pytest.fixture
def client():
    return JiraClient("https://jira.test", "test-token")


def raw_issue(key="ABC-1", **fields):
    return {"id": key, "key": key, "fields": fields}


def test_unsupported_rest_version_is_rejected():
    with pytest.raises(ValueError, match="rest_api_version"):
        JiraClient("https://jira.test", "test", rest_api_version="4")


@pytest.mark.parametrize("method", ["list_boards", "list_board_sprints"])
def test_agile_pagination_loads_all_pages_without_premature_stop(
    client, monkeypatch, method
):
    if method == "list_boards":
        items = [{"id": 1}, {"id": 2}]
        call = partial(client.list_boards, "ABC")
    else:
        items = [
            {"id": i, "startDate": "2026-05-01", "endDate": "2026-05-15"}
            for i in (1, 2)
        ]
        call = partial(client.list_board_sprints, 42)
    get = Mock(
        side_effect=[
            {"values": [item], "isLast": i == 1} for i, item in enumerate(items)
        ]
    )
    monkeypatch.setattr(client, "_get", get)
    assert [item.id for item in call()] == [1, 2]
    assert [call.kwargs["params"]["startAt"] for call in get.call_args_list] == [0, 1]


@pytest.mark.parametrize("method", ["list_boards", "list_board_sprints"])
def test_empty_nonfinal_agile_page_terminates_instead_of_looping(
    client, monkeypatch, method
):
    get = Mock(return_value={"values": [], "isLast": False})
    monkeypatch.setattr(client, "_get", get)
    result = (
        client.list_boards("ABC")
        if method == "list_boards"
        else client.list_board_sprints(42)
    )
    assert result == []
    assert get.call_count == 1


def test_issue_lookup_batches_requests_preserves_order_and_keeps_missing_keys_out(
    client, monkeypatch, caplog
):
    keys = [f"ABC-{i}" for i in range(1, 102)]
    search = Mock(
        side_effect=[
            [
                Issue(str(i), f"ABC-{i}", "Ticket", "Done", "done", None)
                for i in range(100, 0, -1)
            ],
            [],
        ]
    )
    monkeypatch.setattr(client, "search_issues", search)
    with caplog.at_level("WARNING"):
        issues = client.get_issues_by_keys(keys)
    assert [issue.key for issue in issues] == keys[:-1]
    assert search.call_count == 2
    assert search.call_args_list[0].args[0] == f"key in ({', '.join(keys[:100])})"
    assert search.call_args_list[1].args[0] == "key in (ABC-101)"
    assert "no details for 1 requested issues" in caplog.text


def test_parent_enrichment_preserves_missing_and_unrelated_parents(
    client, monkeypatch, caplog
):
    issues = [
        Issue("1", "ABC-1", "Ticket", "Open", "new", None, parent="ABC-99"),
        Issue("2", "ABC-2", "Ticket", "Open", "new", None),
    ]
    monkeypatch.setattr(client, "get_issues_by_keys", Mock(return_value=[]))
    with caplog.at_level("WARNING"):
        assert client.enrich_parent_summaries(issues) == issues
    assert "Parent summary missing for ABC-99" in caplog.text


def test_search_activity_requests_custom_fields_once_and_retains_valid_embedded_entries(
    client, monkeypatch, caplog
):
    client.parent_field = "custom_parent"
    client.review_fields = ("custom_review", "custom_parent")
    get = Mock(
        return_value={
            "total": 1,
            "issues": [
                raw_issue(
                    custom_parent={"key": "ABC-99", "name": "Parent"},
                    custom_review="D12",
                    comment={
                        "comments": [
                            {"id": "invalid"},
                            {
                                "id": "1",
                                "created": "2026-05-01",
                                "body": "Useful comment",
                            },
                        ]
                    },
                )
                | {
                    "changelog": {
                        "histories": [
                            {},
                            {
                                "created": "2026-05-01",
                                "items": [{"field": "status", "toString": "Done"}],
                            },
                        ],
                        "startAt": "invalid",
                        "maxResults": None,
                        "total": "3",
                    }
                }
            ],
        }
    )
    monkeypatch.setattr(client, "_get", get)
    with caplog.at_level("WARNING"):
        (issue,) = client.search_issues("project = ABC", include_activity=True)
    requested = get.call_args.kwargs["params"]["fields"].split(",")
    assert requested.count("custom_parent") == 1
    assert "custom_review" in requested and "comment" in requested
    assert issue.parent == "ABC-99 - Parent"
    assert issue.reviews[0].id == 12
    assert [comment.body for comment in issue.comments] == ["Useful comment"]
    assert [change.field for change in issue.changes] == ["status"]
    assert "Ignoring invalid Jira comment" in caplog.text
    assert "Ignoring invalid Jira changelog history" in caplog.text
    assert "Embedded Jira changelog is truncated" in caplog.text


@pytest.mark.parametrize(
    "changelog", ["invalid", {"histories": "invalid"}, {"histories": []}]
)
def test_unusable_changelog_yields_no_changes(client, monkeypatch, changelog):
    monkeypatch.setattr(client, "_get", Mock(return_value={"changelog": changelog}))
    assert client.get_issue_changes("ABC-1", date(2026, 5, 1), date(2026, 5, 15)) == []


def test_comment_pagination_filters_dates_without_stopping_at_invalid_entries(
    client, monkeypatch
):
    get = Mock(
        side_effect=[
            {"total": 3, "comments": [{"id": "1", "created": "2026-04-30"}]},
            {"total": 3, "comments": [{"id": "bad"}]},
            {
                "total": 3,
                "comments": [{"id": "2", "created": "2026-05-15", "body": "Last day"}],
            },
        ]
    )
    monkeypatch.setattr(client, "_get", get)
    comments = client.get_issue_comments("ABC-1", date(2026, 5, 1), date(2026, 5, 15))
    assert [comment.body for comment in comments] == ["Last day"]
    assert [call.kwargs["params"]["startAt"] for call in get.call_args_list] == [
        0,
        1,
        2,
    ]


@pytest.mark.parametrize(
    "parent, expected",
    [
        ({"key": "ABC-9"}, "ABC-9"),
        ({"fields": {"summary": "Parent name"}}, "Parent name"),
        ({"name": "Parent name"}, "Parent name"),
        ({}, None),
        (42, None),
        ("", None),
    ],
)
def test_custom_parent_shapes_fall_back_without_losing_issue(parent, expected):
    issue = _parse_issue(raw_issue(custom_parent=parent), parent_field="custom_parent")
    assert issue.parent == expected
    assert issue.key == "ABC-1"


@pytest.mark.parametrize(
    "parent, expected",
    [
        ("not-an-object", None),
        ({"key": "ABC-9"}, "ABC-9"),
        ({"key": "ABC-9", "fields": {"summary": "Parent name"}}, "ABC-9 - Parent name"),
        ({"key": "ABC-9", "fields": {"issuetype": {"name": "Epic"}}}, "ABC-9"),
    ],
)
def test_standard_parent_shapes(parent, expected):
    assert _parse_issue(raw_issue(parent=parent)).parent == expected


def test_fix_versions_accept_names_and_objects_but_ignore_unusable_entries():
    issue = _parse_issue(raw_issue(fixVersions=[{"name": "v1"}, "v2", {}, None, 42]))
    assert issue.fix_versions == ("v1", "v2")


@pytest.mark.parametrize(
    "body, expected",
    [
        (None, ""),
        (42, ""),
        (
            {
                "type": "doc",
                "content": [
                    None,
                    42,
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": " Hello "},
                            {"type": "hardBreak"},
                            {"type": "text", "text": " world "},
                        ],
                    },
                ],
            },
            "Hello world",
        ),
    ],
)
def test_embedded_comment_body_accepts_partial_adf(body, expected):
    issue = _parse_issue(
        raw_issue(
            comment={"comments": [{"id": "1", "created": "2026-05-01", "body": body}]}
        ),
        include_activity=True,
    )
    assert issue.comments[0].body == expected


def test_oversized_review_number_does_not_discard_other_references():
    # Python rejects integer strings over its digit limit. Jira fields are untrusted
    # input: skip the unusable reference while retaining normal ones in the field.
    raw = raw_issue(review_field="D" + "9" * 5000 + " D12")
    issue = _parse_issue(raw, review_fields=("review_field",))
    assert [ref.id for ref in issue.reviews] == [12]


@pytest.mark.parametrize("payload", ["unavailable", 42, ["unexpected"]])
def test_malformed_comment_envelope_preserves_ticket_and_other_activity(
    client, monkeypatch, payload
):
    raw = raw_issue(comment=payload) | {
        "changelog": {
            "histories": [
                {
                    "created": "2026-05-01",
                    "items": [{"field": "status", "toString": "Done"}],
                }
            ]
        }
    }
    monkeypatch.setattr(
        client, "_get", Mock(return_value={"total": 1, "issues": [raw]})
    )
    (issue,) = client.search_issues("project = ABC", include_activity=True)
    assert issue.key == "ABC-1"
    assert issue.comments == ()
    assert [change.field for change in issue.changes] == ["status"]


def test_complete_embedded_activity_does_not_emit_truncation_warning(
    client, monkeypatch, caplog
):
    page = {"startAt": 0, "maxResults": 20, "total": 1}
    raw = raw_issue(
        comment=page
        | {"comments": [{"id": "1", "created": "2026-05-01", "body": "Complete"}]}
    ) | {
        "changelog": page
        | {
            "histories": [
                {
                    "created": "2026-05-01",
                    "items": [{"field": "status", "toString": "Done"}],
                }
            ]
        }
    }
    monkeypatch.setattr(
        client, "_get", Mock(return_value={"total": 1, "issues": [raw]})
    )
    with caplog.at_level("WARNING"):
        (issue,) = client.search_issues("project = ABC", include_activity=True)
    assert [comment.body for comment in issue.comments] == ["Complete"]
    assert [change.to_value for change in issue.changes] == ["Done"]
    assert "truncated" not in caplog.text


def test_unusable_embedded_changelog_preserves_other_ticket_data(client, monkeypatch):
    raw = raw_issue(summary="Keep this ticket") | {"changelog": "unavailable"}
    monkeypatch.setattr(
        client, "_get", Mock(return_value={"total": 1, "issues": [raw]})
    )
    (issue,) = client.search_issues("project = ABC", include_activity=True)
    assert issue.key == "ABC-1"
    assert issue.summary == "Keep this ticket"
    assert issue.changes == ()
