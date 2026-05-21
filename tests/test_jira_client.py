from datetime import datetime, timedelta, timezone
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


def _raw_issue(key: str, issue_id: str) -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": key,
        "fields": {
            "summary": key,
            "status": {"name": "To Do", "statusCategory": {"key": "new"}},
        },
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
