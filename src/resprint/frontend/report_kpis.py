from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from resprint.exporters.common import format_duration
from resprint.frontend.utils.charts import render_chart
from resprint.frontend.utils.templates import render_template
from resprint.models import IssueReviewItem, SprintReview


@dataclass(frozen=True)
class KpiBlock:
    title: str
    html: str
    wide: bool = False


@dataclass(frozen=True)
class KpiGroup:
    title: str
    blocks: tuple[KpiBlock, ...]
    summary_html: str = ""
    expanded: bool = False


@dataclass(frozen=True)
class TicketProgressSegment:
    label: str
    count: int
    percentage: int
    variant: str


@dataclass(frozen=True)
class IssueTypeTime:
    issue_type: str
    seconds: int
    duration: str


@dataclass(frozen=True)
class TimeRatioSegment:
    label: str
    seconds: int
    duration: str
    percentage: int
    variant: str


def render_kpi_section(review: SprintReview) -> str:
    return render_template("report_kpis.html", groups=_kpi_blocks(review))


def _kpi_blocks(review: SprintReview) -> tuple[KpiGroup, ...]:
    return (
        KpiGroup(
            title="Vue sprint",
            expanded=True,
            blocks=(
                KpiBlock(
                    title="Repartition des tickets",
                    html=_render_ticket_progress(review),
                ),
            ),
        ),
        KpiGroup(
            title="Temps consomme",
            summary_html=_render_consumed_time_ratio(review),
            blocks=(
                KpiBlock(
                    title="Sprint vs hors sprint par type",
                    html=_render_consumed_time_comparison(review),
                    wide=True,
                ),
                KpiBlock(
                    title="Temps sprint consomme",
                    html=_render_sprint_time_kpi(review),
                ),
                KpiBlock(
                    title="Temps hors sprint consomme",
                    html=_render_issue_type_time_kpi(
                        review.out_of_sprint,
                        total_label="Temps total consomme hors sprint",
                        empty_message="Aucun temps hors sprint.",
                        seconds_getter=lambda item: item.tempo_seconds,
                    ),
                ),
            ),
        ),
        KpiGroup(
            title="Estimations",
            blocks=(
                KpiBlock(
                    title="Projection vs estimation originale par type",
                    html=_render_estimate_projection_comparison(review),
                    wide=True,
                ),
                KpiBlock(
                    title="Temps original estime",
                    html=_render_issue_type_time_kpi(
                        _review_items(review),
                        total_label="Temps original estime total",
                        empty_message="Aucune estimation originale.",
                        seconds_getter=lambda item: (
                            item.issue.original_estimate_seconds
                        ),
                    ),
                ),
                KpiBlock(
                    title="Temps restant estime",
                    html=_render_issue_type_time_kpi(
                        _review_items(review),
                        total_label="Temps restant estime total",
                        empty_message="Aucune estimation restante.",
                        seconds_getter=lambda item: (
                            item.issue.remaining_estimate_seconds
                        ),
                    ),
                ),
            ),
        ),
    )


def _render_consumed_time_ratio(review: SprintReview) -> str:
    sprint_seconds = sum(item.tempo_seconds for item in _review_items(review))
    out_of_sprint_seconds = sum(item.tempo_seconds for item in review.out_of_sprint)
    total_seconds = sprint_seconds + out_of_sprint_seconds
    segments = (
        TimeRatioSegment(
            label="Sprint",
            seconds=sprint_seconds,
            duration=format_duration(sprint_seconds),
            percentage=_percentage(sprint_seconds, total_seconds),
            variant="sprint",
        ),
        TimeRatioSegment(
            label="Hors sprint",
            seconds=out_of_sprint_seconds,
            duration=format_duration(out_of_sprint_seconds),
            percentage=_percentage(out_of_sprint_seconds, total_seconds),
            variant="out-of-sprint",
        ),
    )
    aria_label = ", ".join(
        f"{segment.label}: {segment.duration}, {segment.percentage}%"
        for segment in segments
    )
    chart_html = render_chart(
        "consumed-time-ratio-chart",
        _time_ratio_chart_config(segments),
        label=aria_label,
        class_name="time-ratio-chart",
    )
    return render_template(
        "report_time_ratio.html",
        chart_html=chart_html,
        segments=segments,
        total_time=format_duration(total_seconds),
        aria_label=aria_label,
    )


def _time_ratio_chart_config(
    segments: tuple[TimeRatioSegment, ...],
) -> dict[str, object]:
    return {
        "type": "bar",
        "data": {
            "labels": ["Temps"],
            "datasets": [
                {
                    "label": segment.label,
                    "data": [segment.seconds / 3600],
                    "backgroundColor": _chart_color(segment.variant),
                    "borderWidth": 0,
                }
                for segment in segments
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "x": {"display": False, "stacked": True, "beginAtZero": True},
                "y": {"display": False, "stacked": True},
            },
        },
    }


