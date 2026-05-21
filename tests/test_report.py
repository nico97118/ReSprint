from datetime import UTC, date, datetime

from sprint_review.models import (
    Issue,
    IssueReviewItem,
    JiraComment,
    Sprint,
    SprintReview,
    UserTimeSpent,
)
from sprint_review.report import render_html, render_markdown


def test_render_markdown_contains_requested_issue_columns() -> None:
    issue = Issue(
        id="10001",
        key="ABC-1",
        summary="Finaliser le paiement",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
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
    )

    report = render_markdown(
        review,
        Sprint(1, "Sprint 1", date(2026, 5, 1), date(2026, 5, 15)),
        "https://jira.example.test",
    )

    assert "## Tickets termines" in report
    assert "## Tickets non termines avec du temps consomme" in report
    assert "## Tickets non commences" in report
    assert "Issue key | Titre | Epopee | Priorite | FixVersion" in report
    assert "Temps consomme par utilisateur" in report
    assert "Temps total consomme" in report
    assert "Temps original depasse" in report
    assert "[ABC-1](https://jira.example.test/browse/ABC-1)" in report
    assert "Finaliser le paiement" in report
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


def test_render_html_contains_static_sections_and_escaped_issue_data() -> None:
    issue = Issue(
        id="10001",
        key="ABC-1",
        summary="Finaliser le paiement",
        status="In Progress",
        status_category="indeterminate",
        assignee="Alice",
        epic="Epic <unsafe>",
        priority="High",
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
    review = SprintReview(
        completed=(item,),
        unfinished_with_time=(),
        not_started=(),
    )

    html = render_html(
        review,
        Sprint(1, "Sprint 1", date(2026, 5, 1), date(2026, 5, 15)),
        "https://jira.example.test",
    )

    assert "<!doctype html>" in html
    assert "Tickets termines" in html
    assert "Tickets non termines avec du temps consomme" in html
    assert "ABC-1" in html
    assert "Finaliser le paiement" in html
    assert "data-report-table" in html
    assert "data-table-search" in html
    assert "data-theme-toggle" in html
    assert "theme-switch" in html
    assert 'role="switch"' in html
    assert 'setAttribute("data-theme", theme)' in html
    assert "sprint-review-theme" in html
    assert 'data-sort-column="0"' in html
    assert "mdi-sort" in html
    assert "mdi-magnify" in html
    assert 'data-sort-value="7200"' in html
    assert "Non termines avec temps" in html
    assert "Epic &lt;unsafe&gt;" in html
    assert "Bob: 2.00 h" in html
    assert "badge-danger" in html
