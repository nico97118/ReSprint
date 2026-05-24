import json
from datetime import UTC, date, datetime

from resprint.exporters.json import render_json
from resprint.exporters.markdown import render_markdown
from resprint.frontend.report_page import render_html
from resprint.models import (
    Issue,
    IssueReviewItem,
    JiraComment,
    Sprint,
    SprintReview,
    UserTimeSpent,
)


def test_render_markdown_contains_requested_issue_columns() -> None:
    issue = Issue(
        id="10001",
        key="ABC-1",
        summary="Finaliser le paiement",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
        issue_type="Story",
        epic="ABC-10 - Tunnel commande",
        priority="High",
        fix_versions=("2026.05",),
        original_estimate_seconds=28800,
        remaining_estimate_seconds=7200,
    )
    item = IssueReviewItem(
        issue=issue,
        tempo_seconds=5400,
        total_seconds=9000,
        worklog_count=2,
        time_spent_by_user=(UserTimeSpent("Bob", 5400),),
        total_time_spent_by_user=(
            UserTimeSpent("Bob", 5400),
            UserTimeSpent("Alice", 3600),
        ),
        comments=(
            JiraComment(
                id="1",
                issue_id="10001",
                author="Bob",
                created_at=datetime(2026, 5, 10, 9, 30, tzinfo=UTC),
                body="Blocage recette identifie",
            ),
        ),
    )

    review = SprintReview(
        completed=(),
        unfinished_with_time=(item,),
        not_started=(),
        out_of_sprint=(
            IssueReviewItem(
                issue=Issue(
                    id="10003",
                    key="ABC-3",
                    summary="Support hors sprint",
                    status="In Progress",
                    status_category="indeterminate",
                    assignee="Alice",
                    issue_type="Task",
                ),
                tempo_seconds=3600,
                total_seconds=3600,
                worklog_count=1,
            ),
        ),
    )

    report = render_markdown(
        review,
        Sprint(1, "Sprint 1", date(2026, 5, 1), date(2026, 5, 15)),
        "https://jira.example.test",
    )

    assert "## Tickets termines" in report
    assert "## Tickets non termines avec du temps consomme" in report
    assert "## Tickets non commences" in report
    assert "## Hors sprint" in report
    assert "Issue key | Titre | Type | Epopee | Priorite | FixVersion" in report
    assert "Temps consomme par utilisateur" in report
    assert "Temps total consomme" in report
    assert "Temps original depasse" in report
    assert "[ABC-1](https://jira.example.test/browse/ABC-1)" in report
    assert "Finaliser le paiement" in report
    assert "Story" in report
    assert "ABC-10 - Tunnel commande" in report
    assert "High" in report
    assert "2026.05" in report
    assert "8.00 h" in report
    assert "2.00 h" in report
    assert "1.50 h" in report
    assert "2.50 h" in report
    assert "Non" in report
    assert "Bob: 1.50 h" in report
    assert "2026-05-10 09:30 - Bob: Blocage recette identifie" in report
    assert "[ABC-3](https://jira.example.test/browse/ABC-3)" in report
    assert "Support hors sprint" in report


def test_render_json_contains_out_of_sprint_and_jql() -> None:
    item = IssueReviewItem(
        issue=Issue(
            id="10003",
            key="ABC-3",
            summary="Support hors sprint",
            status="In Progress",
            status_category="indeterminate",
            assignee="Alice",
            issue_type="Task",
        ),
        tempo_seconds=3600,
        total_seconds=3600,
        worklog_count=1,
    )
    report = render_json(
        SprintReview(
            completed=(),
            unfinished_with_time=(),
            not_started=(),
            out_of_sprint=(item,),
        ),
        Sprint(0, "Iteration mai", date(2026, 5, 1), date(2026, 5, 15)),
        "project = ABC",
    )

    payload = json.loads(report)

    assert payload["jql"] == "project = ABC"
    assert payload["out_of_sprint"][0]["key"] == "ABC-3"


