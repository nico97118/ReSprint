from datetime import date, datetime, timedelta, timezone
from typing import Any

from sprint_review.jira_client import (
    JiraClient,
    _parse_comment,
    _parse_issue,
    _parse_jira_worklog,
    _plain_text_from_adf,
)


class FakeJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.epic_field = None
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
        self.epic_field = None
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
        self.epic_field = None
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


class FakeBoardAndSprintJiraClient(JiraClient):
    def __init__(self) -> None:
        self.base_url = "https://jira.example.test"
        self.epic_field = None
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

    boards = client.list_boards("ABC")

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


def test_parse_issue_extracts_epic_priority_and_estimates() -> None:
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

    assert issue.epic == "ABC-10 - Tunnel commande"
    assert issue.priority == "High"
    assert issue.fix_versions == ("2026.05", "2026.06")
    assert issue.original_estimate_seconds == 28800
    assert issue.remaining_estimate_seconds == 7200


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
