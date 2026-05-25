from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

from resprint.exporters.common import format_bool, format_duration, format_fix_versions
from resprint.exporters.json import render_json
from resprint.exporters.markdown import render_markdown
from resprint.frontend.utils.charts import render_chart
from resprint.frontend.utils.page import render_page, static_text, vendor_script
from resprint.frontend.utils.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableFilter,
    TableRow,
    render_table_section,
    table_css,
    table_script,
)
from resprint.frontend.utils.templates import render_template
from resprint.logging import get_logger
from resprint.models import (
    Issue,
    IssueReviewItem,
    JiraIssueChange,
    Sprint,
    SprintReview,
)

logger = get_logger(__name__)

REPORT_TABLE_COLUMNS = [
    TableColumn("key", "Issue key"),
    TableColumn("summary", "Titre"),
    TableColumn("issue_type", "Type"),
    TableColumn("status", "Statut"),
    TableColumn("parent", "Parent"),
    TableColumn(
        "original_estimate",
        "Temps original estime",
        short_label="Original",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "remaining_estimate",
        "Temps restant estime",
        short_label="Restant",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "total_time",
        "Temps total consomme",
        short_label="Total",
        numeric=True,
        sort_type="number",
    ),
    TableColumn(
        "sprint_time",
        "Temps sprint",
        short_label="Sprint",
        numeric=True,
        sort_type="number",
    ),
]


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


@dataclass(frozen=True)
class SummaryTab:
    label: str
    panel_id: str
    count: int
    variant: str
    selected: bool = False


def render_html(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
    jql: str | None = None,
) -> str:
    logger.info("Rendering HTML report for sprint %s", sprint.name)
    title = sprint.name
    sections = [
        ("Tickets termines", list(review.completed)),
        (
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
        ),
        ("Tickets non commences", list(review.not_started)),
    ]
    if review.out_of_sprint:
        sections.append(("Hors sprint", list(review.out_of_sprint)))
    logger.debug(
        "HTML report sections: %s",
        [(section_title, len(items)) for section_title, items in sections],
    )
    sections_html = "\n".join(
        _render_html_section(title, items, jira_base_url) for title, items in sections
    )
    summary_html = _render_html_summary(review)
    kpi_section_html = _render_kpi_section(_kpi_blocks(review))
    export_json = _script_json(render_json(review, sprint, jql))
    export_markdown = _script_text(render_markdown(review, sprint, jira_base_url))
    content = render_template(
        "report.html",
        sprint=sprint,
        jql=jql,
        jira_jql_url=_jira_jql_url(jira_base_url, jql),
        export_json=export_json,
        export_markdown=export_markdown,
        kpi_section_html=kpi_section_html,
        summary_html=summary_html,
        sections_html=sections_html,
    )
    report_css = static_text("report.css") + table_css()
    report_script = static_text("charts.js") + static_text("report.js") + table_script()

    return render_page(
        title,
        content,
        header_actions=_render_export_actions(sprint),
        extra_css=report_css,
        vendor_scripts=vendor_script("chartjs/chart.umd.js"),
        scripts=report_script,
        max_width="1440px",
    )


def _render_export_actions(sprint: Sprint) -> str:
    basename = _html_attr(f"resprint-{_filename_slug(sprint.name)}")
    return f"""<details
  class="report-export"
  data-report-export
  data-export-basename="{basename}"
>
  <summary class="report-export-trigger">
    <span class="button-content">
      <span class="mdi mdi-download" aria-hidden="true"></span>
      <span>Exporter</span>
      <span class="mdi mdi-chevron-down" aria-hidden="true"></span>
    </span>
  </summary>
  <div class="report-export-menu">
    <button type="button" data-export-option="json">JSON</button>
    <button type="button" data-export-option="markdown">Markdown</button>
  </div>
</details>"""


def _filename_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "rapport"


def _jira_jql_url(jira_base_url: str, jql: str | None) -> str | None:
    if not jql:
        return None
    return f"{jira_base_url}/issues/?jql={quote(jql)}"


def _script_json(value: str) -> str:
    return _script_text(value)


def _script_text(value: str) -> str:
    return (
        value.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _render_kpi_section(groups: tuple[KpiGroup, ...]) -> str:
    if not groups:
        return ""
    return render_template("report_kpis.html", groups=groups)


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
            "plugins": {
                "legend": {"display": False},
            },
            "scales": {
                "x": {
                    "display": False,
                    "stacked": True,
                    "beginAtZero": True,
                },
                "y": {
                    "display": False,
                    "stacked": True,
                },
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
            "plugins": {
                "legend": {"display": False},
            },
            "scales": {
                "x": {
                    "display": False,
                    "stacked": True,
                    "beginAtZero": True,
                },
                "y": {
                    "display": False,
                    "stacked": True,
                },
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
            "plugins": {
                "legend": {"position": "bottom"},
            },
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "stacked": True,
                    "ticks": {"precision": 0},
                },
                "y": {
                    "grid": {"display": False},
                    "stacked": True,
                },
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
            "plugins": {
                "legend": {"position": "bottom"},
            },
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "ticks": {"precision": 0},
                },
                "y": {
                    "grid": {"display": False},
                },
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
            "plugins": {
                "legend": {"display": False},
            },
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"display": False},
                    "ticks": {"precision": 0},
                },
                "y": {
                    "grid": {"display": False},
                },
            },
        },
    }


