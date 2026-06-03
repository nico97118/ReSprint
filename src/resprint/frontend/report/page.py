from __future__ import annotations

from resprint.frontend.report.exports import (
    jira_jql_url,
    render_export_actions,
    report_export_json,
    report_export_markdown,
)
from resprint.frontend.report.kpis import render_kpi_section
from resprint.frontend.report.tables import (
    render_report_sections,
    render_report_summary,
)
from resprint.frontend.utils.page import asset_url, render_page
from resprint.frontend.utils.table import table_css, table_script
from resprint.frontend.utils.templates import render_template
from resprint.logging import get_logger
from resprint.models import Sprint, SprintReview

logger = get_logger(__name__)


def render_html(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
    jql: str | None = None,
    participants: tuple[str, ...] = (),
) -> str:
    logger.info("Rendering HTML report for sprint %s", sprint.name)
    title = sprint.name
    sections_html = render_report_sections(review, jira_base_url)
    summary_html = render_report_summary(review)
    kpi_section_html = render_kpi_section(review)
    export_json = report_export_json(review, sprint, jql)
    export_markdown = report_export_markdown(review, sprint, jira_base_url)
    content = render_template(
        "pages/report.html",
        sprint=sprint,
        jql=jql,
        participants=participants,
        jira_jql_url=jira_jql_url(jira_base_url, jql),
        export_json=export_json,
        export_markdown=export_markdown,
        kpi_section_html=kpi_section_html,
        summary_html=summary_html,
        sections_html=sections_html,
    )

    return render_page(
        title,
        content,
        header_actions=render_export_actions(sprint),
        stylesheets=(
            asset_url("min/common.min.css"),
            asset_url("min/report.min.css"),
            table_css(),
        ),
        head_scripts=(asset_url("min/theme.min.js"),),
        scripts=(
            table_script(),
            asset_url("vendor/chartjs/chart.umd.js"),
            asset_url("min/charts.min.js"),
            asset_url("min/report.min.js"),
        ),
    )