def _render_ticket_progress(review: SprintReview) -> str:
    counts = (
        ("Termines", len(review.completed), "completed"),
        ("Commences", len(review.unfinished_with_time), "started"),
        ("Non commences", len(review.not_started), "not-started"),
    )
    total = sum(count for _, count, _ in counts)
    segments = tuple(
        TicketProgressSegment(
            label=label,
            count=count,
            percentage=_percentage(count, total),
            variant=variant,
        )
        for label, count, variant in counts
    )
    aria_label = ", ".join(
        f"{segment.label}: {segment.count} tickets, {segment.percentage}%"
        for segment in segments
    )
    chart_html = render_chart(
        "ticket-distribution-chart",
        _ticket_progress_chart_config(segments),
        label=aria_label,
        class_name="ticket-progress-chart",
    )
    return render_template(
        "report_ticket_progress.html",
        chart_html=chart_html,
        segments=segments,
        total=total,
        aria_label=aria_label,
    )


def _ticket_progress_chart_config(
    segments: tuple[TicketProgressSegment, ...],
) -> dict[str, object]:
    return {
        "type": "bar",
        "data": {
            "labels": ["Tickets"],
            "datasets": [
                {
                    "label": segment.label,
                    "data": [segment.count],
                    "backgroundColor": _chart_color(segment.variant),
                    "borderWidth": 0,
                }
                for segment in segments
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "x": {"display": False, "stacked": True, "beginAtZero": True},
                "y": {"display": False, "stacked": True},
            },
        },
    }


def _render_sprint_time_kpi(review: SprintReview) -> str:
    return _render_issue_type_time_kpi(
        _review_items(review),
        total_label="Temps total consomme durant le sprint",
        empty_message="Aucun temps consomme.",
        seconds_getter=lambda item: item.tempo_seconds,
    )


def _render_consumed_time_comparison(review: SprintReview) -> str:
    sprint_seconds = _seconds_by_issue_type(_review_items(review))
    out_of_sprint_seconds = _seconds_by_issue_type(review.out_of_sprint)
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
    if not issue_types:
        return '<div class="muted">Aucun temps consomme.</div>'

    return _chart_frame(
        render_chart(
            "consumed-time-by-issue-type-chart",
            _consumed_time_comparison_chart_config(
                issue_types,
                sprint_seconds,
                out_of_sprint_seconds,
            ),
            label="Temps consomme sprint et hors sprint par type de ticket",
            class_name="consumed-time-comparison-chart",
        ),
        "kpi-chart-frame consumed-time-comparison-frame",
    )


def _consumed_time_comparison_chart_config(
    issue_types: tuple[str, ...],
    sprint_seconds: dict[str, int],
    out_of_sprint_seconds: dict[str, int],
) -> dict[str, object]:
    return {
        "type": "bar",
        "data": {
            "labels": list(issue_types),
            "datasets": [
                {
                    "label": "Sprint",
                    "data": [
                        round(sprint_seconds.get(issue_type, 0) / 3600, 2)
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("sprint"),
                    "borderWidth": 0,
                    "stack": "consumed",
                },
                {
                    "label": "Hors sprint",
                    "data": [
                        round(out_of_sprint_seconds.get(issue_type, 0) / 3600, 2)
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("out-of-sprint"),
                    "borderWidth": 0,
                    "stack": "consumed",
                },
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"position": "bottom"}},
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "stacked": True,
                    "ticks": {"precision": 0},
                },
                "y": {"grid": {"display": False}, "stacked": True},
            },
        },
    }


def _seconds_by_issue_type(items: tuple[IssueReviewItem, ...]) -> dict[str, int]:
    seconds_by_issue_type: dict[str, int] = {}
    for item in items:
        issue_type = item.issue.issue_type or "Sans type"
        seconds_by_issue_type[issue_type] = (
            seconds_by_issue_type.get(issue_type, 0) + item.tempo_seconds
        )
    return seconds_by_issue_type


def _render_estimate_projection_comparison(review: SprintReview) -> str:
    original_seconds: dict[str, int] = {}
    spent_before_sprint_seconds: dict[str, int] = {}
    sprint_seconds: dict[str, int] = {}
    remaining_seconds: dict[str, int] = {}
    for item in _review_items(review):
        issue_type = item.issue.issue_type or "Sans type"
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
    if not any(
        original_seconds.get(issue_type, 0)
        or spent_before_sprint_seconds.get(issue_type, 0)
        or sprint_seconds.get(issue_type, 0)
        or remaining_seconds.get(issue_type, 0)
        for issue_type in issue_types
    ):
        return '<div class="muted">Aucune estimation exploitable.</div>'

    return _chart_frame(
        render_chart(
            "estimate-projection-by-issue-type-chart",
            _estimate_projection_chart_config(
                issue_types,
                original_seconds,
                spent_before_sprint_seconds,
                sprint_seconds,
                remaining_seconds,
            ),
            label=(
                "Progression temps consomme et restant "
                "comparee a l'estimation originale"
            ),
            class_name="estimate-projection-chart",
        ),
        "kpi-chart-frame estimate-projection-frame",
    )


