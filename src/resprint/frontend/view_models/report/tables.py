from __future__ import annotations

import re
from dataclasses import dataclass

from resprint.exporters.common import format_bool, format_duration, format_fix_versions
from resprint.frontend.i18n import t
from resprint.models import Issue, IssueReviewItem, SprintReview


@dataclass(frozen=True)
class DurationCellView:
    label: str
    sort_value: int


@dataclass(frozen=True)
class StatusBadgeView:
    label: str
    category: str


@dataclass(frozen=True)
class UserTimeView:
    user: str
    duration: str


@dataclass(frozen=True)
class CommentView:
    author: str
    created: str
    body: str


@dataclass(frozen=True)
class ChangeView:
    author: str
    created: str
    field: str
    from_value: str
    to_value: str


@dataclass(frozen=True)
class TimeProgressLegendItemView:
    variant: str
    label: str


@dataclass(frozen=True)
class TimeProgressView:
    original_width: str
    spent_before_width: str
    sprint_width: str
    remaining_width: str
    original_duration: str
    spent_before_duration: str
    sprint_duration: str
    remaining_duration: str
    projection_duration: str
    legend_items: tuple[TimeProgressLegendItemView, ...]


@dataclass(frozen=True)
class IssueDetailView:
    progress: TimeProgressView
    priority: str
    fix_versions: str
    time_spent_by_user: tuple[UserTimeView, ...]
    comments: tuple[CommentView, ...]
    changes: tuple[ChangeView, ...]


@dataclass(frozen=True)
class IssueRowView:
    key: str
    issue_url: str
    summary: str
    issue_type: str
    priority: str
    status: StatusBadgeView
    parent: str
    assignee: str
    original_estimate: DurationCellView
    remaining_estimate: DurationCellView
    total_time: DurationCellView
    sprint_time: DurationCellView
    row_style: str | None
    search_text: str
    detail: IssueDetailView


@dataclass(frozen=True)
class ReportTableView:
    title: str
    section_id: str
    rows: tuple[IssueRowView, ...]


@dataclass(frozen=True)
class SummaryTabView:
    label: str
    panel_id: str
    count: int
    variant: str
    selected: bool = False


def build_report_table_views(
    review: SprintReview,
    jira_base_url: str,
) -> tuple[ReportTableView, ...]:
    return tuple(
        ReportTableView(
            title=title,
            section_id=slugify(title),
            rows=tuple(_issue_row_view(item, jira_base_url) for item in items),
        )
        for title, items in _report_sections(review)
    )


def build_summary_tabs(review: SprintReview) -> tuple[SummaryTabView, ...]:
    tabs = [
        SummaryTabView(
            label=t("report.completed_issues"),
            panel_id=slugify(t("report.completed_issues")),
            count=len(review.completed),
            variant="completed",
            selected=True,
        ),
        SummaryTabView(
            label=t("report.unfinished_with_time_short"),
            panel_id=slugify(t("report.unfinished_with_time_issues")),
            count=len(review.unfinished_with_time),
            variant="started",
        ),
        SummaryTabView(
            label=t("report.not_started_short"),
            panel_id=slugify(t("report.not_started_issues")),
            count=len(review.not_started),
            variant="not-started",
        ),
    ]
    if review.out_of_sprint:
        tabs.append(
            SummaryTabView(
                label=t("report.out_of_sprint"),
                panel_id=slugify(t("report.out_of_sprint")),
                count=len(review.out_of_sprint),
                variant="out-of-sprint",
            )
        )
    return tuple(tabs)


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _report_sections(
    review: SprintReview,
) -> tuple[tuple[str, tuple[IssueReviewItem, ...]], ...]:
    sections = [
        (t("report.completed_issues"), review.completed),
        (t("report.unfinished_with_time_issues"), review.unfinished_with_time),
        (t("report.not_started_issues"), review.not_started),
    ]
    if review.out_of_sprint:
        sections.append((t("report.out_of_sprint"), review.out_of_sprint))
    return tuple(sections)


def _issue_row_view(item: IssueReviewItem, jira_base_url: str) -> IssueRowView:
    issue = item.issue
    detail = _issue_detail_view(item)
    issue_type = issue.issue_type or "-"
    priority = issue.priority or "-"
    parent = issue.parent or "-"
    assignee = issue.assignee or "-"
    return IssueRowView(
        key=issue.key,
        issue_url=f"{jira_base_url}/browse/{issue.key}",
        summary=issue.summary or "-",
        issue_type=issue_type,
        priority=priority,
        status=_status_badge(issue),
        parent=parent,
        assignee=assignee,
        original_estimate=_duration_view(issue.original_estimate_seconds),
        remaining_estimate=_duration_view(issue.remaining_estimate_seconds),
        total_time=_duration_view(item.total_seconds),
        sprint_time=_duration_view(item.tempo_seconds),
        row_style=_row_style(item),
        search_text=_search_text(item, detail),
        detail=detail,
    )


