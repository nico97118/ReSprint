from __future__ import annotations

from dataclasses import dataclass

from resprint.exporters.common import format_bool, format_fix_versions
from resprint.frontend.report_formatters import (
    duration_cell,
    format_html_status,
    html_attr,
    html_text,
    plain_changes,
    plain_comments,
    plain_time_spent_by_user,
    render_issue_detail,
    row_style,
    slugify,
)
from resprint.frontend.utils.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableFilter,
    TableRow,
    render_table_section,
)
from resprint.frontend.utils.templates import render_template
from resprint.logging import get_logger
from resprint.models import IssueReviewItem, SprintReview

logger = get_logger(__name__)

REPORT_TABLE_COLUMNS = [
    TableColumn("key", "Issue key"),
    TableColumn("summary", "Titre"),
    TableColumn("issue_type", "Type"),
    TableColumn("status", "Statut"),
    TableColumn("parent", "Parent"),
    TableColumn(
        "original_estimate",
        "Temps original estime",
        short_label="Original",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "remaining_estimate",
        "Temps restant estime",
        short_label="Restant",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "total_time",
        "Temps total consomme",
        short_label="Total",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "sprint_time",
        "Temps sprint",
        short_label="Sprint",
        numeric=True,
        sort_type="number",
    ),
]


@dataclass(frozen=True)
class SummaryTab:
    label: str
    panel_id: str
    count: int
    variant: str
    selected: bool = False


def render_report_sections(review: SprintReview, jira_base_url: str) -> str:
    sections = _report_sections(review)
    logger.debug(
        "HTML report sections: %s",
        [(section_title, len(items)) for section_title, items in sections],
    )
    return "\n".join(
        _render_html_section(title, items, jira_base_url) for title, items in sections
    )


def render_report_summary(review: SprintReview) -> str:
    tabs = [
        SummaryTab(
            label="Tickets termines",
            panel_id=slugify("Tickets termines"),
            count=len(review.completed),
            variant="completed",
            selected=True,
        ),
        SummaryTab(
            label="Non termines avec temps",
            panel_id=slugify("Tickets non termines avec du temps consomme"),
            count=len(review.unfinished_with_time),
            variant="started",
        ),
        SummaryTab(
            label="Non commences",
            panel_id=slugify("Tickets non commences"),
            count=len(review.not_started),
            variant="not-started",
        ),
    ]
    if review.out_of_sprint:
        tabs.append(
            SummaryTab(
                label="Hors sprint",
                panel_id=slugify("Hors sprint"),
                count=len(review.out_of_sprint),
                variant="out-of-sprint",
            )
        )
    return render_template("report_summary.html", tabs=tabs)


def _report_sections(
    review: SprintReview,
) -> list[tuple[str, list[IssueReviewItem]]]:
    sections = [
        ("Tickets termines", list(review.completed)),
        (
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
        ),
        ("Tickets non commences", list(review.not_started)),
    ]
    if review.out_of_sprint:
        sections.append(("Hors sprint", list(review.out_of_sprint)))
    return sections


def _render_html_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> str:
    section_id = slugify(title)
    if not items:
        logger.debug("Rendering empty HTML report section '%s'", title)
        return render_template(
            "report_empty_section.html",
            section_id=section_id,
            title=title,
        )

    logger.debug("Rendering HTML report section '%s' with %s items", title, len(items))
    rows = [_html_row(item, jira_base_url) for item in items]
    return render_table_section(
        section_id=section_id,
        title=title,
        columns=REPORT_TABLE_COLUMNS,
        rows=rows,
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("key"),
        filters=[
            TableFilter("issue_type", "Type", "Tous les types"),
            TableFilter("status", "Statut", "Tous les statuts"),
            TableFilter("parent", "Parent", "Tous les parents"),
        ],
        empty_message="Aucun ticket ne correspond a la recherche.",
        section_attributes={
            "data-report-table": "",
            "data-report-panel": "",
        },
    )


def _html_row(item: IssueReviewItem, jira_base_url: str) -> TableRow:
    issue = item.issue
    issue_url = f"{jira_base_url}/browse/{issue.key}"
    search_text = " ".join(
        (
            issue.key,
            issue.summary,
            issue.issue_type or "",
            issue.status,
            issue.status_category,
            issue.parent or "",
            issue.priority or "",
            format_fix_versions(issue.fix_versions),
            format_bool(item.is_over_original_estimate),
            plain_time_spent_by_user(item),
            plain_comments(item),
            plain_changes(item),
        )
    )
    return TableRow(
        cells={
            "key": TableCell(
                f'<a href="{html_attr(issue_url)}">{html_text(issue.key)}</a>'
            ),
            "summary": TableCell(html_text(issue.summary or "-")),
            "issue_type": TableCell(html_text(issue.issue_type or "-")),
            "status": TableCell(format_html_status(issue)),
            "parent": TableCell(html_text(issue.parent or "-")),
            "original_estimate": duration_cell(issue.original_estimate_seconds),
            "remaining_estimate": duration_cell(issue.remaining_estimate_seconds),
            "total_time": duration_cell(item.total_seconds),
            "sprint_time": duration_cell(item.tempo_seconds),
        },
        search_text=search_text,
        style=row_style(item),
        details_html=render_issue_detail(item),
    )
