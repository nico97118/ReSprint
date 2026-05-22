from __future__ import annotations

import html
import json
from dataclasses import asdict

from sprint_review.models import IssueReviewItem, Sprint, SprintReview
from sprint_review.table_renderer import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    render_table_section,
    table_css,
    table_script,
)
from sprint_review.ui_assets import render_page

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
    overrun = _html(_format_bool(item.is_over_original_estimate))
    search_text = " ".join(
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
    )
    return TableRow(
        cells={
            "key": TableCell(
                f'<a href="{_html_attr(issue_url)}">{_html(issue.key)}</a>'
            ),
            "summary": TableCell(_html(issue.summary or "-")),
            "epic": TableCell(_html(issue.epic or "-")),
            "priority": TableCell(_html(issue.priority or "-")),
            "fix_versions": TableCell(_html(_format_fix_versions(issue.fix_versions))),
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


def _duration_cell(seconds: int | None) -> TableCell:
    return TableCell(
        _html(_format_duration(seconds)), sort_value=_sort_seconds(seconds)
    )


def _row_style(item: IssueReviewItem) -> str | None:
    if item.issue.remaining_estimate_seconds in (None, 0):
        return "error"
    if item.is_over_original_estimate:
        return "warning"
    return None


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
