from __future__ import annotations

from collections.abc import Callable

import requests
from flask import Flask, Response, render_template_string, request

from sprint_review.application.report_service import (
    ReportContext,
    build_report,
    create_jira_client,
)
from sprint_review.config import Settings
from sprint_review.domain.models import Board
from sprint_review.integrations.jira import JiraClient
from sprint_review.presentation.report import render_html
from sprint_review.presentation.ui_assets import render_page

BuildReport = Callable[..., ReportContext]


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

        boards = jira.list_boards(settings.jira_project_key, board_type="scrum")
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
            sprint_error=sprint_error,
        )
        return render_page(
            "Sprint Review",
            content,
            extra_css=HOME_CSS,
            scripts=HOME_SCRIPT,
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
    .sprint-tools {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 12px;
    }
    .no-results { margin: 12px 0 0; }
    @media (max-width: 700px) {
      form.toolbar { align-items: stretch; flex-direction: column; }
      .sprint-tools { align-items: stretch; flex-direction: column; }
    }
"""


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
      <h2>Sprints actifs et clos</h2>
      {% if sprint_error %}
        <p class="empty">{{ sprint_error }}</p>
      {% elif sprints %}
        <div class="sprint-tools">
          <div class="search-wrap">
            <span class="mdi mdi-magnify" aria-hidden="true"></span>
            <input
              class="search"
              type="search"
              placeholder="Rechercher un sprint..."
              aria-label="Rechercher un sprint"
              data-sprint-search
            >
          </div>
          <span class="row-count" data-sprint-count></span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Sprint</th>
              <th>Date debut</th>
              <th>Date fin</th>
              <th>Statut</th>
              <th>Rapport</th>
            </tr>
          </thead>
          <tbody>
            {% for sprint in sprints %}
              <tr
                data-sprint-row
                data-search="{{ (
                  sprint.name ~ ' ' ~
                  sprint.start_date.isoformat() ~ ' ' ~
                  sprint.end_date.isoformat() ~ ' ' ~
                  (sprint.state or '')
                ) | lower }}"
              >
                <td>{{ sprint.name }}</td>
                <td>{{ sprint.start_date.isoformat() }}</td>
                <td>{{ sprint.end_date.isoformat() }}</td>
                <td>
                  {% if sprint.state == "active" %}
                    <span class="badge badge-active">Actif</span>
                  {% elif sprint.state == "closed" %}
                    <span class="badge badge-closed">Clos</span>
                  {% else %}
                    <span class="badge">{{ sprint.state or "-" }}</span>
                  {% endif %}
                </td>
                <td>
                  <form method="post" action="/report">
                    <input
                      type="hidden"
                      name="board_id"
                      value="{{ selected_board_id }}"
                    >
                    <input
                      type="hidden"
                      name="sprint_id"
                      value="{{ sprint.id }}"
                    >
                    <button type="submit">
                      <span class="button-content">
                        <span
                          class="mdi mdi-file-chart-outline"
                          aria-hidden="true"
                        ></span>
                        <span>Generer</span>
                      </span>
                    </button>
                  </form>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
        <p class="no-results" data-sprint-no-results>
          Aucun sprint ne correspond a la recherche.
        </p>
      {% else %}
        <p class="empty">Aucun sprint actif ou clos pour ce board.</p>
      {% endif %}
    {% else %}
      <p class="empty">Selectionne un board pour afficher les sprints.</p>
    {% endif %}
"""


HOME_SCRIPT = """
    const sprintSearch = document.querySelector("[data-sprint-search]");
    if (sprintSearch) {
      const sprintRows = Array.from(document.querySelectorAll("[data-sprint-row]"));
      const sprintCount = document.querySelector("[data-sprint-count]");
      const noSprintResults = document.querySelector("[data-sprint-no-results]");

      function updateSprintSearch() {
        const query = sprintSearch.value.trim().toLocaleLowerCase("fr");
        let visibleRows = 0;
        sprintRows.forEach((row) => {
          const visible = !query || row.dataset.search.includes(query);
          row.hidden = !visible;
          if (visible) {
            visibleRows += 1;
          }
        });
        sprintCount.textContent = `${visibleRows} / ${sprintRows.length}`;
        noSprintResults.style.display = visibleRows === 0 ? "block" : "none";
      }

      sprintSearch.addEventListener("input", updateSprintSearch);
      updateSprintSearch();
    }
"""