def test_render_html_contains_static_sections_and_escaped_issue_data() -> None:
    issue = Issue(
        id="10001",
        key="ABC-1",
        summary="Finaliser le paiement",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
        issue_type="Story",
        epic="Epic <unsafe>",
        priority="High",
        fix_versions=("2026.05",),
        original_estimate_seconds=3600,
        remaining_estimate_seconds=0,
    )
    item = IssueReviewItem(
        issue=issue,
        tempo_seconds=7200,
        total_seconds=7200,
        worklog_count=1,
        time_spent_by_user=(UserTimeSpent("Bob", 7200),),
    )
    warning_issue = Issue(
        id="10002",
        key="ABC-2",
        summary="Verifier le stock",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
        issue_type="Bug",
        priority="Medium",
        original_estimate_seconds=3600,
        remaining_estimate_seconds=1800,
    )
    warning_item = IssueReviewItem(
        issue=warning_issue,
        tempo_seconds=1800,
        total_seconds=7200,
        worklog_count=1,
    )
    review = SprintReview(
        completed=(item, warning_item),
        unfinished_with_time=(),
        not_started=(),
        out_of_sprint=(
            IssueReviewItem(
                issue=Issue(
                    id="10003",
                    key="ABC-3",
                    summary="Support hors sprint",
                    status="In Progress",
                    status_category="indeterminate",
                    assignee="Alice",
                    issue_type="Task",
                ),
                tempo_seconds=3600,
                total_seconds=3600,
                worklog_count=1,
            ),
        ),
    )

    html = render_html(
        review,
        Sprint(1, "Sprint 1", date(2026, 5, 1), date(2026, 5, 15)),
        "https://jira.example.test",
    )

    assert "<!doctype html>" in html
    assert "Tickets termines" in html
    assert "Tickets non termines avec du temps consomme" in html
    assert "Hors sprint" in html
    assert "ABC-1" in html
    assert "ABC-2" in html
    assert "ABC-3" in html
    assert "Finaliser le paiement" in html
    assert "Story" in html
    assert "Bug" in html
    assert "data-report-table" in html
    assert "data-table-filter" in html
    assert "Tous les types" in html
    assert "Toutes les epopees" in html
    assert "Toutes les priorites" in html
    assert "Toutes les versions" in html
    assert "kpi-section" in html
    assert "Repartition des tickets" in html
    assert "report-sections-header" in html
    assert "Tickets" in html
    assert "report-export" in html
    assert "data-export-format" in html
    assert "mdi-download" in html
    assert "Exporter" in html
    assert 'id="report-export-json"' in html
    assert '"completed"' in html
    assert "URL.createObjectURL" in html
    assert "ticket-progress-bar" in html
    assert "Termines" in html
    assert "Commences" in html
    assert "Non commences" in html
    assert "100%" in html
    assert "Temps sprint consomme" in html
    assert "Temps total consomme durant le sprint" in html
    assert "Temps original estime" in html
    assert "Temps original estime total" in html
    assert "Temps restant estime" in html
    assert "Temps restant estime total" in html
    assert "Temps hors sprint consomme" in html
    assert "Temps total consomme hors sprint" in html
    assert '<details class="kpi-group" open>' in html
    assert '<summary class="kpi-group-summary">' in html
    assert "mdi-chevron-down" in html
    assert "Ratio sprint / hors sprint" in html
    assert "time-ratio-bar" in html
    assert "time-ratio-segment-sprint" in html
    assert "time-ratio-segment-out-of-sprint" in html
    assert "2.50 h" in html
    assert "0.50 h" in html
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert 'aria-selected="true"' in html
    assert "summary-item-completed" in html
    assert "summary-item-started" in html
    assert "summary-item-not-started" in html
    assert "summary-item-out-of-sprint" in html
    assert "data-report-panel" in html
    assert "data-target-panel" in html
    assert "data-table-search" in html
    assert "data-theme-toggle" in html
    assert "theme-switch" in html
    assert "--switch-icon" in html
    assert "min-height: 0" in html
    assert 'role="switch"' in html
    assert 'setAttribute("data-theme", theme)' in html
    assert "mdi-weather-night" in html
    assert "resprint-theme" in html
    assert 'data-sort-column="0"' in html
    assert 'data-default-sort-column="0"' in html
    assert "sort-indicator" in html
    assert "mdi-sort" not in html
    assert "mdi-arrow-up" in html
    assert "mdi-arrow-down" in html
    assert "opacity: 0.45" in html
    assert r'content: "\F005D"' in html
    assert r'content: "\\F005D"' not in html
    assert "mdi-magnify" in html
    assert 'data-sort-value="7200"' in html
    assert "Non termines avec temps" in html
    assert "Epic &lt;unsafe&gt;" in html
    assert "Bob: 2.00 h" in html
    assert "badge-danger" in html
    assert "table-row-error" in html
    assert "table-row-warning" in html
    assert '<div class="report-query">' not in html


def test_render_html_displays_period_jql_when_provided() -> None:
    html = render_html(
        SprintReview(
            completed=(),
            unfinished_with_time=(),
            not_started=(),
        ),
        Sprint(0, "Iteration mai", date(2026, 5, 1), date(2026, 5, 15)),
        "https://jira.example.test",
        "project = ABC AND fixVersion = 2026.05",
    )

    assert "report-query" in html
    assert "JQL" in html
    assert "project = ABC AND fixVersion = 2026.05" in html
