from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from resprint.exporters.common import format_duration
from resprint.frontend.i18n import t
from resprint.models import IssueReviewItem, SprintReview


@dataclass(frozen=True)
class TicketProgressSegmentView:
    label: str
    count: int
    percentage: int
    variant: str


@dataclass(frozen=True)
class TicketProgressView:
    total: int
    segments: tuple[TicketProgressSegmentView, ...]
    aria_label: str


@dataclass(frozen=True)
class TimeRatioSegmentView:
    label: str
    seconds: int
    duration: str
    percentage: int
    variant: str


@dataclass(frozen=True)
class TimeRatioView:
    total_time: str
    segments: tuple[TimeRatioSegmentView, ...]
    aria_label: str


@dataclass(frozen=True)
class ConsumedTimeComparisonView:
    issue_types: tuple[str, ...]
    sprint_seconds: dict[str, int]
    out_of_sprint_seconds: dict[str, int]

    @property
    def is_empty(self) -> bool:
        return not self.issue_types


@dataclass(frozen=True)
class EstimateProjectionView:
    issue_types: tuple[str, ...]
    original_seconds: dict[str, int]
    spent_before_sprint_seconds: dict[str, int]
    sprint_seconds: dict[str, int]
    remaining_seconds: dict[str, int]

    @property
    def is_empty(self) -> bool:
        return not any(
            self.original_seconds.get(issue_type, 0)
            or self.spent_before_sprint_seconds.get(issue_type, 0)
            or self.sprint_seconds.get(issue_type, 0)
            or self.remaining_seconds.get(issue_type, 0)
            for issue_type in self.issue_types
        )


@dataclass(frozen=True)
class IssueTypeTimeView:
    issue_type: str
    seconds: int
    duration: str


@dataclass(frozen=True)
class IssueTypeTimeKpiView:
    chart_id: str
    total_time: str
    total_label: str
    empty_message: str
    issue_type_times: tuple[IssueTypeTimeView, ...]


@dataclass(frozen=True)
class ReportKpiView:
    ticket_progress: TicketProgressView
    consumed_time_ratio: TimeRatioView
    consumed_time_comparison: ConsumedTimeComparisonView
    sprint_time: IssueTypeTimeKpiView
    out_of_sprint_time: IssueTypeTimeKpiView
    estimate_projection: EstimateProjectionView
    original_estimate_time: IssueTypeTimeKpiView
    remaining_estimate_time: IssueTypeTimeKpiView


def build_report_kpis(review: SprintReview) -> ReportKpiView:
    review_items = _review_items(review)
    return ReportKpiView(
        ticket_progress=_ticket_progress(review),
        consumed_time_ratio=_consumed_time_ratio(review, review_items),
        consumed_time_comparison=_consumed_time_comparison(review, review_items),
        sprint_time=_issue_type_time_kpi(
            review_items,
            total_label=t("report.total_sprint_time"),
            empty_message=t("report.no_time"),
            seconds_getter=lambda item: item.tempo_seconds,
        ),
        out_of_sprint_time=_issue_type_time_kpi(
            review.out_of_sprint,
            total_label=t("report.total_out_of_sprint_time"),
            empty_message=t("report.no_out_of_sprint_time"),
            seconds_getter=lambda item: item.tempo_seconds,
        ),
        estimate_projection=_estimate_projection(review_items),
        original_estimate_time=_issue_type_time_kpi(
            review_items,
            total_label=t("report.total_original_estimate"),
            empty_message=t("report.no_original_estimate"),
            seconds_getter=lambda item: item.issue.original_estimate_seconds,
        ),
        remaining_estimate_time=_issue_type_time_kpi(
            review_items,
            total_label=t("report.total_remaining_estimate"),
            empty_message=t("report.no_remaining_estimate"),
            seconds_getter=lambda item: item.issue.remaining_estimate_seconds,
        ),
    )


def _ticket_progress(review: SprintReview) -> TicketProgressView:
    counts = (
        (t("report.completed_short"), len(review.completed), "completed"),
        (t("report.started_short"), len(review.unfinished_with_time), "started"),
        (t("report.not_started_short"), len(review.not_started), "not-started"),
    )
    total = sum(count for _, count, _ in counts)
    segments = tuple(
        TicketProgressSegmentView(
            label=label,
            count=count,
            percentage=_percentage(count, total),
            variant=variant,
        )
        for label, count, variant in counts
    )
    return TicketProgressView(
        total=total,
        segments=segments,
        aria_label=", ".join(
            (
                f"{segment.label}: {segment.count} "
                f"{t('report.ticket_label').lower()}, {segment.percentage}%"
            )
            for segment in segments
        ),
    )


