from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from importlib.resources import files

import requests
from flask import Flask, Response, request, send_from_directory

from resprint.config import Settings
from resprint.frontend.i18n import configure_language, t
from resprint.frontend.report.page import render_html
from resprint.frontend.utils.page import asset_url, render_page
from resprint.frontend.utils.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    badge_cell,
    html_cell,
    render_table_section,
    table_css,
    table_script,
    text_cell,
)
from resprint.frontend.utils.templates import render_template
from resprint.helpers.jira import JiraClient
from resprint.helpers.tempo import TempoTeamWorklogClient
from resprint.logging import get_logger
from resprint.models import Board, Sprint, TempoTeam
from resprint.report import (
    ReportContext,
    build_report,
    create_jira_client,
)

logger = get_logger(__name__)

BuildReport = Callable[..., ReportContext]

_REPORT_SPRINT_PARAMS = frozenset({"sprint_id", "tempo_team_id"})
_REPORT_PERIOD_PARAMS = frozenset(
    {"jql", "start_date", "end_date", "sprint_name", "tempo_team_id"}
)


def create_app(
    settings: Settings,
    jira_client: JiraClient | None = None,
    tempo_client: TempoTeamWorklogClient | None = None,
    build_report_func: BuildReport = build_report,
) -> Flask:
    logger.info("Creating Flask application")
    configure_language(settings.language)
    app = Flask(__name__)
    jira = jira_client or create_jira_client(settings)
    tempo = tempo_client or TempoTeamWorklogClient(
        settings.jira_base_url,
        settings.jira_api_token,
    )

    @app.get("/healthz")
    def healthz() -> Response:
        logger.debug("Healthcheck requested")
        return Response("ok", mimetype="text/plain")

    @app.get("/assets/<path:filename>")
    def assets(filename: str) -> Response:
        logger.debug("Serving frontend asset %s", filename)
        return send_from_directory(str(files("resprint.frontend.static")), filename)

    @app.get("/")
    def index() -> str:
        logger.info("Rendering home page")
        boards, board_error = _load_boards(jira, settings.jira_project_key)
        selected_board_id = _selected_board_id(boards, request.args.get("board_id"))
        selected_tempo_team_id = _optional_int(request.args.get("tempo_team_id"))
        tempo_teams, tempo_team_error = _load_tempo_teams(tempo)
        sprints = []
        sprint_error = None
        if selected_board_id is not None:
            try:
                logger.info("Loading sprints for selected board %s", selected_board_id)
                sprints = jira.list_board_sprints(
                    selected_board_id,
                    states=("active", "closed"),
                )
            except requests.RequestException:
                logger.warning(
                    "Unable to load sprints for board %s",
                    selected_board_id,
                    exc_info=True,
                )
                sprint_error = t("home.sprint_load_error")
        content = render_template(
            "pages/home.html",
            project_key=settings.jira_project_key,
            board_error=board_error,
            boards=boards,
            selected_board_id=selected_board_id,
            tempo_teams=tempo_teams,
            selected_tempo_team_id=selected_tempo_team_id,
            tempo_team_error=tempo_team_error,
            sprints=sprints,
            sprint_table_html=_render_sprint_table(
                sprints,
                selected_board_id,
                selected_tempo_team_id,
            ),
            sprint_error=sprint_error,
        )
        return render_page(
            t("app.brand"),
            content,
            stylesheets=(
                asset_url("min/common.min.css"),
                asset_url("min/home.min.css"),
                table_css(),
            ),
            head_scripts=(asset_url("min/theme.min.js"),),
            scripts=(
                table_script(),
                asset_url("min/home.min.js"),
            ),
        )

    @app.get("/report")
    def report() -> str | tuple[str, int]:
        try:
            context = _build_report_context_from_query(
                settings,
                build_report_func,
                request.args,
            )
            return render_html(
                context.review,
                context.sprint,
                context.jira_base_url,
                context.jql,
            )
        except ValueError as exc:
            logger.warning("Invalid web report request: %s", exc, exc_info=True)
            return _render_report_error(
                t("report.invalid_params.title"),
                t("report.invalid_params.message", message=exc),
                400,
            )
        except requests.RequestException as exc:
            logger.error("Unable to generate report from web UI", exc_info=True)
            return _render_report_error(
                t("report.external_error.title"),
                t("report.external_error.message", message=exc),
                502,
            )

    return app


def _load_boards(
    jira: JiraClient,
    project_key: str | None,
) -> tuple[list[Board], str | None]:
    if not project_key:
        logger.warning("Cannot load boards without JIRA_PROJECT_KEY")
        return [], t("home.project_key_required")
    try:
        logger.info("Loading Scrum boards for project %s", project_key)
        boards = jira.list_boards(project_key, board_type="scrum")
    except requests.RequestException:
        logger.error("Unable to load Jira boards", exc_info=True)
        return [], t("home.board_error")
    if not boards:
        logger.warning("No Scrum board found for project %s", project_key)
        return [], t("home.board_empty", project_key=project_key)
    logger.info("Loaded %s Scrum boards for project %s", len(boards), project_key)
    return boards, None


def _selected_board_id(boards: list[Board], board_id: str | None) -> int | None:
    if board_id:
        logger.debug("Selected board from request: %s", board_id)
        return int(board_id)
    if len(boards) == 1:
        logger.debug("Auto-selecting only available board: %s", boards[0].id)
        return int(boards[0].id)
    logger.debug("No board selected")
    return None


