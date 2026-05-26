from __future__ import annotations

import html
import re

from resprint.exporters.common import format_duration, format_fix_versions
from resprint.frontend.utils.jira_markup import render_jira_markup
from resprint.frontend.utils.table import TableCell
from resprint.frontend.utils.templates import render_template
from resprint.models import Issue, IssueReviewItem, JiraComment, JiraIssueChange


def html_text(value: object) -> str:
    return html.escape(str(value), quote=False)


def html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def duration_cell(seconds: int | None) -> TableCell:
    return TableCell(
        html_text(format_duration(seconds)),
        sort_value=_sort_seconds(seconds),
    )


def row_style(item: IssueReviewItem) -> str | None:
    if (
        item.issue.remaining_estimate_seconds in (None, 0)
        and item.issue.status_category != "done"
    ):
        return "error"
    if item.is_over_original_estimate:
        return "warning"
    return None


def format_html_status(issue: Issue) -> str:
    status = issue.status or "-"
    category = issue.status_category or "unknown"
    normalized_category = re.sub(r"[^a-z0-9_-]+", "-", category.lower()).strip("-")
    if normalized_category not in {"new", "indeterminate", "done"}:
        normalized_category = "unknown"
    return (
        f'<span class="badge badge-status-{normalized_category}">'
        f"{html_text(status)}</span>"
    )


def render_issue_detail(item: IssueReviewItem) -> str:
    issue = item.issue
    details = [
        _render_issue_detail_item(
            "Progression temps", _render_time_progress(item), "issue-detail-item-wide"
        ),
        _render_issue_detail_item("Priorite", html_text(issue.priority or "-")),
        _render_issue_detail_item(
            "FixVersion", html_text(format_fix_versions(issue.fix_versions))
        ),
        _render_issue_detail_item(
            "Temps sprint par utilisateur", format_html_time_spent_by_user(item)
        ),
        _render_expandable_issue_detail_item(
            "Commentaires sprint",
            format_html_comments(item),
            count=len(item.comments),
            expanded=True,
        ),
        _render_expandable_issue_detail_item(
            "Activite sprint",
            format_html_changes(item),
            count=len(item.changes),
            expanded=False,
        ),
    ]
    rendered_details = "\n".join(details)
    return f'<dl class="issue-detail-grid">{rendered_details}</dl>'


def format_html_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{html_text(user_time.user)}: {html_text(format_duration(user_time.seconds))}"
        for user_time in item.time_spent_by_user
    )
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def format_html_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return '<span class="muted">-</span>'

    rendered_comments = [_render_html_comment(comment) for comment in item.comments]
    return f'<div class="issue-comments">{"".join(rendered_comments)}</div>'


def format_html_changes(item: IssueReviewItem) -> str:
    if not item.changes:
        return '<span class="muted">-</span>'

    rendered_changes = [_render_html_change(change) for change in item.changes]
    return f'<div class="issue-changelog">{"".join(rendered_changes)}</div>'


def plain_time_spent_by_user(item: IssueReviewItem) -> str:
    return " ".join(
        f"{user_time.user}: {format_duration(user_time.seconds)}"
        for user_time in item.time_spent_by_user
    )


def plain_comments(item: IssueReviewItem) -> str:
    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(f"{created} - {author}: {body}")
    return " ".join(rendered_comments)


def plain_changes(item: IssueReviewItem) -> str:
    rendered_changes = []
    for change in item.changes:
        author = change.author or "Auteur inconnu"
        created = change.created_at.strftime("%Y-%m-%d %H:%M")
        field = change.field or "champ inconnu"
        from_value = change.from_value or "-"
        to_value = change.to_value or "-"
        rendered_changes.append(
            f"{created} - {author}: {field}: {from_value} -> {to_value}"
        )
    return " ".join(rendered_changes)


def _sort_seconds(seconds: int | None) -> int:
    return -1 if seconds is None else seconds


def _render_issue_detail_item(label: str, value: str, css_class: str = "") -> str:
    classes = f"issue-detail-item {css_class}".strip()
    return render_template(
        "components/report/issue_detail_item.html",
        classes=classes,
        label=label,
        value=value,
    )


def _render_expandable_issue_detail_item(
    label: str,
    content: str,
    *,
    count: int,
    expanded: bool,
) -> str:
    classes = "issue-detail-item issue-detail-item-wide issue-detail-item-expandable"
    return render_template(
        "components/report/issue_detail_expandable.html",
        classes=classes,
        label=label,
        content=content,
        count=count,
        expanded=expanded,
    )


def _render_time_progress(item: IssueReviewItem) -> str:
    issue = item.issue
    original_seconds = issue.original_estimate_seconds or 0
    remaining_seconds = issue.remaining_estimate_seconds or 0
    sprint_seconds = max(item.tempo_seconds, 0)
    spent_before_sprint_seconds = max(item.total_seconds - sprint_seconds, 0)
    projection_seconds = (
        spent_before_sprint_seconds + sprint_seconds + remaining_seconds
    )
    scale_seconds = max(original_seconds, projection_seconds, 1)

    original_width = _width_percent(original_seconds, scale_seconds)
    spent_before_width = _width_percent(spent_before_sprint_seconds, scale_seconds)
    sprint_width = _width_percent(sprint_seconds, scale_seconds)
    remaining_width = _width_percent(remaining_seconds, scale_seconds)
    original_duration = format_duration(original_seconds)
    spent_before_duration = format_duration(spent_before_sprint_seconds)
    sprint_duration = format_duration(sprint_seconds)
    remaining_duration = format_duration(remaining_seconds)
    projection_duration = format_duration(projection_seconds)
    legend_html = "\n".join(
        (
            _time_progress_legend_item("original", "Original estime"),
            _time_progress_legend_item("spent-before", "Deja consomme"),
            _time_progress_legend_item("spent-sprint", "Sprint"),
            _time_progress_legend_item("remaining", "Restant"),
        )
    )

    return render_template(
        "components/report/time_progress.html",
        original_width=f"{original_width:.4f}",
        spent_before_width=f"{spent_before_width:.4f}",
        sprint_width=f"{sprint_width:.4f}",
        remaining_width=f"{remaining_width:.4f}",
        original_duration=original_duration,
        spent_before_duration=spent_before_duration,
        sprint_duration=sprint_duration,
        remaining_duration=remaining_duration,
        projection_duration=projection_duration,
        legend_html=legend_html,
    )


def _time_progress_legend_item(variant: str, label: str) -> str:
    return (
        f'<span><span class="time-progress-dot time-progress-dot-{variant}">'
        f"</span>{html_text(label)}</span>"
    )


def _width_percent(seconds: int, scale_seconds: int) -> float:
    if seconds <= 0:
        return 0
    return seconds / scale_seconds * 100


def _render_html_comment(comment: JiraComment) -> str:
    author = comment.author or "Auteur inconnu"
    created = comment.created_at.strftime("%Y-%m-%d %H:%M")
    body = comment.body or "(commentaire vide)"
    return render_template(
        "components/report/issue_comment.html",
        created=created,
        author=author,
        body_html=render_jira_markup(body),
    )


def _render_html_change(change: JiraIssueChange) -> str:
    author = change.author or "Auteur inconnu"
    created = change.created_at.strftime("%Y-%m-%d %H:%M")
    field = change.field or "champ inconnu"
    from_value = change.from_value or "-"
    to_value = change.to_value or "-"
    return render_template(
        "components/report/issue_change.html",
        created=created,
        author=author,
        field=field,
        from_value=from_value,
        to_value=to_value,
    )
