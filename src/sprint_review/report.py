from __future__ import annotations

import json
from dataclasses import asdict

from sprint_review.models import IssueReviewItem, Sprint, SprintReview


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
            "| Issue key | Epopee | Priorite | FixVersion | Temps original estime | "
            "Temps restant estime | Temps total consomme | "
            "Temps consomme durant le sprint | "
            "Temps original depasse | "
            "Temps consomme par utilisateur | "
            "Commentaires durant le sprint |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for item in items:
        issue = item.issue
        issue_url = f"{jira_base_url}/browse/{issue.key}"
        lines.append(
            "| "
            f"[{issue.key}]({issue_url}) | "
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


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds / 3600
    return f"{hours:.2f} h"


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