def _optional_int(value: str | None) -> int | None:
    return int(value) if value else None


def _required_arg(args: Mapping[str, str], name: str) -> str:
    value = args.get(name)
    if value is None or value == "":
        raise ValueError(t("report.required_param", name=name))
    return value


def _build_report_context_from_query(
    settings: Settings,
    build_report_func: BuildReport,
    args: Mapping[str, str],
) -> ReportContext:
    _validate_report_query_args(args)
    tempo_team_id = _optional_int(args.get("tempo_team_id"))
    if _is_period_report_request(args):
        logger.info("Generating period/JQL report from web UI")
        sprint_name = args.get("sprint_name") or None
        context = build_report_func(
            settings,
            jql=_required_arg(args, "jql"),
            sprint_start=date.fromisoformat(_required_arg(args, "start_date")),
            sprint_end=date.fromisoformat(_required_arg(args, "end_date")),
            sprint_name=sprint_name,
            tempo_team_id=tempo_team_id,
        )
        return context

    sprint_id = int(_required_arg(args, "sprint_id"))
    logger.info("Generating sprint report from web UI sprint=%s", sprint_id)
    return build_report_func(
        settings,
        sprint_id=sprint_id,
        tempo_team_id=tempo_team_id,
    )


def _validate_report_query_args(args: Mapping[str, str]) -> None:
    keys = set(args.keys())
    unexpected_keys = keys - (_REPORT_SPRINT_PARAMS | _REPORT_PERIOD_PARAMS)
    if unexpected_keys:
        raise ValueError(t("report.unexpected_param", name=sorted(unexpected_keys)[0]))

    has_sprint_mode = "sprint_id" in keys
    has_period_mode = _is_period_report_request(args)
    if has_sprint_mode and has_period_mode:
        raise ValueError(t("report.mixed_params"))
    if has_sprint_mode and "sprint_name" in keys and not has_period_mode:
        raise ValueError(t("report.unexpected_param", name="sprint_name"))


def _is_period_report_request(args: Mapping[str, str]) -> bool:
    return any(key in args for key in ("jql", "start_date", "end_date"))


def _load_tempo_teams(
    tempo_client: TempoTeamWorklogClient,
) -> tuple[list[TempoTeam], str | None]:
    try:
        logger.info("Loading Tempo teams for home page")
        teams = tempo_client.list_teams()
        return teams, None
    except requests.RequestException:
        logger.warning("Unable to list Tempo teams", exc_info=True)
        return [], t("home.tempo_team_error")


def _render_report_error(
    title: str,
    message: str,
    status_code: int,
) -> tuple[str, int]:
    return _render_error_page(title, message), status_code


def _render_error_page(title: str, message: str) -> str:
    logger.error("Rendering error page '%s': %s", title, message)
    content = render_template("pages/error.html", message=message)
    return render_page(
        title,
        content,
    )


def _render_sprint_table(
    sprints: list[Sprint],
    selected_board_id: int | None,
    selected_tempo_team_id: int | None,
) -> str:
    if not selected_board_id or not sprints:
        logger.debug(
            "Skipping sprint table render selected_board_id=%s sprint_count=%s",
            selected_board_id,
            len(sprints),
        )
        return ""

    logger.debug("Rendering sprint table with %s sprints", len(sprints))
    return render_table_section(
        section_id="sprints",
        title=t("home.sprints.title"),
        columns=_sprint_table_columns(),
        rows=[_sprint_row(sprint, selected_tempo_team_id) for sprint in sprints],
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("start_date", "desc"),
        empty_message=t("home.sprints.empty"),
    )


def _sprint_row(
    sprint: Sprint,
    selected_tempo_team_id: int | None,
) -> TableRow:
    state = sprint.state or ""
    return TableRow(
        cells={
            "name": text_cell(sprint.name),
            "start_date": text_cell(
                sprint.start_date.isoformat(),
                sort_value=sprint.start_date.isoformat(),
            ),
            "end_date": text_cell(
                sprint.end_date.isoformat(),
                sort_value=sprint.end_date.isoformat(),
            ),
            "state": _state_cell(state),
            "report": html_cell(
                _report_form(sprint.id, selected_tempo_team_id),
            ),
        },
        search_text=" ".join(
            (
                sprint.name,
                sprint.start_date.isoformat(),
                sprint.end_date.isoformat(),
                state,
            )
        ),
        style="success" if state == "active" else None,
    )


def _state_cell(state: str) -> TableCell:
    if state == "active":
        return badge_cell(t("status.active"), "active")
    if state == "closed":
        return badge_cell(t("status.closed"), "closed")
    return badge_cell(state or "-")


def _report_form(
    sprint_id: int,
    tempo_team_id: int | None,
) -> str:
    return render_template(
        "components/home/sprint_report_form.html",
        sprint_id=sprint_id,
        tempo_team_id=tempo_team_id,
    )


def _sprint_table_columns() -> list[TableColumn]:
    return [
        TableColumn("name", t("table.sprint")),
        TableColumn("start_date", t("table.start_date")),
        TableColumn("end_date", t("table.end_date")),
        TableColumn("state", t("table.status")),
        TableColumn("report", t("table.report"), sortable=False),
    ]