def _consumed_time_ratio(
    review: SprintReview,
    review_items: tuple[IssueReviewItem, ...],
) -> TimeRatioView:
    sprint_seconds = sum(item.tempo_seconds for item in review_items)
    out_of_sprint_seconds = sum(item.tempo_seconds for item in review.out_of_sprint)
    total_seconds = sprint_seconds + out_of_sprint_seconds
    segments = (
        TimeRatioSegmentView(
            label=t("report.sprint"),
            seconds=sprint_seconds,
            duration=format_duration(sprint_seconds),
            percentage=_percentage(sprint_seconds, total_seconds),
            variant="sprint",
        ),
        TimeRatioSegmentView(
            label=t("report.out_of_sprint"),
            seconds=out_of_sprint_seconds,
            duration=format_duration(out_of_sprint_seconds),
            percentage=_percentage(out_of_sprint_seconds, total_seconds),
            variant="out-of-sprint",
        ),
    )
    return TimeRatioView(
        total_time=format_duration(total_seconds),
        segments=segments,
        aria_label=", ".join(
            f"{segment.label}: {segment.duration}, {segment.percentage}%"
            for segment in segments
        ),
    )


def _consumed_time_comparison(
    review: SprintReview,
    review_items: tuple[IssueReviewItem, ...],
) -> ConsumedTimeComparisonView:
    sprint_seconds = _tempo_seconds_by_issue_type(review_items)
    out_of_sprint_seconds = _tempo_seconds_by_issue_type(review.out_of_sprint)
    issue_types = tuple(
        sorted(
            sprint_seconds.keys() | out_of_sprint_seconds.keys(),
            key=lambda issue_type: (
                -(
                    sprint_seconds.get(issue_type, 0)
                    + out_of_sprint_seconds.get(issue_type, 0)
                ),
                issue_type,
            ),
        )
    )
    return ConsumedTimeComparisonView(
        issue_types=issue_types,
        sprint_seconds=sprint_seconds,
        out_of_sprint_seconds=out_of_sprint_seconds,
    )


def _estimate_projection(
    review_items: tuple[IssueReviewItem, ...],
) -> EstimateProjectionView:
    original_seconds: dict[str, int] = {}
    spent_before_sprint_seconds: dict[str, int] = {}
    sprint_seconds: dict[str, int] = {}
    remaining_seconds: dict[str, int] = {}
    for item in review_items:
        issue_type = item.issue.issue_type or t("report.no_issue_type")
        original_seconds[issue_type] = original_seconds.get(issue_type, 0) + (
            item.issue.original_estimate_seconds or 0
        )
        spent_before_sprint_seconds[issue_type] = spent_before_sprint_seconds.get(
            issue_type, 0
        ) + max(item.total_seconds - item.tempo_seconds, 0)
        sprint_seconds[issue_type] = (
            sprint_seconds.get(issue_type, 0) + item.tempo_seconds
        )
        remaining_seconds[issue_type] = remaining_seconds.get(issue_type, 0) + (
            item.issue.remaining_estimate_seconds or 0
        )

    issue_types = tuple(
        sorted(
            original_seconds.keys()
            | spent_before_sprint_seconds.keys()
            | sprint_seconds.keys()
            | remaining_seconds.keys(),
            key=lambda issue_type: (
                -max(
                    original_seconds.get(issue_type, 0),
                    spent_before_sprint_seconds.get(issue_type, 0)
                    + sprint_seconds.get(issue_type, 0)
                    + remaining_seconds.get(issue_type, 0),
                ),
                issue_type,
            ),
        )
    )
    return EstimateProjectionView(
        issue_types=issue_types,
        original_seconds=original_seconds,
        spent_before_sprint_seconds=spent_before_sprint_seconds,
        sprint_seconds=sprint_seconds,
        remaining_seconds=remaining_seconds,
    )


def _issue_type_time_kpi(
    items: tuple[IssueReviewItem, ...],
    *,
    total_label: str,
    empty_message: str,
    seconds_getter: Callable[[IssueReviewItem], int | None],
) -> IssueTypeTimeKpiView:
    total_seconds = 0
    seconds_by_issue_type: dict[str, int] = {}
    for item in items:
        seconds = _seconds_value(seconds_getter(item))
        total_seconds += seconds
        issue_type = item.issue.issue_type or t("report.no_issue_type")
        seconds_by_issue_type[issue_type] = (
            seconds_by_issue_type.get(issue_type, 0) + seconds
        )

    issue_type_times = tuple(
        IssueTypeTimeView(
            issue_type=issue_type,
            seconds=seconds,
            duration=format_duration(seconds),
        )
        for issue_type, seconds in sorted(
            seconds_by_issue_type.items(),
            key=lambda value: (-value[1], value[0]),
        )
        if seconds > 0
    )
    return IssueTypeTimeKpiView(
        chart_id=f"{_slugify(total_label)}-chart",
        total_time=format_duration(total_seconds),
        total_label=total_label,
        empty_message=empty_message,
        issue_type_times=issue_type_times,
    )


def _tempo_seconds_by_issue_type(items: tuple[IssueReviewItem, ...]) -> dict[str, int]:
    seconds_by_issue_type: dict[str, int] = {}
    for item in items:
        issue_type = item.issue.issue_type or t("report.no_issue_type")
        seconds_by_issue_type[issue_type] = (
            seconds_by_issue_type.get(issue_type, 0) + item.tempo_seconds
        )
    return seconds_by_issue_type


def _seconds_value(seconds: int | None) -> int:
    return 0 if seconds is None else seconds


def _review_items(review: SprintReview) -> tuple[IssueReviewItem, ...]:
    return review.completed + review.unfinished_with_time + review.not_started


def _percentage(count: int, total: int) -> int:
    if total == 0:
        return 0
    return round(count / total * 100)


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