def _issue_detail_view(item: IssueReviewItem) -> IssueDetailView:
    issue = item.issue
    return IssueDetailView(
        progress=_time_progress_view(item),
        priority=issue.priority or "-",
        fix_versions=format_fix_versions(issue.fix_versions),
        time_spent_by_user=tuple(
            UserTimeView(
                user=user_time.user,
                duration=format_duration(user_time.seconds),
            )
            for user_time in item.time_spent_by_user
        ),
        comments=tuple(
            CommentView(
                author=comment.author or t("report.unknown_author"),
                created=comment.created_at.strftime("%Y-%m-%d %H:%M"),
                body=comment.body or t("report.empty_comment"),
            )
            for comment in item.comments
        ),
        changes=tuple(
            ChangeView(
                author=change.author or t("report.unknown_author"),
                created=change.created_at.strftime("%Y-%m-%d %H:%M"),
                field=change.field or t("report.unknown_field"),
                from_value=change.from_value or "-",
                to_value=change.to_value or "-",
            )
            for change in item.changes
        ),
    )


def _time_progress_view(item: IssueReviewItem) -> TimeProgressView:
    issue = item.issue
    original_seconds = issue.original_estimate_seconds or 0
    remaining_seconds = issue.remaining_estimate_seconds or 0
    sprint_seconds = max(item.tempo_seconds, 0)
    spent_before_sprint_seconds = max(item.total_seconds - sprint_seconds, 0)
    projection_seconds = (
        spent_before_sprint_seconds + sprint_seconds + remaining_seconds
    )
    scale_seconds = max(original_seconds, projection_seconds, 1)

    return TimeProgressView(
        original_width=_width_percent(original_seconds, scale_seconds),
        spent_before_width=_width_percent(spent_before_sprint_seconds, scale_seconds),
        sprint_width=_width_percent(sprint_seconds, scale_seconds),
        remaining_width=_width_percent(remaining_seconds, scale_seconds),
        original_duration=format_duration(original_seconds),
        spent_before_duration=format_duration(spent_before_sprint_seconds),
        sprint_duration=format_duration(sprint_seconds),
        remaining_duration=format_duration(remaining_seconds),
        projection_duration=format_duration(projection_seconds),
        legend_items=(
            TimeProgressLegendItemView(
                "original", t("report.original_estimated_short")
            ),
            TimeProgressLegendItemView("spent-before", t("report.spent_before")),
            TimeProgressLegendItemView("spent-sprint", t("report.sprint")),
            TimeProgressLegendItemView("remaining", t("report.remaining_short")),
        ),
    )


def _status_badge(issue: Issue) -> StatusBadgeView:
    status = issue.status or "-"
    category = issue.status_category or "unknown"
    normalized_category = re.sub(r"[^a-z0-9_-]+", "-", category.lower()).strip("-")
    if normalized_category not in {"new", "indeterminate", "done"}:
        normalized_category = "unknown"
    return StatusBadgeView(label=status, category=normalized_category)


def _duration_view(seconds: int | None) -> DurationCellView:
    return DurationCellView(
        label=format_duration(seconds),
        sort_value=-1 if seconds is None else seconds,
    )


def _row_style(item: IssueReviewItem) -> str | None:
    if (
        item.issue.remaining_estimate_seconds in (None, 0)
        and item.issue.status_category != "done"
    ):
        return "error"
    if item.is_over_original_estimate:
        return "warning"
    return None


def _search_text(item: IssueReviewItem, detail: IssueDetailView) -> str:
    issue = item.issue
    return " ".join(
        (
            issue.key,
            issue.summary,
            issue.issue_type or "",
            issue.status,
            issue.status_category,
            issue.parent or "",
            issue.assignee or "",
            detail.priority,
            detail.fix_versions,
            format_bool(item.is_over_original_estimate),
            _plain_time_spent_by_user(detail),
            _plain_comments(detail),
            _plain_changes(detail),
        )
    )


def _plain_time_spent_by_user(detail: IssueDetailView) -> str:
    return " ".join(
        f"{user_time.user}: {user_time.duration}"
        for user_time in detail.time_spent_by_user
    )


def _plain_comments(detail: IssueDetailView) -> str:
    return " ".join(
        f"{comment.created} - {comment.author}: {comment.body}"
        for comment in detail.comments
    )


def _plain_changes(detail: IssueDetailView) -> str:
    return " ".join(
        (
            f"{change.created} - {change.author}: "
            f"{change.field}: {change.from_value} -> {change.to_value}"
        )
        for change in detail.changes
    )


def _width_percent(seconds: int, scale_seconds: int) -> str:
    if seconds <= 0:
        return "0.0000"
    return f"{seconds / scale_seconds * 100:.4f}"
