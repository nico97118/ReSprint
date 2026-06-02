from __future__ import annotations

from resprint.frontend.i18n import t
from resprint.frontend.utils.html import html_text
from resprint.frontend.utils.jira_markup import render_jira_markup
from resprint.frontend.utils.table import TableCell, badge_cell, html_cell, text_cell
from resprint.frontend.utils.templates import render_template
from resprint.frontend.view_models.report.tables import (
    ChangeView,
    CommentView,
    DurationCellView,
    IssueDetailView,
    StatusBadgeView,
    TimeProgressLegendItemView,
    TimeProgressView,
    UserTimeView,
)


def duration_cell(duration: DurationCellView) -> TableCell:
    return text_cell(
        duration.label,
        sort_value=duration.sort_value,
    )


def status_cell(status: StatusBadgeView) -> TableCell:
    return badge_cell(status.label, f"status-{status.category}")


def priority_cell(priority: str) -> TableCell:
    normalized = priority.casefold().strip()
    variant, icon = _priority_variant_icon(normalized)
    if priority == "-":
        return text_cell(priority, sort_value=0)
    return html_cell(
        (
            f'<span class="issue-priority issue-priority-{variant}">'
            f'<span class="mdi {icon} issue-priority-icon" aria-hidden="true"></span>'
            f"<span>{html_text(priority)}</span>"
            "</span>"
        ),
        sort_value=_priority_sort_rank(variant),
    )


def _priority_variant_icon(normalized_priority: str) -> tuple[str, str]:
    if normalized_priority in {"highest", "blocker", "bloquant", "bloquante"}:
        return "highest", "mdi-chevron-double-up"
    if normalized_priority in {"high", "haute", "haut", "major", "majeure"}:
        return "high", "mdi-chevron-up"
    if normalized_priority in {"low", "basse", "bas", "minor", "mineure"}:
        return "low", "mdi-chevron-down"
    if normalized_priority in {"lowest", "trivial", "triviale", "très basse"}:
        return "lowest", "mdi-chevron-double-down"
    return "medium", "mdi-minus"


def _priority_sort_rank(priority_variant: str) -> int:
    return {
        "highest": 90,
        "high": 80,
        "medium": 60,
        "low": 40,
        "lowest": 20,
    }.get(priority_variant, 60)


def render_issue_detail(detail: IssueDetailView) -> str:
    details = [
        _render_issue_detail_item(
            t("report.time_progress"),
            _render_time_progress(detail.progress),
            "issue-detail-item-wide",
        ),
        _render_issue_detail_item(t("report.priority"), html_text(detail.priority)),
        _render_issue_detail_item(
            t("report.fix_version"), html_text(detail.fix_versions)
        ),
        _render_issue_detail_item(
            t("report.sprint_time_by_user_html"),
            format_html_time_spent_by_user(detail.time_spent_by_user),
        ),
        _render_expandable_issue_detail_item(
            t("report.sprint_comments"),
            format_html_comments(detail.comments),
            count=len(detail.comments),
            expanded=True,
        ),
        _render_expandable_issue_detail_item(
            t("report.sprint_activity_html"),
            format_html_changes(detail.changes),
            count=len(detail.changes),
            expanded=False,
        ),
    ]
    rendered_details = "\n".join(details)
    return f'<dl class="issue-detail-grid">{rendered_details}</dl>'


def format_html_time_spent_by_user(time_spent_by_user: tuple[UserTimeView, ...]) -> str:
    if not time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{html_text(user_time.user)}: {html_text(user_time.duration)}"
        for user_time in time_spent_by_user
    )
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def format_html_comments(comments: tuple[CommentView, ...]) -> str:
    if not comments:
        return '<span class="muted">-</span>'

    rendered_comments = [_render_html_comment(comment) for comment in comments]
    return f'<div class="issue-comments">{"".join(rendered_comments)}</div>'


def format_html_changes(changes: tuple[ChangeView, ...]) -> str:
    if not changes:
        return '<span class="muted">-</span>'

    rendered_changes = [_render_html_change(change) for change in changes]
    return f'<div class="issue-changelog">{"".join(rendered_changes)}</div>'


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


def _render_time_progress(progress: TimeProgressView) -> str:
    legend_html = "\n".join(
        _time_progress_legend_item(item) for item in progress.legend_items
    )

    return render_template(
        "components/report/time_progress.html",
        original_width=progress.original_width,
        spent_before_width=progress.spent_before_width,
        sprint_width=progress.sprint_width,
        remaining_width=progress.remaining_width,
        original_duration=progress.original_duration,
        spent_before_duration=progress.spent_before_duration,
        sprint_duration=progress.sprint_duration,
        remaining_duration=progress.remaining_duration,
        projection_duration=progress.projection_duration,
        legend_html=legend_html,
    )


def _time_progress_legend_item(item: TimeProgressLegendItemView) -> str:
    return (
        f'<span><span class="time-progress-dot time-progress-dot-{item.variant}">'
        f"</span>{html_text(item.label)}</span>"
    )


def _render_html_comment(comment: CommentView) -> str:
    return render_template(
        "components/report/issue_comment.html",
        created=comment.created,
        author=comment.author,
        body_html=render_jira_markup(comment.body),
    )


def _render_html_change(change: ChangeView) -> str:
    return render_template(
        "components/report/issue_change.html",
        created=change.created,
        author=change.author,
        field=change.field,
        from_value=change.from_value,
        to_value=change.to_value,
    )
