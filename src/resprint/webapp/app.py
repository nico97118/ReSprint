from __future__ import annotations

import html
from collections.abc import Callable

import requests
from flask import Flask, Response, render_template_string, request

from resprint.application.report_service import (
    ReportContext,
    build_report,
    create_jira_client,
)
from resprint.config import Settings
from resprint.domain.models import Board, Sprint
from resprint.integrations.jira import JiraClient
from resprint.presentation.report import render_html
from resprint.presentation.table_renderer import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    render_table_section,
    table_css,
    table_script,
)
from resprint.presentation.ui_assets import render_page

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
        content = render_template_string(
            HOME_CONTENT_TEMPLATE,
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
            extra_css=HOME_CSS,
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
    content = render_template_string(ERROR_CONTENT_TEMPLATE, message=message)
    return render_page(
        title,
        content,
        extra_css=ERROR_CSS,
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


ERROR_CSS = ""


ERROR_CONTENT_TEMPLATE = """<p>{{ message }}</p>"""


HOME_CSS = """
    h2 { margin: 28px 0 12px; font-size: 20px; }
    form.toolbar {
      display: flex;
      align-items: end;
      gap: 12px;
      margin-bottom: 24px;
    }
    label { display: grid; gap: 6px; font-weight: 650; }
    @media (max-width: 700px) {
      form.toolbar { align-items: stretch; flex-direction: column; }
    }
""" + table_css()


HOME_CONTENT_TEMPLATE = """<p>Projet Jira: <strong>{{ project_key }}</strong></p>

    <form class="toolbar" method="get" action="/">
      <label>
        Board
        <select name="board_id">
          {% if boards|length > 1 %}
            <option value="">Selectionner un board</option>
          {% endif %}
          {% for board in boards %}
            <option
              value="{{ board.id }}"
              {% if board.id == selected_board_id %}selected{% endif %}
            >
              {{ board.name }} ({{ board.type }})
            </option>
          {% endfor %}
        </select>
      </label>
      <button type="submit">
        <span class="button-content">
          <span class="mdi mdi-view-list" aria-hidden="true"></span>
          <span>Afficher les sprints</span>
        </span>
      </button>
    </form>

    {% if selected_board_id %}
      {% if sprint_error %}
        <p class="empty">{{ sprint_error }}</p>
      {% elif sprints %}
        {{ sprint_table_html | safe }}
      {% else %}
        <p class="empty">Aucun sprint actif ou clos pour ce board.</p>
      {% endif %}
    {% else %}
      <p class="empty">Selectionne un board pour afficher les sprints.</p>
    {% endif %}
"""
