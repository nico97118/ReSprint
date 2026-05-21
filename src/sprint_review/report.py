from __future__ import annotations

import html
import json
from dataclasses import asdict

from sprint_review.models import IssueReviewItem, Sprint, SprintReview
from sprint_review.ui_assets import (
    MDI_STYLESHEET,
    THEME_INIT_SCRIPT,
    THEME_SCRIPT,
    THEME_SWITCH,
    common_css,
)


def render_markdown(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    lines = [
        f"# Sprint review - {sprint.name}",
        "",
        f"Periode: {sprint.start_date.isoformat()} -> {sprint.end_date.isoformat()}",
        "",
    ]

    if not _has_items(review):
        lines.append("Aucune issue a signaler pour cette sprint review.")
        return "\n".join(lines) + "\n"

    lines.extend(
        _render_section(
            "Tickets termines",
            list(review.completed),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            "Tickets non commences",
            list(review.not_started),
            jira_base_url,
        )
    )

    return "\n".join(lines) + "\n"


def _render_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend(["Aucun ticket.", ""])
        return lines

    lines.extend(
        [
            "| Issue key | Titre | Epopee | Priorite | FixVersion | "
            "Temps original estime | Temps restant estime | Temps total consomme | "
            "Temps consomme durant le sprint | "
            "Temps original depasse | "
            "Temps consomme par utilisateur | "
            "Commentaires durant le sprint |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | "
            "--- | --- | --- |",
        ]
    )
    for item in items:
        issue = item.issue
        issue_url = f"{jira_base_url}/browse/{issue.key}"
        lines.append(
            "| "
            f"[{issue.key}]({issue_url}) | "
            f"{_escape_table(issue.summary or '-')} | "
            f"{_escape_table(issue.epic or '-')} | "
            f"{_escape_table(issue.priority or '-')} | "
            f"{_escape_table(_format_fix_versions(issue.fix_versions))} | "
            f"{_format_duration(issue.original_estimate_seconds)} | "
            f"{_format_duration(issue.remaining_estimate_seconds)} | "
            f"{_format_duration(item.total_seconds)} | "
            f"{_format_duration(item.tempo_seconds)} | "
            f"{_format_bool(item.is_over_original_estimate)} | "
            f"{_format_time_spent_by_user(item)} | "
            f"{_format_comments(item)} |"
        )

    lines.append("")
    return lines


def render_json(review: SprintReview, sprint: Sprint) -> str:
    payload = {
        "sprint": asdict(sprint),
        "completed": [_item_to_json(item) for item in review.completed],
        "unfinished_with_time": [
            _item_to_json(item) for item in review.unfinished_with_time
        ],
        "not_started": [_item_to_json(item) for item in review.not_started],
    }
    return json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n"


def render_html(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    title = f"Sprint review - {sprint.name}"
    sections = [
        ("Tickets termines", list(review.completed)),
        (
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
        ),
        ("Tickets non commences", list(review.not_started)),
    ]
    sections_html = "\n".join(
        _render_html_section(title, items, jira_base_url) for title, items in sections
    )
    summary_html = _render_html_summary(review)
    shared_css = common_css()

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html(title)}</title>
  {MDI_STYLESHEET}
  <style>
    {shared_css}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 4px; font-size: 28px; }}
    h2 {{ margin: 0; font-size: 20px; }}
    .period {{ margin: 0 0 24px; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 0 0 28px;
    }}
    .summary-item {{
      color: var(--text);
      border: 1px solid var(--border);
      background: var(--surface);
      cursor: pointer;
      padding: 14px 16px;
      text-align: left;
    }}
    .summary-item[aria-selected="true"] {{
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
    }}
    .summary-item:hover {{
      background: var(--surface-strong);
    }}
    .summary-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      text-transform: uppercase;
    }}
    .summary-count {{
      display: inline-block;
      margin-top: 8px;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 10px;
      background: var(--surface-muted);
      font-size: 18px;
      font-weight: 720;
    }}
    section {{ margin-top: 30px; }}
    .section-header {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }}
    .section-tools {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .search {{ width: 100%; }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
    th {{
      text-align: left;
      white-space: nowrap;
    }}
    th[data-sortable] {{ padding: 0; }}
    .sort-button {{
      width: 100%;
      border: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 650;
      text-align: left;
      white-space: nowrap;
    }}
    th.numeric .sort-button {{ justify-content: flex-end; }}
    .sort-indicator {{
      color: var(--muted);
      font-size: 16px;
      line-height: 1;
      min-width: 16px;
    }}
    .sort-button:hover
      .sort-indicator:not(.mdi-arrow-up):not(.mdi-arrow-down) {{
      opacity: 0.45;
    }}
    .sort-button:hover
      .sort-indicator:not(.mdi-arrow-up):not(.mdi-arrow-down)::before {{
      content: "\\F005D";
      display: inline-block;
      font: normal normal normal 24px/1 "Material Design Icons";
      font-size: 16px;
      text-rendering: auto;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }}
    td.numeric, th.numeric {{ text-align: right; white-space: nowrap; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 650; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); }}
    .stack {{ display: grid; gap: 4px; }}
    .comments {{ max-width: 380px; }}
    .empty {{ margin: 0 0 20px; }}
    .no-results {{ padding: 14px 16px; }}
    @media (max-width: 760px) {{
      main {{ padding: 22px 14px 36px; }}
      .summary {{ grid-template-columns: 1fr; }}
      .section-header {{ display: grid; align-items: start; }}
      .section-tools {{ width: 100%; }}
    }}
  </style>
  {THEME_INIT_SCRIPT}
</head>
<body>
  <main>
    {THEME_SWITCH}
    <h1>{_html(title)}</h1>
    <p class="period">
      Periode: {_html(sprint.start_date.isoformat())}
      -> {_html(sprint.end_date.isoformat())}
    </p>
    {summary_html}
    {sections_html}
  </main>
  <script>
    const collator = new Intl.Collator("fr", {{ numeric: true, sensitivity: "base" }});

    {THEME_SCRIPT}

    const tabButtons = Array.from(document.querySelectorAll("[data-report-tab]"));
    const tabPanels = Array.from(document.querySelectorAll("[data-report-panel]"));

    function activateTab(targetId) {{
      tabButtons.forEach((button) => {{
        const active = button.dataset.targetPanel === targetId;
        button.setAttribute("aria-selected", String(active));
      }});
      tabPanels.forEach((panel) => {{
        panel.hidden = panel.id !== targetId;
      }});
    }}

    tabButtons.forEach((button) => {{
      button.addEventListener("click", () => {{
        activateTab(button.dataset.targetPanel);
      }});
    }});
    if (tabButtons.length) {{
      activateTab(tabButtons[0].dataset.targetPanel);
    }}

    document.querySelectorAll("[data-report-table]").forEach((section) => {{
      const input = section.querySelector("[data-table-search]");
      const tbody = section.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const count = section.querySelector("[data-row-count]");
      const noResults = section.querySelector("[data-no-results]");

      function updateCount() {{
        const visibleRows = rows.filter((row) => !row.hidden).length;
        count.textContent = `${{visibleRows}} / ${{rows.length}}`;
        noResults.style.display = visibleRows === 0 ? "block" : "none";
      }}

      input.addEventListener("input", () => {{
        const query = input.value.trim().toLocaleLowerCase("fr");
        rows.forEach((row) => {{
          row.hidden = query && !row.dataset.search.includes(query);
        }});
        updateCount();
      }});

      section.querySelectorAll("[data-sort-column]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const column = Number(button.dataset.sortColumn);
          const type = button.dataset.sortType || "text";
          const current = button.dataset.sortDirection || "none";
          const direction = current === "asc" ? "desc" : "asc";

          section.querySelectorAll("[data-sort-column]").forEach((other) => {{
            other.dataset.sortDirection = "none";
            other.querySelector(".sort-indicator").className = "sort-indicator";
            other.closest("th").setAttribute("aria-sort", "none");
          }});

          button.dataset.sortDirection = direction;
          button.querySelector(".sort-indicator").className =
            direction === "asc"
              ? "sort-indicator mdi mdi-arrow-up"
              : "sort-indicator mdi mdi-arrow-down";
          button.closest("th").setAttribute(
            "aria-sort",
            direction === "asc" ? "ascending" : "descending",
          );

          rows
            .sort((left, right) => {{
              const leftValue = sortValue(left, column, type);
              const rightValue = sortValue(right, column, type);
              const comparison = type === "number"
                ? leftValue - rightValue
                : collator.compare(leftValue, rightValue);
              return direction === "asc" ? comparison : -comparison;
            }})
            .forEach((row) => tbody.appendChild(row));
        }});
      }});

      updateCount();
    }});

    function sortValue(row, column, type) {{
      const cell = row.cells[column];
      const value = cell.dataset.sortValue || cell.textContent.trim();
      return type === "number" ? Number(value || 0) : value;
    }}
  </script>
