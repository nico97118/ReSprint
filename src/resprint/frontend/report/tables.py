from __future__ import annotations

from resprint.frontend.i18n import t
from resprint.frontend.report.formatters import (
    duration_cell,
    priority_cell,
    render_issue_detail,
    status_cell,
)
from resprint.frontend.utils.table import (
    DefaultSort,
    TableColumn,
    TableFilter,
    TableRow,
    link_cell,
    render_table_section,
    text_cell,
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
        columns=_report_table_columns(),
        rows=rows,
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("key"),
        filters=[
            TableFilter("issue_type", t("table.type"), t("table.all_types")),
            TableFilter("priority", t("report.priority"), t("table.all_priorities")),
            TableFilter("status", t("table.status"), t("table.all_statuses")),
            TableFilter("parent", t("table.parent"), t("table.all_parents")),
            TableFilter("assignee", t("table.assignee"), t("table.all_assignees")),
        ],
        empty_message=t("table.no_matching_issue"),
        section_attributes={
            "data-report-table": "",
            "data-report-panel": "",
        },
    )


def _html_row(row: IssueRowView) -> TableRow:
    return TableRow(
        cells={
            "key": link_cell(row.key, row.issue_url),
            "summary": text_cell(row.summary),
            "issue_type": text_cell(row.issue_type),
            "priority": priority_cell(row.priority),
            "status": status_cell(row.status),
            "parent": text_cell(row.parent),
            "assignee": text_cell(row.assignee),
            "original_estimate": duration_cell(row.original_estimate),
            "remaining_estimate": duration_cell(row.remaining_estimate),
            "total_time": duration_cell(row.total_time),
            "sprint_time": duration_cell(row.sprint_time),
        },
        search_text=row.search_text,
        style=row.row_style,
        details_html=render_issue_detail(row.detail),
    )


def _report_table_columns() -> list[TableColumn]:
    return [
        TableColumn("key", t("table.issue_key")),
        TableColumn("summary", t("table.title")),
        TableColumn("issue_type", t("table.type")),
        TableColumn("priority", t("report.priority")),
        TableColumn("status", t("table.status")),
        TableColumn("parent", t("table.parent")),
        TableColumn(
            "assignee",
            t("table.assignee"),
            short_label=t("table.assignee_short"),
        ),
        TableColumn(
            "original_estimate",
            t("report.original_estimate"),
            short_label=t("table.original"),
            numeric=True,
            sort_type="number",
        ),
        TableColumn(
            "remaining_estimate",
            t("report.remaining_estimate"),
            short_label=t("table.remaining"),
            numeric=True,
            sort_type="number",
        ),
        TableColumn(
            "total_time",
            t("table.total_time"),
            short_label=t("table.total"),
            numeric=True,
            sort_type="number",
        ),
        TableColumn(
            "sprint_time",
            t("table.sprint_time"),
            short_label=t("table.sprint"),
            numeric=True,
            sort_type="number",
        ),
    ]