def _estimate_projection_chart_config(
    issue_types: tuple[str, ...],
    original_seconds: dict[str, int],
    spent_before_sprint_seconds: dict[str, int],
    sprint_seconds: dict[str, int],
    remaining_seconds: dict[str, int],
) -> dict[str, object]:
    return {
        "type": "bar",
        "data": {
            "labels": list(issue_types),
            "datasets": [
                {
                    "label": "Original",
                    "data": [
                        round(original_seconds.get(issue_type, 0) / 3600, 2)
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("original"),
                    "borderWidth": 0,
                    "stack": "original",
                },
                {
                    "label": "Deja consomme",
                    "data": [
                        round(
                            spent_before_sprint_seconds.get(issue_type, 0) / 3600,
                            2,
                        )
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("spent-before"),
                    "borderWidth": 0,
                    "stack": "projection",
                },
                {
                    "label": "Sprint",
                    "data": [
                        round(sprint_seconds.get(issue_type, 0) / 3600, 2)
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("sprint"),
                    "borderWidth": 0,
                    "stack": "projection",
                },
                {
                    "label": "Restant estime",
                    "data": [
                        round(remaining_seconds.get(issue_type, 0) / 3600, 2)
                        for issue_type in issue_types
                    ],
                    "backgroundColor": _chart_color("remaining"),
                    "borderWidth": 0,
                    "stack": "projection",
                },
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"position": "bottom"}},
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "ticks": {"precision": 0},
                },
                "y": {"grid": {"display": False}},
            },
        },
    }


def _chart_color(variant: str) -> str:
    return {
        "completed": "#1f7a4d",
        "started": "#0969da",
        "not-started": "#64748b",
        "sprint": "#0969da",
        "out-of-sprint": "#c2410c",
        "original": "#94a3b8",
        "spent-before": "#64748b",
        "total": "#0969da",
        "remaining": "#d97706",
    }.get(variant, "#64748b")


def _chart_frame(chart_html: str, class_name: str) -> str:
    return f'<div class="{class_name}">{chart_html}</div>'


def _chart_palette(index: int) -> str:
    return (
        "#0969da",
        "#1f7a4d",
        "#c2410c",
        "#8250df",
        "#bf3989",
        "#64748b",
    )[index % 6]


def _render_issue_type_time_kpi(
    items: tuple[IssueReviewItem, ...],
    *,
    total_label: str,
    empty_message: str,
    seconds_getter: Callable[[IssueReviewItem], int | None],
) -> str:
    total_seconds = 0
    seconds_by_issue_type: dict[str, int] = {}
    for item in items:
        seconds = _seconds_value(seconds_getter(item))
        total_seconds += seconds
        issue_type = item.issue.issue_type or "Sans type"
        seconds_by_issue_type[issue_type] = (
            seconds_by_issue_type.get(issue_type, 0) + seconds
        )

    issue_type_times = tuple(
        IssueTypeTime(
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
    chart_html = ""
    if issue_type_times:
        chart_html = render_chart(
            f"{_slugify(total_label)}-chart",
            _issue_type_time_chart_config(issue_type_times),
            label=total_label,
            class_name="issue-type-time-chart",
        )
    return render_template(
        "report_sprint_time.html",
        total_time=format_duration(total_seconds),
        total_label=total_label,
        issue_type_times=issue_type_times,
        chart_html=chart_html,
        empty_message=empty_message,
    )


def _issue_type_time_chart_config(
    issue_type_times: tuple[IssueTypeTime, ...],
) -> dict[str, object]:
    return {
        "type": "bar",
        "data": {
            "labels": [item.issue_type for item in issue_type_times],
            "datasets": [
                {
                    "label": "Heures",
                    "data": [
                        round(item.seconds / 3600, 2) for item in issue_type_times
                    ],
                    "backgroundColor": [
                        _chart_palette(index)
                        for index, _item in enumerate(issue_type_times)
                    ],
                    "borderWidth": 0,
                }
            ],
        },
        "options": {
            "indexAxis": "y",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "ticks": {"precision": 0},
                },
                "y": {"grid": {"display": False}},
            },
        },
    }


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
