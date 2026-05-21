from __future__ import annotations

from collections.abc import Callable

import requests
from flask import Flask, Response, render_template_string, request

from sprint_review.config import Settings
from sprint_review.jira_client import JiraClient
from sprint_review.models import Board
from sprint_review.report import render_html
from sprint_review.report_service import ReportContext, build_report, create_jira_client

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
        return render_template_string(
            HOME_TEMPLATE,
            project_key=settings.jira_project_key,
            boards=boards,
            selected_board_id=selected_board_id,
            sprints=sprints,
            sprint_error=sprint_error,
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
    return render_template_string(
        ERROR_TEMPLATE,
        title=title,
        message=message,
    )


ERROR_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body {
      margin: 0;
      color: var(--text);
      background: var(--background);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }
    :root {
      color-scheme: light;
      --background: #f7f8fa;
      --surface: #ffffff;
      --surface-muted: #eef2f7;
      --border: #d7dde5;
      --text: #17202a;
      --muted: #5f6b7a;
      --accent: #0969da;
      --accent-text: #ffffff;
    }
    html[data-theme="dark"] {
      color-scheme: dark;
      --background: #101418;
      --surface: #181f26;
      --surface-muted: #222b35;
      --border: #344150;
      --text: #e7edf4;
      --muted: #a7b3c2;
      --accent: #5aa2ff;
      --accent-text: #06111f;
    }
    main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }
    header {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 20px;
    }
    h1 { margin: 0; font-size: 28px; }
    h2 { margin: 28px 0 12px; font-size: 20px; }
    form.toolbar {
      display: flex;
      align-items: end;
      gap: 12px;
      margin-bottom: 24px;
    }
    label { display: grid; gap: 6px; font-weight: 650; }
    select, button {
      min-height: 36px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 6px 10px;
      font: inherit;
    }
    button {
      color: var(--accent-text);
      background: var(--accent);
      border-color: var(--accent);
      cursor: pointer;
      font-weight: 650;
    }
    .theme-toggle {
      color: var(--text);
      background: var(--surface);
      border-color: var(--border);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid #d7dde5;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid #d7dde5;
      text-align: left;
      vertical-align: top;
    }
    th { background: #eef2f7; font-weight: 650; }
    .empty { color: #5f6b7a; }
  </style>
</head>
<body>
  <main>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
  </main>
</body>
</html>"""


HOME_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sprint Review</title>
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css"
  >
  <style>
    body {
      margin: 0;
      color: #17202a;
      background: #f7f8fa;
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }
    main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }
    h1 { margin: 0 0 20px; font-size: 28px; }
    h2 { margin: 28px 0 12px; font-size: 20px; }
    form.toolbar {
      display: flex;
      align-items: end;
      gap: 12px;
      margin-bottom: 24px;
    }
    label { display: grid; gap: 6px; font-weight: 650; }
    select, button {
      min-height: 36px;
      border: 1px solid #cbd5e1;
      background: #fff;
      padding: 6px 10px;
      font: inherit;
    }
    button {
      color: #fff;
      background: #0969da;
      border-color: #0969da;
      cursor: pointer;
      font-weight: 650;
    }
    .mdi { font-size: 18px; line-height: 1; }
    .button-content {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--border);
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }
    th { background: var(--surface-muted); font-weight: 650; }
    .empty { color: var(--muted); }
    @media (max-width: 700px) {
      header { display: grid; }
      form.toolbar { align-items: stretch; flex-direction: column; }
    }
  </style>
  <script>
    const storedTheme = localStorage.getItem("sprint-review-theme");
    if (storedTheme) {
      document.documentElement.dataset.theme = storedTheme;
    }
  </script>
</head>
<body>
  <main>
    <header>
      <h1>Sprint Review</h1>
      <button class="theme-toggle" type="button" data-theme-toggle>
        <span class="button-content">
          <span class="mdi mdi-theme-light-dark" aria-hidden="true"></span>
          <span data-theme-label>Theme</span>
        </span>
      </button>
    </header>
    <p>Projet Jira: <strong>{{ project_key }}</strong></p>

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
              <tr>
                <td>{{ sprint.name }}</td>
                <td>{{ sprint.start_date.isoformat() }}</td>
                <td>{{ sprint.end_date.isoformat() }}</td>
                <td>{{ sprint.state or "-" }}</td>
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
      {% else %}
        <p class="empty">Aucun sprint actif ou clos pour ce board.</p>
      {% endif %}
    {% else %}
      <p class="empty">Selectionne un board pour afficher les sprints.</p>
    {% endif %}
  </main>
  <script>
    const themeToggle = document.querySelector("[data-theme-toggle]");
    const themeLabel = document.querySelector("[data-theme-label]");

    function currentTheme() {
      return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    }

    function applyTheme(theme) {
      document.documentElement.dataset.theme = theme;
      localStorage.setItem("sprint-review-theme", theme);
      themeLabel.textContent = theme === "dark" ? "Mode sombre" : "Mode clair";
    }

    applyTheme(currentTheme());
    themeToggle.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  </script>
</body>
</html>"""