</body>
</html>
"""


def _render_html_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> str:
    section_id = _html_attr(_slugify(title))
    if not items:
        return (
            f'<section id="{section_id}" data-report-panel>'
            f"<h2>{_html(title)}</h2>"
            '<p class="empty">Aucun ticket.</p></section>'
        )

    rows = "\n".join(_render_html_row(item, jira_base_url) for item in items)
    return f"""<section id="{section_id}" data-report-table data-report-panel>
  <div class="section-header">
    <h2>{_html(title)} <span class="muted">({len(items)})</span></h2>
    <div class="section-tools">
      <div class="search-wrap">
        <span class="mdi mdi-magnify" aria-hidden="true"></span>
        <input
          class="search"
          type="search"
          aria-label="Rechercher dans {_html_attr(title)}"
          placeholder="Rechercher..."
          data-table-search
        >
      </div>
      <span class="row-count" data-row-count></span>
    </div>
  </div>
  <div class="table-wrap">
    <table aria-describedby="{section_id}-empty">
      <thead>
        <tr>
          {_sortable_header("Issue key", 0)}
          {_sortable_header("Titre", 1)}
          {_sortable_header("Epopee", 2)}
          {_sortable_header("Priorite", 3)}
          {_sortable_header("FixVersion", 4)}
          {_sortable_header("Temps original estime", 5, "number", True)}
          {_sortable_header("Temps restant estime", 6, "number", True)}
          {_sortable_header("Temps total consomme", 7, "number", True)}
          {_sortable_header("Temps sprint", 8, "number", True)}
          {_sortable_header("Depassement", 9, "number")}
          <th>Temps sprint par utilisateur</th>
          <th>Commentaires sprint</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <div class="no-results" id="{section_id}-empty" data-no-results>
      Aucun ticket ne correspond a la recherche.
    </div>
  </div>
