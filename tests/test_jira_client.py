import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from resprint.helpers.jira import (
    JiraClient,
    _parse_changelog_history,
    _parse_comment,
    _parse_issue,
    _parse_jira_worklog,
    _plain_text_from_adf,
)
from resprint.models import Issue


class FakeJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        start_at = int((params or {}).get("startAt", 0))
        if start_at == 0:
            return {
                "total": 2,
                "issues": [_raw_issue("ABC-1", "10001")],
            }
        return {
            "total": 2,
            "issues": [_raw_issue("ABC-2", "10002")],
        }


class FakeAgileThenRestJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        if path.startswith("/rest/agile/1.0/board/123/sprint/456/issue"):
            return {
                "isLast": True,
                "issues": [
                    {"id": "10001", "key": "ABC-1"},
                    {"id": "10002", "key": "ABC-2"},
                ],
            }
        if path == "/rest/api/2/search":
            return {
                "total": 2,
                "issues": [
                    _raw_issue("ABC-1", "10001"),
                    _raw_issue("ABC-2", "10002"),
                ],
            }
        raise AssertionError(f"Unexpected path: {path}")


class FakeWorklogJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert path == "/rest/api/2/issue/ABC-1/worklog"
        return {
            "total": 2,
            "worklogs": [
                _raw_worklog("2026-04-20T09:30:00.000+0200", 3600, "Alice"),
                _raw_worklog("2026-05-10T09:30:00.000+0200", 1800, "Bob"),
            ],
        }


class FakeChangelogJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"
        self.ignored_changelog_fields = frozenset(
            {"worklogid", "timeestimate", "timespent"}
        )
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        return {
            "key": "ABC-1",
            "changelog": {
                "histories": [
                    {
                        "author": {"displayName": "Alice"},
                        "created": "2026-05-10T14:30:00.000+0200",
                        "items": [
                            {
                                "field": "status",
                                "fromString": "To Do",
                                "toString": "In Progress",
                            }
                        ],
                    },
                    {
                        "author": {"displayName": "Bob"},
                        "created": "2026-04-28T09:00:00.000+0200",
                        "items": [
                            {
                                "field": "assignee",
                                "fromString": "Alice",
                                "toString": "Bob",
                            }
                        ],
                    },
                ]
            },
        }


class FakeTruncatedChangelogJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"
        self.ignored_changelog_fields = frozenset(
            {"worklogid", "timeestimate", "timespent"}
        )
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        if path == "/rest/api/2/issue/ABC-1":
            return {
                "key": "ABC-1",
                "changelog": {
                    "startAt": 0,
                    "maxResults": 1,
                    "total": 2,
                    "histories": [_raw_changelog_history("Alice", "2026-05-10")],
                },
            }
        raise AssertionError(f"Unexpected path: {path}")


class FakeBoardAndSprintJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.parent_field = None
        self.rest_api_base = "/rest/api/2"
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        if path == "/rest/agile/1.0/board":
            return {
                "isLast": True,
                "values": [
                    {
                        "id": 123,
                        "name": "Equipe ABC",
                        "type": "scrum",
                    }
                ],
            }
        if path == "/rest/agile/1.0/board/123/sprint":
            return {
                "isLast": True,
                "values": [
                    {
                        "id": 456,
                        "name": "Sprint 42",
                        "state": "closed",
                        "startDate": "2026-05-01T09:00:00.000+0200",
                        "endDate": "2026-05-15T18:00:00.000+0200",
                    }
                ],
            }
        raise AssertionError(f"Unexpected path: {path}")


class FakeParentSummaryJiraClient(JiraClient):
    def __init__(self) -> None:
        self.requested_keys: list[str] = []

    def get_issues_by_keys(self, issue_keys: list[str]) -> list[Issue]:
        self.requested_keys = issue_keys
        return [
            Issue(
                id="20001",
                key="ABC-10",
                summary="Tunnel commande",
                status="Done",
                status_category="done",
                assignee=None,
            )
        ]


def _raw_issue(key: str, issue_id: str) -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": key,
        "fields": {
            "summary": key,
            "status": {"name": "To Do", "statusCategory": {"key": "new"}},
        },
    }


def _raw_worklog(started: str, seconds: int, author: str) -> dict[str, Any]:
    return {
        "issueId": "10001",
        "author": {"displayName": author},
        "started": started,
        "timeSpentSeconds": seconds,
    }


def _raw_changelog_history(author: str, created_day: str) -> dict[str, Any]:
    return {
        "author": {"displayName": author},
        "created": f"{created_day}T14:30:00.000+0200",
        "items": [
            {
                "field": "status",
                "fromString": "To Do",
                "toString": "In Progress",
            }
        ],
    }


