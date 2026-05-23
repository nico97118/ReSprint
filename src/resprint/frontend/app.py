from __future__ import annotations

import html
from collections.abc import Callable

import requests
from flask import Flask, Response, request

from resprint.config import Settings
from resprint.frontend.report_page import render_html
from resprint.frontend.utils.page import render_page, static_text
from resprint.frontend.utils.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    render_table_section,
    table_css,
    table_script,
)
from resprint.frontend.utils.templates import render_template
from resprint.helpers.jira import JiraClient
from resprint.models import Board, Sprint
from resprint.report import (
    ReportContext,
    build_report,
    create_jira_client,
)

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
    build_report_func: BuildReport = build_report,
) -> Flask:
    app = Flask(__name__)
    jira = jira_client or create_jira_client(settings)

    @app.get("/healthz")
    def healthz() -> Response:
        return Response("ok", mimetype="text/plain")

    @app.get("/")
    def index() -> str:
        if not settings.jira_project_key:
            return _render_error(
                "Configuration manquante",
                "JIRA_PROJECT_KEY est requis pour l'interface web.",
            )

        try:
            boards = jira.list_boards(settings.jira_project_key, board_type="scrum")
        except requests.RequestException:
            return _render_error(
                "Jira inaccessible",
                (
                    "Impossible de contacter Jira. Verifie l'URL, le token "
                    "et les droits d'acces au projet."
                ),
            )
        if not boards:
            return _render_error(
                "Aucun board trouve",
                f"Aucun board Scrum Jira pour le projet {settings.jira_project_key}.",
            )

        selected_board_id = _selected_board_id(boards, request.args.get("board_id"))
        sprints = []
        sprint_error = None
        if selected_board_id is not None:
            try:
                sprints = jira.list_board_sprints(
                    selected_board_id,
                    states=("active", "closed"),
                )
            except requests.RequestException:
                sprint_error = (
                    "Impossible de recuperer les sprints pour ce board. "
                    "Il s'agit probablement d'un board qui ne supporte pas les sprints."
                )
        content = render_template(
            "home.html",
            project_key=settings.jira_project_key,
            boards=boards,
            selected_board_id=selected_board_id,
            sprints=sprints,
            sprint_table_html=_render_sprint_table(sprints, selected_board_id),
            sprint_error=sprint_error,
        )
        return render_page(
            "ReSprint",
            content,
            extra_css=static_text("home.css") + table_css(),
            scripts=table_script(),
        )

    @app.post("/report")
    def report() -> str:
        board_id = int(request.form["board_id"])
        sprint_id = int(request.form["sprint_id"])
        context = build_report_func(
            settings,
            sprint_id=sprint_id,
            board_id=board_id,
        )
        return render_html(context.review, context.sprint, context.jira_base_url)

    return app


def _selected_board_id(boards: list[Board], board_id: str | None) -> int | None:
    if board_id:
        return int(board_id)
    if len(boards) == 1:
        return int(boards[0].id)
    return None


def _render_error(title: str, message: str) -> str:
    content = render_template("error.html", message=message)
    return render_page(
        title,
        content,
    )


def _render_sprint_table(sprints: list[Sprint], selected_board_id: int | None) -> str:
    if not selected_board_id or not sprints:
        return ""

    return render_table_section(
        section_id="sprints",
        title="Sprints actifs et clos",
        columns=SPRINT_TABLE_COLUMNS,
        rows=[_sprint_row(sprint, selected_board_id) for sprint in sprints],
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("start_date", "desc"),
        empty_message="Aucun sprint ne correspond a la recherche.",
    )


def _sprint_row(sprint: Sprint, selected_board_id: int) -> TableRow:
    state = sprint.state or ""
    return TableRow(
        cells={
            "name": TableCell(_html(sprint.name)),
            "start_date": TableCell(
                _html(sprint.start_date.isoformat()),
                sort_value=sprint.start_date.isoformat(),
            ),
            "end_date": TableCell(
                _html(sprint.end_date.isoformat()),
                sort_value=sprint.end_date.isoformat(),
            ),
            "state": TableCell(_state_badge(state)),
            "report": TableCell(_report_form(selected_board_id, sprint.id)),
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


def _state_badge(state: str) -> str:
    if state == "active":
        return '<span class="badge badge-active">Actif</span>'
    if state == "closed":
        return '<span class="badge badge-closed">Clos</span>'
    return f'<span class="badge">{_html(state or "-")}</span>'


def _report_form(board_id: int, sprint_id: int) -> str:
    return f"""<form method="post" action="/report">
  <input type="hidden" name="board_id" value="{board_id}">
  <input type="hidden" name="sprint_id" value="{sprint_id}">
  <button type="submit">
    <span class="button-content">
      <span class="mdi mdi-file-chart-outline" aria-hidden="true"></span>
      <span>Generer</span>
    </span>
  </button>
</form>"""


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)
