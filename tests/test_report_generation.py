from datetime import UTC, date, datetime

import pytest
import requests

from resprint.config import Settings
from resprint.frontend.view_models.report.tables import build_report_table_views
from resprint.models import (
    Issue,
    IssueReviewItem,
    JiraComment,
    JiraIssueChange,
    Sprint,
    SprintReview,
    TempoTeamMember,
    TempoWorklog,
    UserIdentity,
)
from resprint.report import build_report


class FakeJiraClient:
    def __init__(self) -> None:
        self.requested_issue_keys: list[str] = []
        self.requested_issue_include_activity: bool | None = None
        self.requested_worklog_issue_keys: list[str] = []
        self.requested_comment_issue_keys: list[str] = []
        self.requested_jql: str | None = None
        self.fail_changelog = False
        self.fail_worklog = False
        self.fail_parent_enrichment = False
        self.include_excluded_sprint_issue = False

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
        include_comments: bool = False,
    ) -> list[Issue]:
        self.requested_jql = jql
        comment_body = (
            "Commentaire sprint" if jql == "sprint = 456" else "Commentaire periode"
        )
        issues = [
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
            )
        ]
        if self.include_excluded_sprint_issue:
            issues.append(
                Issue(
                    id="10003",
                    key="ABC-3",
                    summary="A exclure",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                )
            )
        return issues

    def enrich_parent_summaries(self, issues: list[Issue]) -> list[Issue]:
        if self.fail_parent_enrichment:
            raise RuntimeError("parent enrichment unavailable")
        return issues

    def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
        self.requested_worklog_issue_keys.append(issue_id_or_key)
        if self.fail_worklog:
            raise RuntimeError("worklog unavailable")
        if issue_id_or_key == "ABC-2":
            return [
                TempoWorklog(
                    "10002",
                    5400,
                    date(2026, 5, 3),
                    "Bob",
                    issue_key="ABC-2",
                ),
                TempoWorklog(
                    "10002",
                    3600,
                    date(2026, 4, 20),
                    "Alice",
                    issue_key="ABC-2",
                ),
            ]
        return []

    def get_issue_changes(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[JiraIssueChange]:
        if self.fail_changelog:
            raise RuntimeError("changelog unavailable")
        return [
            JiraIssueChange(
                author="Alice",
                created_at=datetime(2026, 5, 10, 14, 30, tzinfo=UTC),
                field="status",
                from_value="To Do",
                to_value="Done",
            )
        ]

    def get_issue_comments(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[JiraComment]:
        self.requested_comment_issue_keys.append(issue_id_or_key)
        if issue_id_or_key == "ABC-2":
            return [
                JiraComment(
                    id="c-2",
                    issue_id="10002",
                    author="Bob",
                    created_at=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
                    body="Commentaire hors sprint",
                )
            ]
        return [
            JiraComment(
                id="c-1",
                issue_id="10001",
                author="Alice",
                created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
                body="Commentaire sprint",
            )
        ]

    def get_issues_by_keys(
        self,
        issue_keys: list[str],
        include_activity: bool = False,
    ) -> list[Issue]:
        self.requested_issue_keys = issue_keys
        self.requested_issue_include_activity = include_activity
        if not issue_keys:
            return []
        return [
            Issue(
                id="10002",
                key="ABC-2",
                summary="Hors sprint",
                status="In Progress",
                status_category="indeterminate",
                assignee="Bob",
                issue_type="Bug",
            )
        ]


class FakeTempoTeamWorklogClient:
    def __init__(self) -> None:
        self.calls: list[tuple[int, date, date]] = []
        self.worker_calls: list[tuple[tuple[str, ...], date, date]] = []
        self.resolve_worker_calls: list[tuple[str, ...]] = []
        self.member_calls: list[int] = []
        self.fail_search = False

    def list_team_members(self, team_id: int) -> list[TempoTeamMember]:
        self.member_calls.append(team_id)
        return [
            TempoTeamMember(identity=UserIdentity(display_name="Alice Tempo")),
            TempoTeamMember(identity=UserIdentity(display_name="Bob Tempo")),
        ]

    def resolve_workers(self, worker_keys: tuple[str, ...]) -> list[TempoTeamMember]:
        self.resolve_worker_calls.append(worker_keys)
        labels = {
            "alice": "Alice Tempo",
            "bob": "Bob Tempo",
        }
        return [
            TempoTeamMember(
                identity=UserIdentity(name=worker, display_name=labels.get(worker))
            )
            for worker in worker_keys
        ]

    def search_team_worklogs(
        self,
        team_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        self.calls.append((team_id, start_date, end_date))
        if self.fail_search:
            raise RuntimeError("tempo team search unavailable")
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

    def search_worker_worklogs(
        self,
        worker_keys: tuple[str, ...],
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        self.worker_calls.append((worker_keys, start_date, end_date))
        if self.fail_search:
            raise RuntimeError("tempo worker search unavailable")
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


def _selected_tempo_without_worklogs(monkeypatch) -> FakeTempoTeamWorklogClient:
    tempo = FakeTempoTeamWorklogClient()
    tempo.fail_search = True
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )
    return tempo


def test_build_report_requires_tempo_selection() -> None:
    with pytest.raises(ValueError, match="Tempo"):
        build_report(
            _settings(),
            sprint_id=456,
        )


def test_build_report_adds_out_of_sprint_items_when_tempo_team_is_selected(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(out_of_sprint_analysis=True),
        sprint_id=456,
        tempo_team_id=42,
    )

    assert tempo.calls == [(42, date(2026, 5, 1), date(2026, 5, 15))]
    assert jira.requested_issue_keys == ["ABC-2"]
    assert jira.requested_issue_include_activity is False
    assert jira.requested_jql == "sprint = 456"
    assert [item.issue.key for item in context.review.out_of_sprint] == ["ABC-2"]
    assert context.review.out_of_sprint[0].tempo_seconds == 5400
    assert context.review.out_of_sprint[0].total_seconds == 9000
    assert jira.requested_worklog_issue_keys == ["ABC-1", "ABC-2"]
    assert context.review.out_of_sprint[0].comments[0].body == "Commentaire hors sprint"
    assert context.review.out_of_sprint[0].changes[0].field == "status"
    assert context.review.completed[0].changes[0].field == "status"
    assert context.review.completed[0].comments[0].body == "Commentaire sprint"


def test_build_report_keeps_basic_out_of_sprint_items_when_analysis_is_disabled(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(),
        sprint_id=456,
        tempo_team_id=42,
    )

    assert tempo.calls == [(42, date(2026, 5, 1), date(2026, 5, 15))]
    assert jira.requested_issue_keys == ["ABC-2"]
    assert jira.requested_issue_include_activity is False
    assert [item.issue.key for item in context.review.out_of_sprint] == ["ABC-2"]
    assert context.review.out_of_sprint[0].tempo_seconds == 5400
    assert context.review.out_of_sprint[0].total_seconds == 5400
    assert context.review.out_of_sprint[0].comments == ()
    assert context.review.out_of_sprint[0].changes == ()
    assert jira.requested_worklog_issue_keys == ["ABC-1"]


def test_build_report_keeps_report_when_issue_activity_load_fails(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    jira.fail_changelog = True
    jira.fail_worklog = True
    _selected_tempo_without_worklogs(monkeypatch)
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )

    context = build_report(
        _settings(),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert jira.requested_jql == "sprint = 456"
    assert [item.issue.key for item in context.review.completed] == ["ABC-1"]
    assert context.review.completed[0].changes == ()
    assert context.review.completed[0].worklog_count == 0


def test_build_report_keeps_heavy_issue_when_comments_and_changelog_timeout(
    monkeypatch,
    caplog,
) -> None:
    caplog.set_level("WARNING", logger="resprint.report")

    class HeavyIssueJiraClient(FakeJiraClient):
        def search_issues(
            self,
            jql: str,
            include_activity: bool = False,
            include_comments: bool = False,
        ) -> list[Issue]:
            self.requested_jql = jql
            return [
                Issue(
                    id="10001",
                    key="ABC-1",
                    summary="Ticket simple",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                ),
                Issue(
                    id="10002",
                    key="ABC-2",
                    summary="Ticket tres lourd",
                    status="Done",
                    status_category="done",
                    assignee="Bob",
                ),
            ]

        def get_issue_comments(
            self,
            issue_id_or_key: str,
            sprint_start: date,
            sprint_end: date,
        ) -> list[JiraComment]:
            if issue_id_or_key == "ABC-2":
                raise TimeoutError("comments timeout")
            return super().get_issue_comments(issue_id_or_key, sprint_start, sprint_end)

        def get_issue_changes(
            self,
            issue_id_or_key: str,
            sprint_start: date,
            sprint_end: date,
        ) -> list[JiraIssueChange]:
            if issue_id_or_key == "ABC-2":
                raise TimeoutError("changelog timeout")
            return super().get_issue_changes(issue_id_or_key, sprint_start, sprint_end)

        def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
            return [
                TempoWorklog(
                    issue_id_or_key,
                    1800,
                    date(2026, 5, 3),
                    "Alice",
                    issue_key=issue_id_or_key,
                )
            ]

    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: HeavyIssueJiraClient(),
    )
    _selected_tempo_without_worklogs(monkeypatch)

    context = build_report(
        _settings(request_concurrency=2),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1", "ABC-2"]
    heavy_item = context.review.completed[1]
    assert heavy_item.issue.key == "ABC-2"
    assert heavy_item.comments == ()
    assert heavy_item.changes == ()
    assert heavy_item.tempo_seconds == 0
    assert heavy_item.total_seconds == 1800
    assert "Jira comments timed out for issue ABC-2" in caplog.text
    assert "Jira changelog timed out for issue ABC-2" in caplog.text


def test_build_report_keeps_report_when_parent_enrichment_fails(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    jira.fail_parent_enrichment = True
    _selected_tempo_without_worklogs(monkeypatch)
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )

    context = build_report(
        _settings(),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1"]


def test_build_report_logs_network_errors_without_stacktrace(
    monkeypatch,
    caplog,
) -> None:
    caplog.set_level("WARNING", logger="resprint.report")

    class NetworkErrorJiraClient(FakeJiraClient):
        def enrich_parent_summaries(self, issues: list[Issue]) -> list[Issue]:
            raise requests.ConnectionError("Jira parent lookup unavailable")

    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: NetworkErrorJiraClient(),
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1"]
    assert "Could not enrich parent issue summaries" in caplog.text
    assert "ConnectionError: Jira parent lookup unavailable" in caplog.text
    assert "Traceback" not in caplog.text


def test_build_report_keeps_report_when_out_of_sprint_load_fails(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    tempo.fail_search = True
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(out_of_sprint_analysis=True),
        sprint_id=456,
        tempo_team_id=42,
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1"]
    assert context.review.out_of_sprint == ()


def test_build_report_excludes_configured_sprint_issue_keys(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    jira.include_excluded_sprint_issue = True
    _selected_tempo_without_worklogs(monkeypatch)
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )

    context = build_report(
        _settings(excluded_issue_keys=frozenset({"abc-3"})),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1"]


def test_build_report_excludes_configured_out_of_sprint_issue_keys(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(
            excluded_issue_keys=frozenset({"abc-2"}),
            out_of_sprint_analysis=True,
        ),
        sprint_id=456,
        tempo_team_id=42,
    )

    assert context.review.out_of_sprint == ()
    assert jira.requested_issue_keys == []


def test_build_report_can_use_period_and_jql_without_sprint(
    monkeypatch,
) -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoTeamWorklogClient()
    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: jira,
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(out_of_sprint_analysis=True),
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


def test_build_report_uses_thread_local_jira_clients_for_parallel_issue_requests(
    monkeypatch,
) -> None:
    calls: list[tuple[str, int, str]] = []
    client_timeouts: list[float] = []
    clients = []

    class ParallelFakeJiraClient(FakeJiraClient):
        def __init__(self, client_index: int) -> None:
            super().__init__()
            self.client_index = client_index

        def search_issues(
            self,
            jql: str,
            include_activity: bool = False,
            include_comments: bool = False,
        ) -> list[Issue]:
            self.requested_jql = jql
            return [
                Issue(
                    id="10001",
                    key="ABC-1",
                    summary="Premier ticket",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                ),
                Issue(
                    id="10002",
                    key="ABC-2",
                    summary="Second ticket",
                    status="Done",
                    status_category="done",
                    assignee="Bob",
                ),
            ]

        def get_issue_changes(
            self,
            issue_id_or_key: str,
            sprint_start: date,
            sprint_end: date,
        ) -> list[JiraIssueChange]:
            calls.append(("changes", self.client_index, issue_id_or_key))
            return []

        def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
            calls.append(("worklogs", self.client_index, issue_id_or_key))
            return [
                TempoWorklog(
                    issue_id_or_key,
                    1800,
                    date(2026, 5, 3),
                    "Alice",
                    issue_key=issue_id_or_key,
                )
            ]

    def create_client(
        _settings: Settings,
        request_timeout: float = 30,
    ) -> ParallelFakeJiraClient:
        client = ParallelFakeJiraClient(len(clients))
        clients.append(client)
        client_timeouts.append(request_timeout)
        return client

    monkeypatch.setattr("resprint.report.create_jira_client", create_client)
    _selected_tempo_without_worklogs(monkeypatch)

    context = build_report(
        _settings(request_concurrency=2),
        sprint_id=456,
        tempo_worker_keys=("alice",),
    )

    assert [item.issue.key for item in context.review.completed] == ["ABC-1", "ABC-2"]
    assert len(clients) >= 3
    assert client_timeouts[0] == 30
    assert set(client_timeouts[1:]) == {10}
    assert {call[0] for call in calls} == {"changes", "worklogs"}
    assert all(client_index != 0 for _kind, client_index, _issue_key in calls)


def test_build_report_uses_tempo_team_worklogs_for_sprint_time(
    monkeypatch,
) -> None:
    tempo = FakeTempoTeamWorklogClient()

    class TwoIssueJiraClient(FakeJiraClient):
        def search_issues(
            self,
            jql: str,
            include_activity: bool = False,
            include_comments: bool = False,
        ) -> list[Issue]:
            self.requested_jql = jql
            return [
                Issue(
                    id="10001",
                    key="ABC-1",
                    summary="Premier ticket",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                ),
                Issue(
                    id="10002",
                    key="ABC-2",
                    summary="Second ticket",
                    status="Done",
                    status_category="done",
                    assignee="Bob",
                ),
            ]

    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: TwoIssueJiraClient(),
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(
            request_concurrency=2,
        ),
        sprint_id=456,
        tempo_team_id=42,
    )

    sprint_time_by_key = {
        item.issue.key: item.tempo_seconds for item in context.review.completed
    }
    assert tempo.calls == [(42, date(2026, 5, 1), date(2026, 5, 15))]
    assert tempo.member_calls == [42]
    assert context.participants == ("Alice Tempo", "Bob Tempo")
    assert sprint_time_by_key == {"ABC-1": 3600, "ABC-2": 5400}


def test_build_report_uses_tempo_worker_worklogs_for_sprint_time(
    monkeypatch,
) -> None:
    tempo = FakeTempoTeamWorklogClient()

    class TwoIssueJiraClient(FakeJiraClient):
        def search_issues(
            self,
            jql: str,
            include_activity: bool = False,
            include_comments: bool = False,
        ) -> list[Issue]:
            self.requested_jql = jql
            return [
                Issue(
                    id="10001",
                    key="ABC-1",
                    summary="Premier ticket",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                ),
                Issue(
                    id="10002",
                    key="ABC-2",
                    summary="Second ticket",
                    status="Done",
                    status_category="done",
                    assignee="Bob",
                ),
            ]

    monkeypatch.setattr(
        "resprint.report.create_jira_client",
        lambda _settings, **_kwargs: TwoIssueJiraClient(),
    )
    monkeypatch.setattr(
        "resprint.report.create_tempo_team_worklog_client",
        lambda _settings: tempo,
    )

    context = build_report(
        _settings(
            request_concurrency=2,
        ),
        sprint_id=456,
        tempo_worker_keys=("alice", "bob"),
        tempo_team_id=42,
    )

    sprint_time_by_key = {
        item.issue.key: item.tempo_seconds for item in context.review.completed
    }
    assert tempo.worker_calls == [
        (("alice", "bob"), date(2026, 5, 1), date(2026, 5, 15))
    ]
    assert tempo.resolve_worker_calls == [("alice", "bob")]
    assert context.participants == ("Alice Tempo", "Bob Tempo")
    assert tempo.calls == []
    assert sprint_time_by_key == {"ABC-1": 3600, "ABC-2": 5400}


def test_report_table_view_uses_issue_project_key() -> None:
    review = SprintReview(
        completed=(
            IssueReviewItem(
                issue=Issue(
                    id="10001",
                    key="ABC-1",
                    project_key="SHOP",
                    summary="Checkout",
                    status="Done",
                    status_category="done",
                    assignee="Alice",
                ),
                tempo_seconds=3600,
                total_seconds=3600,
                worklog_count=1,
            ),
        ),
        unfinished_with_time=(),
        not_started=(),
    )

    tables = build_report_table_views(review, "https://jira.example.test")

    assert tables[0].rows[0].project_key == "SHOP"


def _settings(
    *,
    excluded_issue_keys: frozenset[str] = frozenset(),
    out_of_sprint_analysis: bool = False,
    request_concurrency: int = 4,
) -> Settings:
    return Settings(
        jira_base_url="https://jira.example.test",
        jira_api_token="token",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        jira_ca_bundle=None,
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
        excluded_issue_keys=excluded_issue_keys,
        out_of_sprint_analysis=out_of_sprint_analysis,
        request_concurrency=request_concurrency,
        jira_issue_request_timeout=10,
    )