def test_plain_text_from_adf_extracts_nested_text() -> None:
    body = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Blocage identifie"},
                    {"type": "text", "text": " sur la recette."},
                ],
            }
        ],
    }

    assert _plain_text_from_adf(body) == "Blocage identifie sur la recette."


def test_search_issues_uses_configured_rest_api_version_and_paginates() -> None:
    client = FakeJiraClient()

    issues = client.search_issues("project = ABC")

    assert [issue.key for issue in issues] == ["ABC-1", "ABC-2"]
    assert [call[0] for call in client.calls] == [
        "/rest/api/2/search",
        "/rest/api/2/search",
    ]
    assert [call[1]["startAt"] for call in client.calls if call[1]] == [0, 1]


def test_get_sprint_issues_uses_agile_for_keys_then_rest_v2_for_details() -> None:
    client = FakeAgileThenRestJiraClient()

    issues = client.get_sprint_issues(sprint_id=456, board_id=123)

    assert [issue.key for issue in issues] == ["ABC-1", "ABC-2"]
    assert [call[0] for call in client.calls] == [
        "/rest/agile/1.0/board/123/sprint/456/issue",
        "/rest/api/2/search",
    ]
    search_params = client.calls[1][1] or {}
    assert search_params["jql"] == "key in (ABC-1, ABC-2)"
    assert "summary" in search_params["fields"]


def test_list_boards_parses_agile_boards() -> None:
    client = FakeBoardAndSprintJiraClient()

    boards = client.list_boards("ABC", board_type="scrum")

    assert len(boards) == 1
    assert boards[0].id == 123
    assert boards[0].name == "Equipe ABC"
    assert boards[0].type == "scrum"
    assert client.calls[0] == (
        "/rest/agile/1.0/board",
        {
            "projectKeyOrId": "ABC",
            "startAt": 0,
            "maxResults": 50,
            "type": "scrum",
        },
    )


def test_list_board_sprints_parses_agile_sprints_with_state() -> None:
    client = FakeBoardAndSprintJiraClient()

    sprints = client.list_board_sprints(123)

    assert len(sprints) == 1
    assert sprints[0].id == 456
    assert sprints[0].name == "Sprint 42"
    assert sprints[0].state == "closed"
    assert sprints[0].start_date == date(2026, 5, 1)
    assert sprints[0].end_date == date(2026, 5, 15)
    assert client.calls[0] == (
        "/rest/agile/1.0/board/123/sprint",
        {
            "state": "active,closed",
            "startAt": 0,
            "maxResults": 50,
        },
    )


def test_get_all_issue_worklogs_returns_unfiltered_worklogs() -> None:
    client = FakeWorklogJiraClient()

    worklogs = client.get_all_issue_worklogs("ABC-1")

    assert [worklog.time_spent_seconds for worklog in worklogs] == [3600, 1800]


def test_get_issue_worklogs_filters_worklogs_on_sprint_dates() -> None:
    client = FakeWorklogJiraClient()

    worklogs = client.get_issue_worklogs(
        "ABC-1",
        date(2026, 5, 1),
        date(2026, 5, 15),
    )

    assert [worklog.author for worklog in worklogs] == ["Bob"]


def test_parse_comment_keeps_author_created_date_and_body() -> None:
    comment = _parse_comment(
        {
            "id": "123",
            "issueId": "10001",
            "author": {"displayName": "Alice"},
            "created": "2026-05-10T14:30:00.000+0200",
            "body": "Commentaire simple",
        }
    )

    assert comment.id == "123"
    assert comment.issue_id == "10001"
    assert comment.author == "Alice"
    assert comment.created_at == datetime(
        2026,
        5,
        10,
        14,
        30,
        tzinfo=timezone(timedelta(hours=2)),
    )
    assert comment.body == "Commentaire simple"


def test_parse_changelog_history_splits_items() -> None:
    changes = _parse_changelog_history(
        {
            "author": {"displayName": "Alice"},
            "created": "2026-05-10T14:30:00.000+0200",
            "items": [
                {
                    "field": "status",
                    "fromString": "To Do",
                    "toString": "In Progress",
                },
                {
                    "field": "priority",
                    "fromString": "Medium",
                    "toString": "High",
                },
                {
                    "field": "worklogId",
                    "fromString": None,
                    "toString": "123",
                },
                {
                    "field": "timeestimate",
                    "fromString": "3600",
                    "toString": "1800",
                },
                {
                    "field": "timespent",
                    "fromString": "0",
                    "toString": "3600",
                },
            ],
        }
    )

    assert len(changes) == 2
    assert changes[0].author == "Alice"
    assert changes[0].created_at == datetime(
        2026,
        5,
        10,
        14,
        30,
        tzinfo=timezone(timedelta(hours=2)),
    )
    assert changes[0].field == "status"
    assert changes[0].from_value == "To Do"
    assert changes[0].to_value == "In Progress"
    assert changes[1].field == "priority"


