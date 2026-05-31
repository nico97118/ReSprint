from __future__ import annotations

from collections.abc import Callable
from datetime import date
from importlib.resources import files

import requests
from flask import Flask, Response, request, send_from_directory

from resprint.config import Settings
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

SPRINT_TABLE_COLUMNS = [
    TableColumn("name", "Sprint"),
    TableColumn("start_date", "Date debut"),
    TableColumn("end_date", "Date fin"),
    TableColumn("state", "Statut"),
    TableColumn("report", "Rapport", sortable=False),
]


def create_app(
    settings: Settings,
    jira_client: JiraClient | None = None,
    tempo_client: TempoTeamWorklogClient | None = None,
    build_report_func: BuildReport = build_report,
) -> Flask:
    logger.info("Creating Flask application")
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
                sprint_error = (
                    "Impossible de recuperer les sprints pour ce board. "
                    "Il s'agit probablement d'un board qui ne supporte pas les sprints."
                )
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
            "ReSprint",
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

    @app.post("/report")
    def report() -> str | tuple[str, int]:
        tempo_team_id = _optional_int(request.form.get("tempo_team_id"))
        try:
            if request.form.get("report_mode") == "period":
                logger.info("Generating period/JQL report from web UI")
                context = build_report_func(
                    settings,
                    jql=request.form["jql"],
                    sprint_start=date.fromisoformat(request.form["start_date"]),
                    sprint_end=date.fromisoformat(request.form["end_date"]),
                    sprint_name=request.form.get("period_name") or None,
                    tempo_team_id=tempo_team_id,
                )
                return render_html(
                    context.review,
                    context.sprint,
                    context.jira_base_url,
                    context.jql,
                )

            board_id = int(request.form["board_id"])
            sprint_id = int(request.form["sprint_id"])
            logger.info(
                "Generating sprint report from web UI board=%s sprint=%s",
                board_id,
                sprint_id,
            )
            context = build_report_func(
                settings,
                sprint_id=sprint_id,
                board_id=board_id,
                tempo_team_id=tempo_team_id,
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
                "Parametres invalides",
                f"Impossible de generer le rapport: {exc}",
                400,
            )
        except requests.RequestException as exc:
            logger.error("Unable to generate report from web UI", exc_info=True)
            return _render_report_error(
                "Erreur Jira ou Tempo",
                (
                    "Impossible de contacter Jira ou Tempo pendant la generation "
                    f"du rapport: {exc}"
                ),
                502,
            )

    return app


def _load_boards(
    jira: JiraClient,
    project_key: str | None,
) -> tuple[list[Board], str | None]:
    if not project_key:
        logger.warning("Cannot load boards without JIRA_PROJECT_KEY")
        return [], "JIRA_PROJECT_KEY est requis pour lister les boards Jira."
    try:
        logger.info("Loading Scrum boards for project %s", project_key)
        boards = jira.list_boards(project_key, board_type="scrum")
    except requests.RequestException:
        logger.error("Unable to load Jira boards", exc_info=True)
        return [], (
            "Impossible de contacter Jira pour lister les boards. "
            "Verifie l'URL, le token et les droits d'acces au projet."
        )
    if not boards:
        logger.warning("No Scrum board found for project %s", project_key)
        return [], f"Aucun board Scrum Jira pour le projet {project_key}."
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


def _load_tempo_teams(
    tempo_client: TempoTeamWorklogClient,
) -> tuple[list[TempoTeam], str | None]:
    try:
        logger.info("Loading Tempo teams for home page")
        teams = tempo_client.list_teams()
        return teams, None
    except requests.RequestException:
        logger.warning("Unable to list Tempo teams", exc_info=True)
        return [], (
            "Impossible de lister les equipes Tempo. "
            "Le rapport reste generable sans selection d'equipe."
        )


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
        title="Sprints actifs et clos",
        columns=SPRINT_TABLE_COLUMNS,
        rows=[
            _sprint_row(sprint, selected_board_id, selected_tempo_team_id)
            for sprint in sprints
        ],
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("start_date", "desc"),
        empty_message="Aucun sprint ne correspond a la recherche.",
    )


def _sprint_row(
    sprint: Sprint,
    selected_board_id: int,
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
                _report_form(selected_board_id, sprint.id, selected_tempo_team_id),
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
        return badge_cell("Actif", "active")
    if state == "closed":
        return badge_cell("Clos", "closed")
    return badge_cell(state or "-")


def _report_form(
    board_id: int,
    sprint_id: int,
    tempo_team_id: int | None,
) -> str:
    return render_template(
        "components/home/sprint_report_form.html",
        board_id=board_id,
        sprint_id=sprint_id,
        tempo_team_id=tempo_team_id,
    )
