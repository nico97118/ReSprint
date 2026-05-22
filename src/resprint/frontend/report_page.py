from __future__ import annotations

import html

from resprint.exporters.common import format_bool, format_duration, format_fix_versions
from resprint.frontend.helpers.page import render_page
from resprint.frontend.helpers.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    render_table_section,
    table_css,
    table_script,
)
from resprint.models import IssueReviewItem, Sprint, SprintReview

REPORT_TABLE_COLUMNS = [
    TableColumn("key", "Issue key"),
    TableColumn("summary", "Titre"),
    TableColumn("epic", "Epopee"),
    TableColumn("priority", "Priorite"),
    TableColumn("fix_versions", "FixVersion"),
    TableColumn(
        "original_estimate", "Temps original estime", numeric=True, sort_type="number"
    ),
    TableColumn(
        "remaining_estimate", "Temps restant estime", numeric=True, sort_type="number"
    ),
    TableColumn("total_time", "Temps total consomme", numeric=True, sort_type="number"),
    TableColumn("sprint_time", "Temps sprint", numeric=True, sort_type="number"),
    TableColumn("overrun", "Depassement", sort_type="number"),
    TableColumn("time_by_user", "Temps sprint par utilisateur", sortable=False),
    TableColumn("comments", "Commentaires sprint", sortable=False),
]


