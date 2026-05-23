from __future__ import annotations

import html
from dataclasses import dataclass

from resprint.exporters.common import format_bool, format_duration, format_fix_versions
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


@dataclass(frozen=True)
class SummaryTab:
    label: str
    panel_id: str
    count: int
    variant: str
    selected: bool = False


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
    content = render_template(
        "report.html",
        sprint=sprint,
        summary_html=summary_html,
        sections_html=sections_html,
    )
    report_css = static_text("report.css") + table_css()
    report_script = static_text("report.js") + table_script()

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
        return render_template(
            "report_empty_section.html",
            section_id=section_id,
            title=title,
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
    tabs = [
        SummaryTab(
            label="Tickets termines",
            panel_id=_slugify("Tickets termines"),
            count=len(review.completed),
            variant="completed",
            selected=True,
        ),
        SummaryTab(
            label="Non termines avec temps",
            panel_id=_slugify("Tickets non termines avec du temps consomme"),
            count=len(review.unfinished_with_time),
            variant="started",
        ),
        SummaryTab(
            label="Non commences",
            panel_id=_slugify("Tickets non commences"),
            count=len(review.not_started),
            variant="not-started",
        ),
    ]
    return render_template("report_summary.html", tabs=tabs)


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