</section>"""


def _render_html_row(item: IssueReviewItem, jira_base_url: str) -> str:
    issue = item.issue
    issue_url = f"{jira_base_url}/browse/{issue.key}"
    overrun_class = "badge-danger" if item.is_over_original_estimate else "badge-ok"
    overrun = _html(_format_bool(item.is_over_original_estimate))
    original_estimate_cell = _numeric_cell(issue.original_estimate_seconds)
    remaining_estimate_cell = _numeric_cell(issue.remaining_estimate_seconds)
    total_time_cell = _numeric_cell(item.total_seconds)
    sprint_time_cell = _numeric_cell(item.tempo_seconds)
    overrun_cell = (
        f'<td data-sort-value="{int(item.is_over_original_estimate)}">'
        f'<span class="badge {overrun_class}">{overrun}</span></td>'
    )
    search_text = _html_attr(
        " ".join(
            (
                issue.key,
                issue.summary,
                issue.epic or "",
                issue.priority or "",
                _format_fix_versions(issue.fix_versions),
                _format_bool(item.is_over_original_estimate),
                _plain_time_spent_by_user(item),
                _plain_comments(item),
            )
        ).casefold()
    )
    return f"""<tr data-search="{search_text}">
  <td><a href="{_html_attr(issue_url)}">{_html(issue.key)}</a></td>
  <td>{_html(issue.summary or "-")}</td>
  <td>{_html(issue.epic or "-")}</td>
  <td>{_html(issue.priority or "-")}</td>
  <td>{_html(_format_fix_versions(issue.fix_versions))}</td>
  {original_estimate_cell}
  {remaining_estimate_cell}
  {total_time_cell}
  {sprint_time_cell}
  {overrun_cell}
  <td>{_format_html_time_spent_by_user(item)}</td>
  <td class="comments">{_format_html_comments(item)}</td>
</tr>"""


def _render_html_summary(review: SprintReview) -> str:
    completed_tab = _render_summary_tab(
        "Tickets termines",
        "Tickets termines",
        len(review.completed),
        True,
    )
    unfinished_tab = _render_summary_tab(
        "Non termines avec temps",
        "Tickets non termines avec du temps consomme",
        len(review.unfinished_with_time),
    )
    not_started_tab = _render_summary_tab(
        "Non commences",
        "Tickets non commences",
        len(review.not_started),
    )
    return f"""<div class="summary" role="tablist" aria-label="Sections du rapport">
  {completed_tab}
  {unfinished_tab}
  {not_started_tab}
