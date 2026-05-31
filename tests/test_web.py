from datetime import date

import requests

from resprint.config import Settings
from resprint.frontend.app import create_app
from resprint.models import Board, Sprint, SprintReview, TempoTeam
from resprint.report import ReportContext


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
                id=457,
                name="Sprint 43",
                start_date=date(2026, 5, 16),
                end_date=date(2026, 5, 30),
                state="active",
            ),
            Sprint(
                id=456,
                name="Sprint 42",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 15),
                state="closed",
            ),
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


class FakeBoardErrorJiraClient(FakeJiraClient):
    def list_boards(
        self,
        project_key: str,
        board_type: str | None = None,
    ) -> list[Board]:
        self.board_calls.append((project_key, board_type))
        raise requests.ConnectionError("Jira is unreachable")


class FakeTempoClient:
    def __init__(self) -> None:
        self.team_calls = 0

    def list_teams(self) -> list[TempoTeam]:
        self.team_calls += 1
        return [
            TempoTeam(id=10, name="Tempo Team ABC"),
            TempoTeam(id=20, name="Tempo Team DEF"),
        ]


class FakeTempoErrorClient(FakeTempoClient):
    def list_teams(self) -> list[TempoTeam]:
        self.team_calls += 1
        raise requests.ConnectionError("Tempo teams unavailable")


def test_healthz_returns_ok() -> None:
    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
    )

    response = app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"


def test_assets_serves_vendored_frontend_files() -> None:
    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
    )
    client = app.test_client()

    mdi_css = client.get("/assets/vendor/mdi/css/materialdesignicons.min.css")
    chart_js = client.get("/assets/vendor/chartjs/chart.umd.js")
    mdi_font = client.get("/assets/vendor/mdi/fonts/materialdesignicons-webfont.woff2")

    assert mdi_css.status_code == 200
    assert "Material Design Icons" in mdi_css.text
    assert chart_js.status_code == 200
    assert "Chart.js v4.4.9" in chart_js.text
    assert mdi_font.status_code == 200
    assert len(mdi_font.data) > 0


def test_index_displays_boards_and_sprints() -> None:
    jira = FakeJiraClient()
    tempo = FakeTempoClient()
    app = create_app(_settings(), jira_client=jira, tempo_client=tempo)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Equipe ABC" in response.text
    assert "Analyse par sprint Jira" in response.text
    assert "Analyse par periode et JQL" in response.text
    assert '<details class="home-panel analysis-panel" open>' in response.text
    assert '<details class="home-panel analysis-panel">' in response.text
    assert '<summary class="analysis-summary">' in response.text
    assert "Usage principal" in response.text
    assert "Usage avance" in response.text
    assert 'name="report_mode" value="period"' in response.text
    assert 'name="start_date" type="date"' in response.text
    assert 'name="end_date" type="date"' in response.text
    assert 'name="jql"' in response.text
    assert "Sprint 42" in response.text
    assert "Sprint 43" in response.text
    assert "Tempo Team ABC" in response.text
    assert "Tempo Team DEF" in response.text
    assert "2026-05-01" in response.text
    assert "2026-05-16" in response.text
    assert "/assets/vendor/mdi/css/materialdesignicons.min.css" in response.text
    assert "/assets/min/common.min.css" in response.text
    assert "/assets/min/home.min.css" in response.text
    assert "/assets/min/table.min.css" in response.text
    assert "/assets/min/theme.min.js" in response.text
    assert "/assets/min/table.min.js" in response.text
    assert "/assets/min/home.min.js" in response.text
    assert "cdn.jsdelivr.net" not in response.text
    assert "app-navbar" in response.text
    assert "app-brand" in response.text
    assert "Navigation principale" in response.text
    assert "mdi-file-chart-outline" in response.text
    assert "data-theme-toggle" in response.text
    assert "theme-switch" in response.text
    assert 'role="switch"' in response.text
    assert "data-enhanced-table" in response.text
    assert "data-table-search" in response.text
    assert "data-report-generation-form" in response.text
    assert "Generation en cours..." in response.text
    assert 'data-default-sort-column="1"' in response.text
    assert 'data-default-sort-direction="desc"' in response.text
    assert 'aria-sort="descending"' in response.text
    assert "mdi-magnify" in response.text
    assert "mdi-arrow-down" in response.text
    assert "table-row-success" in response.text
    assert "badge-active" in response.text
    assert "Actif" in response.text
    assert "badge-closed" in response.text
    assert "Clos" in response.text
    assert jira.board_calls == [("ABC", "scrum")]
    assert jira.sprint_calls == [(123, ("active", "closed"))]
    assert tempo.team_calls == 1


def test_index_uses_configured_english_language() -> None:
    app = create_app(
        _settings(language="en"),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
    )

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    assert "Jira sprint analysis" in response.text
    assert "Period and JQL analysis" in response.text
    assert "Primary use" in response.text
    assert "Advanced use" in response.text
    assert "Generate report" in response.text
    assert "Navigation principale" not in response.text


def test_index_handles_jira_board_lookup_error() -> None:
    jira = FakeBoardErrorJiraClient()
    app = create_app(
        _settings(),
        jira_client=jira,
        tempo_client=FakeTempoClient(),
    )

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Analyse par periode et JQL" in response.text
    assert "Impossible de contacter Jira pour lister les boards" in response.text
    assert "Verifie l&#39;URL, le token" in response.text
    assert jira.board_calls == [("ABC", "scrum")]
    assert jira.sprint_calls == []


