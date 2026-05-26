from __future__ import annotations

from resprint.frontend.report.formatters import (
    duration_cell,
    format_html_status,
    html_attr,
    html_text,
    render_issue_detail,
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
from resprint.frontend.view_models.report.tables import (
    IssueRowView,
    ReportTableView,
    build_report_table_views,
    build_summary_tabs,
)
from resprint.logging import get_logger
from resprint.models import SprintReview

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


def render_report_sections(review: SprintReview, jira_base_url: str) -> str:
    tables = build_report_table_views(review, jira_base_url)
    logger.debug(
        "HTML report sections: %s",
        [(table.title, len(table.rows)) for table in tables],
    )
    return "\n".join(_render_html_section(table) for table in tables)


def render_report_summary(review: SprintReview) -> str:
    tabs = build_summary_tabs(review)
    return render_template("components/report/summary.html", tabs=tabs)


def _render_html_section(
    table: ReportTableView,
) -> str:
    if not table.rows:
        logger.debug("Rendering empty HTML report section '%s'", table.title)
        return render_template(
            "components/report/empty_section.html",
            section_id=table.section_id,
            title=table.title,
        )

    logger.debug(
        "Rendering HTML report section '%s' with %s items",
        table.title,
        len(table.rows),
    )
    rows = [_html_row(row) for row in table.rows]
    return render_table_section(
        section_id=table.section_id,
        title=table.title,
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


def _html_row(row: IssueRowView) -> TableRow:
    return TableRow(
        cells={
            "key": TableCell(
                f'<a href="{html_attr(row.issue_url)}">{html_text(row.key)}</a>'
            ),
            "summary": TableCell(html_text(row.summary)),
            "issue_type": TableCell(html_text(row.issue_type)),
            "status": TableCell(format_html_status(row.status)),
            "parent": TableCell(html_text(row.parent)),
            "original_estimate": duration_cell(row.original_estimate),
            "remaining_estimate": duration_cell(row.remaining_estimate),
            "total_time": duration_cell(row.total_time),
            "sprint_time": duration_cell(row.sprint_time),
        },
        search_text=row.search_text,
        style=row.row_style,
        details_html=render_issue_detail(row.detail),
    )
