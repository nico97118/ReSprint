from datetime import date

import requests

from sprint_review.application.report_service import ReportContext
from sprint_review.config import Settings
from sprint_review.domain.models import Board, Sprint, SprintReview
from sprint_review.webapp.app import create_app


class FakeJiraClient:
    def __init__(self) -> None:
        self.board_calls: list[tuple[str, str | None]] = []
        self.sprint_calls: list[tuple[int, tuple[str, ...]]] = []

    def list_boards(
        self,
        project_key: str,
        board_type: str | None = None,
    ) -> list[Board]:
        self.board_calls.append((project_key, board_type))
        return [Board(id=123, name="Equipe ABC", type="scrum")]

    def list_board_sprints(
        self,
        board_id: int,
        states: tuple[str, ...] = ("active", "closed"),
    ) -> list[Sprint]:
        self.sprint_calls.append((board_id, states))
        return [
            Sprint(
                id=456,
                name="Sprint 42",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 15),
                state="closed",
            )
        ]


class FakeSprintErrorJiraClient(FakeJiraClient):
    def list_boards(
        self,
        project_key: str,
        board_type: str | None = None,
    ) -> list[Board]:
        self.board_calls.append((project_key, board_type))
        return [Board(id=123, name="Kanban ABC", type="kanban")]

    def list_board_sprints(
        self,
        board_id: int,
        states: tuple[str, ...] = ("active", "closed"),
    ) -> list[Sprint]:
        self.sprint_calls.append((board_id, states))
        raise requests.HTTPError("The board does not support sprints")


def test_healthz_returns_ok() -> None:
    app = create_app(_settings(), jira_client=FakeJiraClient())

    response = app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"


def test_index_displays_boards_and_sprints() -> None:
    jira = FakeJiraClient()
    app = create_app(_settings(), jira_client=jira)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Equipe ABC" in response.text
    assert "Sprint 42" in response.text
    assert "2026-05-01" in response.text
    assert "materialdesignicons.min.css" in response.text
    assert "mdi-file-chart-outline" in response.text
    assert "data-theme-toggle" in response.text
    assert "theme-switch" in response.text
    assert 'role="switch"' in response.text
    assert 'setAttribute("data-theme", theme)' in response.text
    assert "mdi-moon-waning-crescent" in response.text
    assert "sprint-review-theme" in response.text
    assert "data-sprint-search" in response.text
    assert "data-sprint-row" in response.text
    assert "mdi-magnify" in response.text
    assert "nth-child(even)" in response.text
    assert "badge-closed" in response.text
    assert "Clos" in response.text
    assert jira.board_calls == [("ABC", "scrum")]
    assert jira.sprint_calls == [(123, ("active", "closed"))]


def test_index_handles_board_without_sprints() -> None:
    jira = FakeSprintErrorJiraClient()
    app = create_app(_settings(), jira_client=jira)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Kanban ABC" in response.text
    assert "Impossible de recuperer les sprints pour ce board" in response.text
    assert jira.sprint_calls == [(123, ("active", "closed"))]


def test_report_post_builds_and_displays_report() -> None:
    calls: list[dict[str, object]] = []

    def build_report_func(
        settings: Settings,
        sprint_id: int,
        board_id: int,
    ) -> ReportContext:
        calls.append(
            {
                "settings": settings,
                "sprint_id": sprint_id,
                "board_id": board_id,
            }
        )
        return ReportContext(
            review=SprintReview(
                completed=(),
                unfinished_with_time=(),
                not_started=(),
            ),
            sprint=Sprint(
                id=sprint_id,
                name="Sprint 42",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 15),
                state="closed",
            ),
            jira_base_url="https://jira.example.test",
        )

    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        build_report_func=build_report_func,
    )

    response = app.test_client().post(
        "/report",
        data={
            "board_id": "123",
            "sprint_id": "456",
        },
    )

    assert response.status_code == 200
    assert "Sprint review - Sprint 42" in response.text
    assert calls[0]["sprint_id"] == 456
    assert calls[0]["board_id"] == 123


def _settings() -> Settings:
    return Settings(
        jira_base_url="https://jira.example.test",
        jira_username="prenom.nom",
        jira_api_token="token",
        jira_auth_method="basic",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        tempo_api_token=None,
        worklog_source="jira",
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        epic_field=None,
    )
