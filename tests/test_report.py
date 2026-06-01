import json
from datetime import UTC, date, datetime

from resprint.exporters.json import render_json
from resprint.exporters.markdown import render_markdown
from resprint.frontend.report.page import render_html
from resprint.models import (
    Issue,
    IssueReviewItem,
    JiraComment,
    JiraIssueChange,
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
        parent="ABC-10 - Tunnel commande",
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
        changes=(
            JiraIssueChange(
                author="Alice",
                created_at=datetime(2026, 5, 11, 10, 15, tzinfo=UTC),
                field="status",
                from_value="To Do",
                to_value="In Progress",
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

    assert "## Tickets terminés" in report
    assert "## Tickets non terminés avec du temps consommé" in report
    assert "## Tickets non commencés" in report
    assert "## Hors sprint" in report
    assert "Clé du ticket | Titre | Type | Parent | Priorité | FixVersion" in report
    assert "Temps consommé par utilisateur" in report
    assert "Temps total consommé" in report
    assert "Temps original dépassé" in report
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
    assert "Activité durant le sprint" in report
    assert "2026-05-11 10:15 - Alice: status: To Do -> In Progress" in report
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
    assert payload["out_of_sprint"][0]["changes"] == []


def test_render_html_contains_static_sections_and_escaped_issue_data() -> None:
    issue = Issue(
        id="10001",
        key="ABC-1",
        summary="Finaliser le paiement",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
        issue_type="Story",
        parent="Parent <unsafe>",
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
        comments=(
            JiraComment(
                id="1",
                issue_id="10001",
                author="Bob",
                created_at=datetime(2026, 5, 12, 14, 30, tzinfo=UTC),
                body="[Spec|https://jira.example.test/spec] *important* <script>",
            ),
        ),
        changes=(
            JiraIssueChange(
                author="Alice",
                created_at=datetime(2026, 5, 11, 10, 15, tzinfo=UTC),
                field="status",
                from_value="To Do",
                to_value="In Progress",
            ),
        ),
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
    assert "Tickets terminés" in html
    assert "Tickets non terminés avec du temps consommé" in html
    assert "Hors sprint" in html
    assert "ABC-1" in html
    assert "ABC-2" in html
    assert "ABC-3" in html
    assert "Finaliser le paiement" in html
    assert "Story" in html
    assert "Statut" in html
    assert "In Progress" in html
    assert "badge-status-indeterminate" in html
    assert "Bug" in html
    assert "data-report-table" in html
    assert "data-table-filter" in html
    assert "Tous les types" in html
    assert "Tous les statuts" in html
    assert "Tous les parents" in html
    assert "kpi-section" in html
    assert "Répartition des tickets" in html
    assert "report-sections-header" in html
    assert "Tickets" in html
    assert "report-export" in html
    assert "report-export-trigger" in html
    assert 'data-export-option="json"' in html
    assert 'data-export-option="markdown"' in html
    assert "mdi-download" in html
    assert "mdi-chevron-down" in html
    assert "Exporter" in html
    assert "Markdown" in html
    assert 'id="report-export-json"' in html
    assert 'id="report-export-markdown"' in html
    assert '"completed"' in html
    assert "# ReSprint - Sprint 1" in html
    assert "/assets/min/common.min.css" in html
    assert "/assets/min/report.min.css" in html
    assert "/assets/min/table.min.css" in html
    assert "/assets/min/theme.min.js" in html
    assert "/assets/min/table.min.js" in html
    assert "/assets/min/charts.min.js" in html
    assert "/assets/min/report.min.js" in html
    assert "ticket-distribution-chart" in html
    assert "data-chart-config" in html
    assert "Terminés" in html
    assert "Commencés" in html
    assert "Non commencés" in html
    assert "100%" in html
    assert "Temps sprint consommé" in html
    assert "Sprint vs hors sprint par type" in html
    assert "consumed-time-by-issue-type-chart" in html
    assert "Temps total consommé durant le sprint" in html
    assert "temps-total-consommé-durant-le-sprint-chart" in html
    assert "Temps original estimé" in html
    assert "Projection vs estimation originale par type" in html
    assert "estimate-projection-by-issue-type-chart" in html
    assert "Progression du temps consommé et du restant comparée" in html
    assert "Déjà consommé" in html
    assert "Temps original estimé total" in html
    assert "temps-original-estimé-total-chart" in html
    assert "Temps restant estimé" in html
    assert "Temps restant estimé total" in html
    assert "temps-restant-estimé-total-chart" in html
    assert "Temps hors sprint consommé" in html
    assert "Temps total consommé hors sprint" in html
    assert "temps-total-consommé-hors-sprint-chart" in html
    assert '<details class="kpi-group" open>' in html
    assert '<summary class="kpi-group-summary">' in html
    assert "mdi-chevron-down" in html
    assert "Ratio sprint / hors sprint" in html
    assert "consumed-time-ratio-chart" in html
    assert "time-ratio-dot-sprint" in html
    assert "time-ratio-dot-out-of-sprint" in html
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
    assert "/assets/vendor/mdi/css/materialdesignicons.min.css" in html
    assert "/assets/vendor/chartjs/chart.umd.js" in html
    assert "cdn.jsdelivr.net" not in html
    assert "app-navbar" in html
    assert "app-brand" in html
    assert "mdi-home" not in html
    assert "theme-switch" in html
    assert 'role="switch"' in html
    assert 'data-sort-column="1"' in html
    assert 'data-default-sort-column="1"' in html
    assert "sort-indicator" in html
    assert "mdi-sort" not in html
    assert "mdi-arrow-up" in html
    assert "mdi-magnify" in html
    assert 'data-sort-value="7200"' in html
    assert "row-expander-header" in html
    assert "data-row-toggle" in html
    assert "table-detail-row" in html
    assert "issue-detail-grid" in html
    assert "Progression du temps" in html
    assert "time-progress" in html
    assert "time-progress-segment-original" in html
    assert "time-progress-segment-spent-before" in html
    assert "time-progress-segment-spent-sprint" in html
    assert "time-progress-segment-remaining" in html
    assert "Projection actuelle" in html
    assert "Priorité" in html
    assert "FixVersion" in html
    assert "Temps sprint par utilisateur" in html
    assert "Commentaires du sprint" in html
    assert "issue-detail-expander" in html
    assert '<details class="issue-detail-expander" open>' in html
    assert '<details class="issue-detail-expander">' in html
    assert html.count('<span class="issue-detail-count-badge">1</span>') >= 2
    assert "Afficher le detail" not in html
    assert "issue-comments" in html
    assert "issue-comment-meta" in html
    assert "2026-05-12 14:30 - Bob" in html
    assert '<a href="https://jira.example.test/spec">Spec</a>' in html
    assert "<strong>important</strong>" in html
    assert "&lt;script&gt;" in html
    assert "Activité du sprint" in html
    assert "issue-changelog" in html
    assert "issue-change-field" in html
    assert "issue-change-value-new" in html
    assert "mdi-arrow-right-thin" in html
    assert "2026-05-11 10:15" in html
    assert "Alice" in html
    assert "status" in html
    assert "To Do" in html
    assert "In Progress" in html
    assert "Non terminés avec temps" in html
    assert "Parent &lt;unsafe&gt;" in html
    assert "Bob: 2.00 h" in html
    assert "Depassement" not in html
    assert "table-row-error" in html
    assert "table-row-warning" in html
    assert '<div class="report-query">' not in html
    # New column header (full label and short label)
    assert 'title="Responsable"' in html
    assert "Resp" in html
    # Assignee value appears in the table rows
    assert "Alice" in html


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
    assert "data-copy-jql" in html
    assert "data-jql-text" in html
    assert "mdi-content-copy" in html
    assert "mdi-open-in-new" in html
    assert (
        "https://jira.example.test/issues/?jql=project%20%3D%20ABC%20AND%20"
        "fixVersion%20%3D%202026.05"
    ) in html
