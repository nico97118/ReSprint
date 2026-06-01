from __future__ import annotations

from resprint.exporters.common import (
    escape_markdown_table,
    format_bool,
    format_changes,
    format_comments,
    format_duration,
    format_fix_versions,
    format_time_spent_by_user,
    has_items,
)
from resprint.frontend.i18n import t
from resprint.logging import get_logger
from resprint.models import IssueReviewItem, Sprint, SprintReview

logger = get_logger(__name__)


def render_markdown(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    logger.info("Rendering Markdown report for sprint %s", sprint.name)
    lines = [
        f"# ReSprint - {sprint.name}",
        "",
        t(
            "report.period_name",
            start=sprint.start_date.isoformat(),
            end=sprint.end_date.isoformat(),
        ),
        "",
    ]

    if not has_items(review):
        logger.info("Markdown report has no issue to render")
        lines.append(t("report.no_issues_in_review"))
        return "\n".join(lines) + "\n"

    lines.extend(
        _render_section(
            t("report.completed_issues"),
            list(review.completed),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            t("report.unfinished_with_time_issues"),
            list(review.unfinished_with_time),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            t("report.not_started_issues"),
            list(review.not_started),
            jira_base_url,
        )
    )
    if review.out_of_sprint:
        lines.extend(
            _render_section(
                t("report.out_of_sprint"),
                list(review.out_of_sprint),
                jira_base_url,
            )
        )

    return "\n".join(lines) + "\n"


def _render_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> list[str]:
    logger.debug("Rendering Markdown section '%s' with %s items", title, len(items))
    lines = [f"## {title}", ""]
    if not items:
        lines.extend([t("report.empty_ticket"), ""])
        return lines

    lines.extend(
        [
            "| "
            f"{t('table.issue_key')} | "
            f"{t('table.title')} | "
            f"{t('table.type')} | "
            f"{t('table.parent')} | "
            f"{t('report.priority')} | "
            f"{t('report.fix_version')} | "
            f"{t('report.original_estimate')} | "
            f"{t('report.remaining_estimate')} | "
            f"{t('table.total_time')} | "
            f"{t('report.spent_during_sprint')} | "
            f"{t('report.over_original_estimate')} | "
            f"{t('report.sprint_time_by_user_markdown')} | "
            f"{t('report.sprint_comments')} | "
            f"{t('report.sprint_activity_markdown')} |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | "
            "--- | --- | --- | --- |",
        ]
    )
    for item in items:
        issue = item.issue
        issue_url = f"{jira_base_url}/browse/{issue.key}"
        lines.append(
            "| "
            f"[{issue.key}]({issue_url}) | "
            f"{escape_markdown_table(issue.summary or '-')} | "
            f"{escape_markdown_table(issue.issue_type or '-')} | "
            f"{escape_markdown_table(issue.parent or '-')} | "
            f"{escape_markdown_table(issue.priority or '-')} | "
            f"{escape_markdown_table(format_fix_versions(issue.fix_versions))} | "
            f"{format_duration(issue.original_estimate_seconds)} | "
            f"{format_duration(issue.remaining_estimate_seconds)} | "
            f"{format_duration(item.total_seconds)} | "
            f"{format_duration(item.tempo_seconds)} | "
            f"{format_bool(item.is_over_original_estimate)} | "
            f"{format_time_spent_by_user(item)} | "
            f"{format_comments(item)} | "
            f"{format_changes(item)} |"
        )

    lines.append("")
    return lines