def render_html(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    title = f"ReSprint - {sprint.name}"
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
    content = f"""<p class="period">
      Periode: {_html(sprint.start_date.isoformat())}
      -> {_html(sprint.end_date.isoformat())}
    </p>
    {summary_html}
    {sections_html}"""

    report_css = (
        """
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
      border: 1px solid;
      border-radius: 10px;
      background: var(--summary-background);
      border-color: var(--summary-border);
      cursor: pointer;
      padding: 14px 16px;
      text-align: left;
    }}
    .summary-item[aria-selected="true"] {{
      box-shadow: inset 0 0 0 1px var(--summary-accent);
    }}
    .summary-item:hover {{
      filter: brightness(0.98);
    }}
    html[data-theme="dark"] .summary-item:hover {{
      filter: brightness(1.08);
    }}
    .summary-item-completed {{
      --summary-background: #effaf4;
      --summary-border: #addcc5;
      --summary-accent: #1f7a4d;
    }}
    .summary-item-started {{
      --summary-background: #eef6ff;
      --summary-border: #b7d7ff;
      --summary-accent: #0969da;
    }}
    .summary-item-not-started {{
      --summary-background: #f8fafc;
      --summary-border: #cbd5e1;
      --summary-accent: #64748b;
    }}
    html[data-theme="dark"] .summary-item-completed {{
      --summary-background: #123522;
      --summary-border: #2f6847;
      --summary-accent: #74d99f;
    }}
    html[data-theme="dark"] .summary-item-started {{
      --summary-background: #10243d;
      --summary-border: #27588c;
      --summary-accent: #5aa2ff;
    }}
    html[data-theme="dark"] .summary-item-not-started {{
      --summary-background: #1f2937;
      --summary-border: #475569;
      --summary-accent: #cbd5e1;
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
      background: color-mix(in srgb, var(--summary-accent) 12%, transparent);
      color: var(--summary-accent);
      font-size: 18px;
      font-weight: 720;
    }}
    section {{ margin-top: 30px; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 650; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); }}
    .stack {{ display: grid; gap: 4px; }}
    .comments {{ max-width: 380px; }}
    .empty {{ margin: 0 0 20px; }}
    @media (max-width: 760px) {{
      .summary {{ grid-template-columns: 1fr; }}
    }}
""".format()
        + table_css()
    )
    report_script = (
        """
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
""".format()
        + table_script()
    )

    return render_page(
        title,
        content,
        extra_css=report_css,
        scripts=report_script,
        max_width="1440px",
    )


def _render_html_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> str:
    section_id = _slugify(title)
    if not items:
        return (
            f'<section id="{_html_attr(section_id)}" data-report-panel>'
            f"<h2>{_html(title)}</h2>"
            '<p class="empty">Aucun ticket.</p></section>'
        )

    rows = [_html_row(item, jira_base_url) for item in items]
    return render_table_section(
        section_id=section_id,
        title=title,
        columns=REPORT_TABLE_COLUMNS,
        rows=rows,
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("key"),
        empty_message="Aucun ticket ne correspond a la recherche.",
        section_attributes={
            "data-report-table": "",
            "data-report-panel": "",
        },
    )


def _html_row(item: IssueReviewItem, jira_base_url: str) -> TableRow:
    issue = item.issue
    issue_url = f"{jira_base_url}/browse/{issue.key}"
    overrun_class = "badge-danger" if item.is_over_original_estimate else "badge-ok"
    overrun = _html(format_bool(item.is_over_original_estimate))
    search_text = " ".join(
        (
            issue.key,
            issue.summary,
            issue.epic or "",
            issue.priority or "",
            format_fix_versions(issue.fix_versions),
            format_bool(item.is_over_original_estimate),
            _plain_time_spent_by_user(item),
            _plain_comments(item),
        )
    )
    return TableRow(
        cells={
            "key": TableCell(
                f'<a href="{_html_attr(issue_url)}">{_html(issue.key)}</a>'
            ),
            "summary": TableCell(_html(issue.summary or "-")),
            "epic": TableCell(_html(issue.epic or "-")),
            "priority": TableCell(_html(issue.priority or "-")),
            "fix_versions": TableCell(_html(format_fix_versions(issue.fix_versions))),
            "original_estimate": _duration_cell(issue.original_estimate_seconds),
            "remaining_estimate": _duration_cell(issue.remaining_estimate_seconds),
            "total_time": _duration_cell(item.total_seconds),
            "sprint_time": _duration_cell(item.tempo_seconds),
            "overrun": TableCell(
                f'<span class="badge {overrun_class}">{overrun}</span>',
                sort_value=int(item.is_over_original_estimate),
            ),
            "time_by_user": TableCell(_format_html_time_spent_by_user(item)),
            "comments": TableCell(_format_html_comments(item), class_name="comments"),
        },
        search_text=search_text,
        style=_row_style(item),
    )


def _render_html_summary(review: SprintReview) -> str:
    completed_tab = _render_summary_tab(
        "Tickets termines",
        "Tickets termines",
        len(review.completed),
        "completed",
        True,
    )
    unfinished_tab = _render_summary_tab(
        "Non termines avec temps",
        "Tickets non termines avec du temps consomme",
        len(review.unfinished_with_time),
        "started",
    )
    not_started_tab = _render_summary_tab(
        "Non commences",
        "Tickets non commences",
        len(review.not_started),
        "not-started",
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
    variant: str,
    selected: bool = False,
) -> str:
    panel_id = _html_attr(_slugify(panel_title))
    return f"""<button
    class="summary-item summary-item-{_html_attr(variant)}"
    type="button"
    role="tab"
    aria-selected="{str(selected).lower()}"
    data-report-tab
    data-target-panel="{panel_id}"
  >
    <span class="summary-label">{_html(label)}</span>
    <span class="summary-count">{count}</span>
  </button>"""


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _sort_seconds(seconds: int | None) -> int:
    return -1 if seconds is None else seconds


def _duration_cell(seconds: int | None) -> TableCell:
    return TableCell(_html(format_duration(seconds)), sort_value=_sort_seconds(seconds))


def _row_style(item: IssueReviewItem) -> str | None:
    if item.issue.remaining_estimate_seconds in (None, 0):
        return "error"
    if item.is_over_original_estimate:
        return "warning"
    return None


def _format_html_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{_html(user_time.user)}: {_html(format_duration(user_time.seconds))}"
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
        f"{user_time.user}: {format_duration(user_time.seconds)}"
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


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
