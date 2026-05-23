from __future__ import annotations

from resprint.exporters.common import (
    escape_markdown_table,
    format_bool,
    format_comments,
    format_duration,
    format_fix_versions,
    format_time_spent_by_user,
    has_items,
)
from resprint.models import IssueReviewItem, Sprint, SprintReview


def render_markdown(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    lines = [
        f"# ReSprint - {sprint.name}",
        "",
        f"Periode: {sprint.start_date.isoformat()} -> {sprint.end_date.isoformat()}",
        "",
    ]

    if not has_items(review):
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
            "| Issue key | Titre | Type | Epopee | Priorite | FixVersion | "
            "Temps original estime | Temps restant estime | Temps total consomme | "
            "Temps consomme durant le sprint | "
            "Temps original depasse | "
            "Temps consomme par utilisateur | "
            "Commentaires durant le sprint |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | "
            "--- | --- | --- |",
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
            f"{escape_markdown_table(issue.epic or '-')} | "
            f"{escape_markdown_table(issue.priority or '-')} | "
            f"{escape_markdown_table(format_fix_versions(issue.fix_versions))} | "
            f"{format_duration(issue.original_estimate_seconds)} | "
            f"{format_duration(issue.remaining_estimate_seconds)} | "
            f"{format_duration(item.total_seconds)} | "
            f"{format_duration(item.tempo_seconds)} | "
            f"{format_bool(item.is_over_original_estimate)} | "
            f"{format_time_spent_by_user(item)} | "
            f"{format_comments(item)} |"
        )

    lines.append("")
    return lines