def test_index_handles_board_without_sprints() -> None:
    jira = FakeSprintErrorJiraClient()
    app = create_app(
        _settings(),
        jira_client=jira,
        tempo_client=FakeTempoClient(),
    )

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Kanban ABC" in response.text
    assert "Impossible de recuperer les sprints pour ce board" in response.text
    assert jira.sprint_calls == [(123, ("active", "closed"))]


def test_index_handles_tempo_team_lookup_error() -> None:
    tempo = FakeTempoErrorClient()
    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=tempo,
    )

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "Impossible de lister les equipes Tempo" in response.text
    assert "Sprint 42" in response.text
    assert tempo.team_calls == 1


def test_report_post_builds_and_displays_report() -> None:
    calls: list[dict[str, object]] = []

    def build_report_func(
        settings: Settings,
        sprint_id: int,
        board_id: int,
        tempo_team_id: int | None = None,
    ) -> ReportContext:
        calls.append(
            {
                "settings": settings,
                "sprint_id": sprint_id,
                "board_id": board_id,
                "tempo_team_id": tempo_team_id,
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
        tempo_client=FakeTempoClient(),
        build_report_func=build_report_func,
    )

    response = app.test_client().post(
        "/report",
        data={
            "board_id": "123",
            "sprint_id": "456",
            "tempo_team_id": "10",
        },
    )

    assert response.status_code == 200
    assert "<h1>Sprint 42</h1>" in response.text
    assert "report-export" in response.text
    assert "Exporter" in response.text
    assert calls[0]["sprint_id"] == 456
    assert calls[0]["board_id"] == 123
    assert calls[0]["tempo_team_id"] == 10


def test_report_post_builds_period_report_from_jql() -> None:
    calls: list[dict[str, object]] = []

    def build_report_func(
        settings: Settings,
        sprint_id: int | None = None,
        board_id: int | None = None,
        jql: str | None = None,
        sprint_start: date | None = None,
        sprint_end: date | None = None,
        sprint_name: str | None = None,
        tempo_team_id: int | None = None,
    ) -> ReportContext:
        calls.append(
            {
                "settings": settings,
                "sprint_id": sprint_id,
                "board_id": board_id,
                "jql": jql,
                "sprint_start": sprint_start,
                "sprint_end": sprint_end,
                "sprint_name": sprint_name,
                "tempo_team_id": tempo_team_id,
            }
        )
        return ReportContext(
            review=SprintReview(
                completed=(),
                unfinished_with_time=(),
                not_started=(),
            ),
            sprint=Sprint(
                id=0,
                name="Iteration mai",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 15),
            ),
            jira_base_url="https://jira.example.test",
            jql="project = ABC AND fixVersion = 2026.05",
        )

    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
        build_report_func=build_report_func,
    )

    response = app.test_client().post(
        "/report",
        data={
            "report_mode": "period",
            "period_name": "Iteration mai",
            "start_date": "2026-05-01",
            "end_date": "2026-05-15",
            "jql": "project = ABC AND fixVersion = 2026.05",
            "tempo_team_id": "10",
        },
    )

    assert response.status_code == 200
    assert "<h1>Iteration mai</h1>" in response.text
    assert "project = ABC AND fixVersion = 2026.05" in response.text
    assert calls[0]["sprint_id"] is None
    assert calls[0]["board_id"] is None
    assert calls[0]["jql"] == "project = ABC AND fixVersion = 2026.05"
    assert calls[0]["sprint_start"] == date(2026, 5, 1)
    assert calls[0]["sprint_end"] == date(2026, 5, 15)
    assert calls[0]["sprint_name"] == "Iteration mai"
    assert calls[0]["tempo_team_id"] == 10


def test_report_post_renders_error_page_when_generation_request_is_invalid() -> None:
    def build_report_func(
        settings: Settings,
        sprint_id: int,
        board_id: int,
        tempo_team_id: int | None = None,
    ) -> ReportContext:
        raise ValueError("JQL invalide")

    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
        build_report_func=build_report_func,
    )

    response = app.test_client().post(
        "/report",
        data={
            "board_id": "123",
            "sprint_id": "456",
        },
    )

    assert response.status_code == 400
    assert "<h1>Parametres invalides</h1>" in response.text
    assert "Impossible de generer le rapport: JQL invalide" in response.text
    assert "Traceback" not in response.text


def test_report_post_renders_error_page_when_jira_or_tempo_is_unreachable() -> None:
    def build_report_func(
        settings: Settings,
        sprint_id: int,
        board_id: int,
        tempo_team_id: int | None = None,
    ) -> ReportContext:
        raise requests.ConnectionError("Jira timeout")

    app = create_app(
        _settings(),
        jira_client=FakeJiraClient(),
        tempo_client=FakeTempoClient(),
        build_report_func=build_report_func,
    )

    response = app.test_client().post(
        "/report",
        data={
            "board_id": "123",
            "sprint_id": "456",
        },
    )

    assert response.status_code == 502
    assert "<h1>Erreur Jira ou Tempo</h1>" in response.text
    assert "Impossible de contacter Jira ou Tempo" in response.text
    assert "Jira timeout" in response.text
    assert "Traceback" not in response.text


def _settings(language: str = "fr") -> Settings:
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
        language=language,
    )
