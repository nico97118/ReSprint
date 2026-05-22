from __future__ import annotations

from resprint.models import IssueReviewItem, SprintReview


def item_to_json(item: IssueReviewItem) -> dict[str, object]:
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


def has_items(review: SprintReview) -> bool:
    return any(
        (
            review.completed,
            review.unfinished_with_time,
            review.not_started,
        )
    )


def escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds / 3600
    return f"{hours:.2f} h"


def format_fix_versions(fix_versions: tuple[str, ...]) -> str:
    if not fix_versions:
        return "-"
    return ", ".join(fix_versions)


def format_bool(value: bool) -> str:
    return "Oui" if value else "Non"


def format_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return "-"

    return "<br>".join(
        escape_markdown_table(f"{user_time.user}: {format_duration(user_time.seconds)}")
        for user_time in item.time_spent_by_user
    )


def format_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return "-"

    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(escape_markdown_table(f"{created} - {author}: {body}"))

    return "<br>".join(rendered_comments)
