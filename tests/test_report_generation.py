from datetime import UTC, date, datetime

from resprint.config import Settings
from resprint.models import Issue, JiraComment, JiraIssueChange, Sprint, TempoWorklog
from resprint.report import build_report


class FakeJiraClient:
    def __init__(self) -> None:
        self.requested_issue_keys: list[str] = []
        self.requested_jql: str | None = None

    def get_sprint(self, sprint_id: int) -> Sprint:
        return Sprint(
            id=sprint_id,
            name="Sprint 42",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 15),
        )

    def get_sprint_issues(
        self,
        sprint_id: int,
        board_id: int | None = None,
        include_activity: bool = False,
    ) -> list[Issue]:
        return [
            Issue(
                id="10001",
                key="ABC-1",
                summary="Dans le sprint",
                status="Done",
                status_category="done",
                assignee="Alice",
                comments=(
                    JiraComment(
                        id="c-1",
                        issue_id="10001",
                        author="Alice",
                        created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
                        body="Commentaire sprint",
                    ),
                ),
                changes=(
                    JiraIssueChange(
                        author="Alice",
                        created_at=datetime(2026, 5, 10, 14, 30, tzinfo=UTC),
                        field="status",
                        from_value="To Do",
                        to_value="Done",
                    ),
                ),
            )
        ]

    def search_issues(
        self,
        jql: str,
        include_activity: bool = False,
    ) -> list[Issue]:
        self.requested_jql = jql
        comment_body = (
            "Commentaire sprint" if jql == "sprint = 456" else "Commentaire periode"
        )
        return [
            Issue(
                id="10001",
                key="ABC-1",
                summary="Dans la periode",
                status="Done",
                status_category="done",
                assignee="Alice",
                comments=(
                    JiraComment(
                        id="c-1",
                        issue_id="10001",
                        author="Alice",
                        created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
                        body=comment_body,
                    ),
                ),
                changes=(
                    JiraIssueChange(
                        author="Alice",
                        created_at=datetime(2026, 5, 10, 14, 30, tzinfo=UTC),
                        field="status",
                        from_value="To Do",
                        to_value="Done",
                    ),
                ),
            )
        ]

    def enrich_parent_summaries(self, issues: list[Issue]) -> list[Issue]:
        return issues

    def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
        return []

    def get_issues_by_keys(
        self,
        issue_keys: list[str],
        include_activity: bool = False,
    ) -> list[Issue]:
        self.requested_issue_keys = issue_keys
        return [
            Issue(
                id="10002",
                key="ABC-2",
                summary="Hors sprint",
                status="In Progress",
                status_category="indeterminate",
                assignee="Bob",
                issue_type="Bug",
                comments=(
                    JiraComment(
                        id="c-2",
                        issue_id="10002",
                        author="Bob",
                        created_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
                        body="Commentaire hors sprint",
                    ),
                ),
                changes=(
                    JiraIssueChange(
                        author="Bob",
                        created_at=datetime(2026, 5, 11, 11, 0, tzinfo=UTC),
                        field="priority",
                        from_value="Low",
                        to_value="High",
                    ),
                ),
            )
        ]


class FakeTempoTeamWorklogClient:
    def __init__(self) -> None:
        self.calls: list[tuple[int, date, date]] = []

    def search_team_worklogs(
        self,
        team_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        self.calls.append((team_id, start_date, end_date))
        return [
            TempoWorklog(
                "10001",
                3600,
                date(2026, 5, 2),
                "Alice",
                issue_key="ABC-1",
            ),
            TempoWorklog(
                "10002",
                5400,
                date(2026, 5, 3),
                "Bob",
                issue_key="ABC-2",
            ),
        ]


def test_build_report_adds_out_of_sprint_items_when_tempo_team_is_selected(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr("resprint.report.create_jira_client", lambda _settings: jira)
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(),
        sprint_id=456,
        board_id=123,
        tempo_team_id=42,
    )

    assert tempo.calls == [(42, date(2026, 5, 1), date(2026, 5, 15))]
    assert jira.requested_issue_keys == ["ABC-2"]
    assert jira.requested_jql == "sprint = 456"
    assert [item.issue.key for item in context.review.out_of_sprint] == ["ABC-2"]
    assert context.review.out_of_sprint[0].tempo_seconds == 5400
    assert context.review.completed[0].changes[0].field == "status"
    assert context.review.completed[0].comments[0].body == "Commentaire sprint"


def test_build_report_can_use_period_and_jql_without_sprint(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr("resprint.report.create_jira_client", lambda _settings: jira)
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(),
        jql="project = ABC AND fixVersion = 2026.05",
        sprint_start=date(2026, 5, 1),
        sprint_end=date(2026, 5, 15),
        sprint_name="Iteration mai",
        tempo_team_id=42,
    )

    assert context.sprint.id == 0
    assert context.sprint.name == "Iteration mai"
    assert context.jql == "project = ABC AND fixVersion = 2026.05"
    assert jira.requested_jql == "project = ABC AND fixVersion = 2026.05"
    assert tempo.calls == [(42, date(2026, 5, 1), date(2026, 5, 15))]
    assert jira.requested_issue_keys == ["ABC-2"]


def _settings() -> Settings:
    return Settings(
        jira_base_url="https://jira.example.test",
        jira_api_token="token",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        tempo_api_token=None,
        worklog_source="jira",
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
    )
