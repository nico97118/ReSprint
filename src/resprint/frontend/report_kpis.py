from __future__ import annotations

from dataclasses import dataclass

from resprint.frontend.utils.charts import render_chart
from resprint.frontend.utils.templates import render_template
from resprint.frontend.view_models.report_kpis import (
    ConsumedTimeComparisonView,
    EstimateProjectionView,
    IssueTypeTimeKpiView,
    IssueTypeTimeView,
    ReportKpiView,
    TicketProgressSegmentView,
    TicketProgressView,
    TimeRatioSegmentView,
    TimeRatioView,
    build_report_kpis,
)
from resprint.models import SprintReview


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


def render_kpi_section(review: SprintReview) -> str:
    return render_template(
        "components/report/kpis.html",
        groups=_kpi_blocks(build_report_kpis(review)),
    )


def _kpi_blocks(kpis: ReportKpiView) -> tuple[KpiGroup, ...]:
    return (
        KpiGroup(
            title="Vue sprint",
            expanded=True,
            blocks=(
                KpiBlock(
                    title="Repartition des tickets",
                    html=_render_ticket_progress(kpis.ticket_progress),
                ),
            ),
        ),
        KpiGroup(
            title="Temps consomme",
            summary_html=_render_consumed_time_ratio(kpis.consumed_time_ratio),
            blocks=(
                KpiBlock(
                    title="Sprint vs hors sprint par type",
                    html=_render_consumed_time_comparison(
                        kpis.consumed_time_comparison
                    ),
                    wide=True,
                ),
                KpiBlock(
                    title="Temps sprint consomme",
                    html=_render_issue_type_time_kpi(kpis.sprint_time),
                ),
                KpiBlock(
                    title="Temps hors sprint consomme",
                    html=_render_issue_type_time_kpi(kpis.out_of_sprint_time),
                ),
            ),
        ),
        KpiGroup(
            title="Estimations",
            blocks=(
                KpiBlock(
                    title="Projection vs estimation originale par type",
                    html=_render_estimate_projection_comparison(
                        kpis.estimate_projection
                    ),
                    wide=True,
                ),
                KpiBlock(
                    title="Temps original estime",
                    html=_render_issue_type_time_kpi(kpis.original_estimate_time),
                ),
                KpiBlock(
                    title="Temps restant estime",
                    html=_render_issue_type_time_kpi(kpis.remaining_estimate_time),
                ),
            ),
        ),
    )


def _render_consumed_time_ratio(kpi: TimeRatioView) -> str:
    chart_html = render_chart(
        "consumed-time-ratio-chart",
        _time_ratio_chart_config(kpi.segments),
        label=kpi.aria_label,
        class_name="time-ratio-chart",
    )
    return render_template(
        "components/report/time_ratio.html",
        chart_html=chart_html,
        segments=kpi.segments,
        total_time=kpi.total_time,
        aria_label=kpi.aria_label,
    )


def _time_ratio_chart_config(
    segments: tuple[TimeRatioSegmentView, ...],
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


def _render_ticket_progress(kpi: TicketProgressView) -> str:
    chart_html = render_chart(
        "ticket-distribution-chart",
        _ticket_progress_chart_config(kpi.segments),
        label=kpi.aria_label,
        class_name="ticket-progress-chart",
    )
    return render_template(
        "components/report/ticket_progress.html",
        chart_html=chart_html,
        segments=kpi.segments,
        total=kpi.total,
        aria_label=kpi.aria_label,
    )


def _ticket_progress_chart_config(
    segments: tuple[TicketProgressSegmentView, ...],
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


def _render_consumed_time_comparison(kpi: ConsumedTimeComparisonView) -> str:
    if kpi.is_empty:
        return '<div class="muted">Aucun temps consomme.</div>'

    return _chart_frame(
        render_chart(
            "consumed-time-by-issue-type-chart",
            _consumed_time_comparison_chart_config(
                kpi.issue_types,
                kpi.sprint_seconds,
                kpi.out_of_sprint_seconds,
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


def _render_estimate_projection_comparison(kpi: EstimateProjectionView) -> str:
    if kpi.is_empty:
        return '<div class="muted">Aucune estimation exploitable.</div>'

    return _chart_frame(
        render_chart(
            "estimate-projection-by-issue-type-chart",
            _estimate_projection_chart_config(
                kpi.issue_types,
                kpi.original_seconds,
                kpi.spent_before_sprint_seconds,
                kpi.sprint_seconds,
                kpi.remaining_seconds,
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


def _render_issue_type_time_kpi(kpi: IssueTypeTimeKpiView) -> str:
    chart_html = ""
    if kpi.issue_type_times:
        chart_html = render_chart(
            kpi.chart_id,
            _issue_type_time_chart_config(kpi.issue_type_times),
            label=kpi.total_label,
            class_name="issue-type-time-chart",
        )
    return render_template(
        "components/report/sprint_time.html",
        total_time=kpi.total_time,
        total_label=kpi.total_label,
        issue_type_times=kpi.issue_type_times,
        chart_html=chart_html,
        empty_message=kpi.empty_message,
    )


def _issue_type_time_chart_config(
    issue_type_times: tuple[IssueTypeTimeView, ...],
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