def test_get_issue_changes_filters_changelog_on_sprint_dates() -> None:
    client = FakeChangelogJiraClient()

    changes = client.get_issue_changes(
        "ABC-1",
        date(2026, 5, 1),
        date(2026, 5, 15),
    )

    assert client.calls == [
        (
            "/rest/api/2/issue/ABC-1",
            {
                "fields": "key",
                "expand": "changelog",
            },
        )
    ]
    assert len(changes) == 1
    assert changes[0].author == "Alice"
    assert changes[0].field == "status"
    assert changes[0].from_value == "To Do"
    assert changes[0].to_value == "In Progress"


def test_get_issue_changes_warns_and_keeps_embedded_changelog_when_truncated(
    caplog,
) -> None:
    caplog.set_level(logging.WARNING, logger="resprint.helpers.jira")
    client = FakeTruncatedChangelogJiraClient()

    changes = client.get_issue_changes(
        "ABC-1",
        date(2026, 5, 1),
        date(2026, 5, 15),
    )

    assert [change.author for change in changes] == ["Alice"]
    assert client.calls == [
        (
            "/rest/api/2/issue/ABC-1",
            {
                "fields": "key",
                "expand": "changelog",
            },
        ),
    ]
    assert "Embedded Jira changelog is truncated" in caplog.text


def test_parse_issue_extracts_parent_priority_and_estimates() -> None:
    issue = _parse_issue(
        {
            "id": "10001",
            "key": "ABC-1",
            "fields": {
                "summary": "Finaliser le paiement",
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate"},
                },
                "assignee": {"displayName": "Alice"},
                "issuetype": {"name": "Story"},
                "priority": {"name": "High"},
                "fixVersions": [{"name": "2026.05"}, {"name": "2026.06"}],
                "parent": {
                    "key": "ABC-10",
                    "fields": {
                        "summary": "Tunnel commande",
                        "issuetype": {"name": "Epic"},
                    },
                },
                "timetracking": {
                    "originalEstimateSeconds": 28800,
                    "remainingEstimateSeconds": 7200,
                },
            },
        }
    )

    assert issue.parent == "ABC-10 - Tunnel commande"
    assert issue.issue_type == "Story"
    assert issue.priority == "High"
    assert issue.fix_versions == ("2026.05", "2026.06")
    assert issue.original_estimate_seconds == 28800
    assert issue.remaining_estimate_seconds == 7200


def test_enrich_parent_summaries_resolves_custom_parent_link_key() -> None:
    client = FakeParentSummaryJiraClient()
    issue = _parse_issue(
        {
            "id": "10001",
            "key": "ABC-1",
            "fields": {
                "summary": "Finaliser le paiement",
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate"},
                },
                "customfield_10014": "ABC-10",
            },
        },
        parent_field="customfield_10014",
    )

    enriched_issues = client.enrich_parent_summaries([issue])

    assert client.requested_keys == ["ABC-10"]
    assert enriched_issues[0].parent == "ABC-10 - Tunnel commande"


def test_enrich_parent_summaries_keeps_already_formatted_parent() -> None:
    client = FakeParentSummaryJiraClient()
    issue = _parse_issue(
        {
            "id": "10001",
            "key": "ABC-1",
            "fields": {
                "summary": "Finaliser le paiement",
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate"},
                },
                "customfield_10014": "ABC-10 - Tunnel commande",
            },
        },
        parent_field="customfield_10014",
    )

    enriched_issues = client.enrich_parent_summaries([issue])

    assert client.requested_keys == []
    assert enriched_issues == [issue]


def test_parse_jira_worklog_extracts_time_author_and_comment() -> None:
    worklog = _parse_jira_worklog(
        {
            "issueId": "10001",
            "author": {"displayName": "Alice"},
            "started": "2026-05-10T09:30:00.000+0200",
            "timeSpentSeconds": 3600,
            "comment": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Analyse technique"}],
                    }
                ],
            },
        }
    )

    assert worklog.issue_id == "10001"
    assert worklog.time_spent_seconds == 3600
    assert worklog.start_date.isoformat() == "2026-05-10"
    assert worklog.author == "Alice"
    assert worklog.description == "Analyse technique"