def _seconds_value(seconds: int | None) -> int:
    return 0 if seconds is None else seconds


def _review_items(review: SprintReview) -> tuple[IssueReviewItem, ...]:
    return review.completed + review.unfinished_with_time + review.not_started


def _render_html_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> str:
    section_id = _slugify(title)
    if not items:
        logger.debug("Rendering empty HTML report section '%s'", title)
        return render_template(
            "report_empty_section.html",
            section_id=section_id,
            title=title,
        )

    logger.debug("Rendering HTML report section '%s' with %s items", title, len(items))
    rows = [_html_row(item, jira_base_url) for item in items]
    return render_table_section(
        section_id=section_id,
        title=title,
        columns=REPORT_TABLE_COLUMNS,
        rows=rows,
        searchable=True,
        sortable=True,
        default_sort=DefaultSort("key"),
        filters=[
            TableFilter("issue_type", "Type", "Tous les types"),
            TableFilter("status", "Statut", "Tous les statuts"),
            TableFilter("parent", "Parent", "Tous les parents"),
        ],
        empty_message="Aucun ticket ne correspond a la recherche.",
        section_attributes={
            "data-report-table": "",
            "data-report-panel": "",
        },
    )


def _html_row(item: IssueReviewItem, jira_base_url: str) -> TableRow:
    issue = item.issue
    issue_url = f"{jira_base_url}/browse/{issue.key}"
    search_text = " ".join(
        (
            issue.key,
            issue.summary,
            issue.issue_type or "",
            issue.status,
            issue.status_category,
            issue.parent or "",
            issue.priority or "",
            format_fix_versions(issue.fix_versions),
            format_bool(item.is_over_original_estimate),
            _plain_time_spent_by_user(item),
            _plain_comments(item),
            _plain_changes(item),
        )
    )
    return TableRow(
        cells={
            "key": TableCell(
                f'<a href="{_html_attr(issue_url)}">{_html(issue.key)}</a>'
            ),
            "summary": TableCell(_html(issue.summary or "-")),
            "issue_type": TableCell(_html(issue.issue_type or "-")),
            "status": TableCell(_format_html_status(issue)),
            "parent": TableCell(_html(issue.parent or "-")),
            "original_estimate": _duration_cell(issue.original_estimate_seconds),
            "remaining_estimate": _duration_cell(issue.remaining_estimate_seconds),
            "total_time": _duration_cell(item.total_seconds),
            "sprint_time": _duration_cell(item.tempo_seconds),
        },
        search_text=search_text,
        style=_row_style(item),
        details_html=_render_issue_detail(item),
    )


def _render_issue_detail(item: IssueReviewItem) -> str:
    issue = item.issue
    details = (
        ("Progression temps", _render_time_progress(item), "issue-detail-item-wide"),
        ("Priorite", _html(issue.priority or "-")),
        ("FixVersion", _html(format_fix_versions(issue.fix_versions))),
        ("Temps sprint par utilisateur", _format_html_time_spent_by_user(item)),
        ("Commentaires sprint", _format_html_comments(item)),
        ("Activite sprint", _format_html_changes(item)),
    )
    rendered_details = "\n".join(
        _render_issue_detail_item(label, value, css_class[0] if css_class else "")
        for detail in details
        for label, value, *css_class in (detail,)
    )
    return f'<dl class="issue-detail-grid">{rendered_details}</dl>'


def _render_issue_detail_item(label: str, value: str, css_class: str = "") -> str:
    classes = f"issue-detail-item {css_class}".strip()
    return f"""<div class="{classes}">
  <dt>{_html(label)}</dt>
  <dd>{value}</dd>
</div>"""


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

    return f"""<div class="time-progress">
  <div class="time-progress-row">
    <div class="time-progress-label">Original estime</div>
    <div class="time-progress-track" aria-label="Temps original estime">
      <div
        class="time-progress-segment time-progress-segment-original"
        style="width: {original_width:.4f}%"
        title="Original estime: {_html_attr(original_duration)}"
      ></div>
    </div>
    <div class="time-progress-value">{_html(original_duration)}</div>
  </div>
  <div class="time-progress-row">
    <div class="time-progress-label">Projection actuelle</div>
    <div class="time-progress-track" aria-label="Projection actuelle">
      <div
        class="time-progress-segment time-progress-segment-spent-before"
        style="width: {spent_before_width:.4f}%"
        title="Deja consomme: {_html_attr(spent_before_duration)}"
      ></div>
      <div
        class="time-progress-segment time-progress-segment-spent-sprint"
        style="width: {sprint_width:.4f}%"
        title="Consomme durant le sprint: {_html_attr(sprint_duration)}"
      ></div>
      <div
        class="time-progress-segment time-progress-segment-remaining"
        style="width: {remaining_width:.4f}%"
        title="Estimation restante: {_html_attr(remaining_duration)}"
      ></div>
    </div>
    <div class="time-progress-value">{_html(projection_duration)}</div>
  </div>
  <div class="time-progress-legend">
    {legend_html}
  </div>
</div>"""