</div>"""


def _render_summary_tab(
    label: str,
    panel_title: str,
    count: int,
    selected: bool = False,
) -> str:
    panel_id = _html_attr(_slugify(panel_title))
    return f"""<button
    class="summary-item"
    type="button"
    role="tab"
    aria-selected="{str(selected).lower()}"
    data-report-tab
    data-target-panel="{panel_id}"
  >
    <span class="summary-label">{_html(label)}</span>
    <span class="summary-count">{count}</span>
  </button>"""


def _sortable_header(
    label: str,
    column: int,
    sort_type: str = "text",
    numeric: bool = False,
) -> str:
    class_name = ' class="numeric"' if numeric else ""
    return f"""<th{class_name} data-sortable aria-sort="none">
  <button
    class="sort-button"
    type="button"
    data-sort-column="{column}"
    data-sort-type="{_html_attr(sort_type)}"
  >
    <span>{_html(label)}</span>
    <span class="sort-indicator" aria-hidden="true"></span>
  </button>
</th>"""


def _item_to_json(item: IssueReviewItem) -> dict[str, object]:
    return {
        "key": item.issue.key,
        "summary": item.issue.summary,
        "epic": item.issue.epic,
        "priority": item.issue.priority,
        "fix_versions": list(item.issue.fix_versions),
        "status": item.issue.status,
        "status_category": item.issue.status_category,
        "assignee": item.issue.assignee,
        "original_estimate_seconds": item.issue.original_estimate_seconds,
        "remaining_estimate_seconds": item.issue.remaining_estimate_seconds,
        "is_over_original_estimate": item.is_over_original_estimate,
        "total_seconds": item.total_seconds,
        "total_hours": round(item.total_hours, 2),
        "tempo_seconds": item.tempo_seconds,
        "tempo_hours": round(item.tempo_hours, 2),
        "total_time_spent_by_user": [
            {
                "user": user_time.user,
                "seconds": user_time.seconds,
                "hours": round(user_time.hours, 2),
            }
            for user_time in item.total_time_spent_by_user
        ],
        "time_spent_by_user": [
            {
                "user": user_time.user,
                "seconds": user_time.seconds,
                "hours": round(user_time.hours, 2),
            }
            for user_time in item.time_spent_by_user
        ],
        "worklog_count": item.worklog_count,
        "authors": list(item.authors),
        "comments": [
            {
                "id": comment.id,
                "author": comment.author,
                "created_at": comment.created_at.isoformat(),
                "body": comment.body,
            }
            for comment in item.comments
        ],
    }


def _has_items(review: SprintReview) -> bool:
    return any(
        (
            review.completed,
            review.unfinished_with_time,
            review.not_started,
        )
    )


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds / 3600
    return f"{hours:.2f} h"


def _sort_seconds(seconds: int | None) -> int:
    return -1 if seconds is None else seconds


def _numeric_cell(seconds: int | None) -> str:
    return (
        f'<td class="numeric" data-sort-value="{_sort_seconds(seconds)}">'
        f"{_html(_format_duration(seconds))}</td>"
    )


def _format_fix_versions(fix_versions: tuple[str, ...]) -> str:
    if not fix_versions:
        return "-"
    return ", ".join(fix_versions)


def _format_bool(value: bool) -> str:
    return "Oui" if value else "Non"


def _format_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return "-"

    return "<br>".join(
        _escape_table(f"{user_time.user}: {_format_duration(user_time.seconds)}")
        for user_time in item.time_spent_by_user
    )


def _format_html_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{_html(user_time.user)}: {_html(_format_duration(user_time.seconds))}"
        for user_time in item.time_spent_by_user
    )
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _format_html_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return '<span class="muted">-</span>'

    lines = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        lines.append(f"{_html(created)} - {_html(author)}: {_html(body)}")
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _plain_time_spent_by_user(item: IssueReviewItem) -> str:
    return " ".join(
        f"{user_time.user}: {_format_duration(user_time.seconds)}"
        for user_time in item.time_spent_by_user
    )


def _plain_comments(item: IssueReviewItem) -> str:
    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(f"{created} - {author}: {body}")
    return " ".join(rendered_comments)


def _format_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return "-"

    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(_escape_table(f"{created} - {author}: {body}"))

    return "<br>".join(rendered_comments)


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