def _time_progress_legend_item(variant: str, label: str) -> str:
    return (
        f'<span><span class="time-progress-dot time-progress-dot-{variant}">'
        f"</span>{_html(label)}</span>"
    )


def _width_percent(seconds: int, scale_seconds: int) -> float:
    if seconds <= 0:
        return 0
    return seconds / scale_seconds * 100


def _format_html_status(issue: Issue) -> str:
    status = issue.status or "-"
    category = issue.status_category or "unknown"
    normalized_category = re.sub(r"[^a-z0-9_-]+", "-", category.lower()).strip("-")
    if normalized_category not in {"new", "indeterminate", "done"}:
        normalized_category = "unknown"
    return (
        f'<span class="badge badge-status-{normalized_category}">{_html(status)}</span>'
    )


def _render_html_summary(review: SprintReview) -> str:
    tabs = [
        SummaryTab(
            label="Tickets termines",
            panel_id=_slugify("Tickets termines"),
            count=len(review.completed),
            variant="completed",
            selected=True,
        ),
        SummaryTab(
            label="Non termines avec temps",
            panel_id=_slugify("Tickets non termines avec du temps consomme"),
            count=len(review.unfinished_with_time),
            variant="started",
        ),
        SummaryTab(
            label="Non commences",
            panel_id=_slugify("Tickets non commences"),
            count=len(review.not_started),
            variant="not-started",
        ),
    ]
    if review.out_of_sprint:
        tabs.append(
            SummaryTab(
                label="Hors sprint",
                panel_id=_slugify("Hors sprint"),
                count=len(review.out_of_sprint),
                variant="out-of-sprint",
            )
        )
    return render_template("report_summary.html", tabs=tabs)


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _sort_seconds(seconds: int | None) -> int:
    return -1 if seconds is None else seconds


def _duration_cell(seconds: int | None) -> TableCell:
    return TableCell(_html(format_duration(seconds)), sort_value=_sort_seconds(seconds))


def _percentage(count: int, total: int) -> int:
    if total == 0:
        return 0
    return round(count / total * 100)


def _row_style(item: IssueReviewItem) -> str | None:
    if (
        item.issue.remaining_estimate_seconds in (None, 0)
        and item.issue.status_category != "done"
    ):
        return "error"
    if item.is_over_original_estimate:
        return "warning"
    return None


def _format_html_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{_html(user_time.user)}: {_html(format_duration(user_time.seconds))}"
        for user_time in item.time_spent_by_user
    )
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _format_html_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return '<span class="muted">-</span>'

    lines = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        lines.append(f"{_html(created)} - {_html(author)}: {_html(body)}")
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _format_html_changes(item: IssueReviewItem) -> str:
    if not item.changes:
        return '<span class="muted">-</span>'

    rendered_changes = [_render_html_change(change) for change in item.changes]
    return f'<div class="issue-changelog">{"".join(rendered_changes)}</div>'


def _render_html_change(change: JiraIssueChange) -> str:
    author = change.author or "Auteur inconnu"
    created = change.created_at.strftime("%Y-%m-%d %H:%M")
    field = change.field or "champ inconnu"
    from_value = change.from_value or "-"
    to_value = change.to_value or "-"
    return f"""<div class="issue-change">
  <div class="issue-change-meta">
    <span>{_html(created)}</span>
    <span>{_html(author)}</span>
  </div>
  <div class="issue-change-body">
    <span class="issue-change-field">{_html(field)}</span>
    <span class="issue-change-value">{_html(from_value)}</span>
    <span class="mdi mdi-arrow-right-thin issue-change-arrow" aria-hidden="true"></span>
    <span class="issue-change-value issue-change-value-new">{_html(to_value)}</span>
  </div>
</div>"""


def _plain_time_spent_by_user(item: IssueReviewItem) -> str:
    return " ".join(
        f"{user_time.user}: {format_duration(user_time.seconds)}"
        for user_time in item.time_spent_by_user
    )


def _plain_comments(item: IssueReviewItem) -> str:
    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(f"{created} - {author}: {body}")
    return " ".join(rendered_comments)


def _plain_changes(item: IssueReviewItem) -> str:
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


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
