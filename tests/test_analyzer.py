from datetime import date

from resprint.analysis import (
    build_out_of_sprint_items,
    build_review_items,
    build_sprint_review,
)
from resprint.models import Issue, TempoWorklog


def test_build_review_items_keeps_unfinished_issues_with_tempo_time() -> None:
    todo = Issue("10001", "ABC-1", "A faire", "In Progress", "indeterminate", "Alice")
    done = Issue("10002", "ABC-2", "Termine", "Done", "done", "Bob")
    empty = Issue("10003", "ABC-3", "Sans temps", "To Do", "new", None)

    items = build_review_items(
        [todo, done, empty],
        {
            "10001": [
                TempoWorklog("10001", 3600, date(2026, 5, 1), "Alice"),
                TempoWorklog("10001", 1800, date(2026, 5, 2), "Bob"),
            ],
            "10002": [TempoWorklog("10002", 7200, date(2026, 5, 1), "Bob")],
        },
        done_status_categories={"done"},
        min_seconds=1,
    )

    assert [item.issue.key for item in items] == ["ABC-1"]
    assert items[0].tempo_seconds == 5400
    assert items[0].total_seconds == 5400
    assert items[0].authors == ("Alice", "Bob")
    assert [(entry.user, entry.seconds) for entry in items[0].time_spent_by_user] == [
        ("Alice", 3600),
        ("Bob", 1800),
    ]


def test_build_review_items_keeps_total_time_separate_from_sprint_time() -> None:
    issue = Issue("10001", "ABC-1", "A faire", "In Progress", "indeterminate", "Alice")

    items = build_review_items(
        [issue],
        {
            "10001": [
                TempoWorklog("10001", 1800, date(2026, 5, 1), "Alice"),
            ],
        },
        done_status_categories={"done"},
        min_seconds=1,
        total_worklogs_by_issue_id={
            "10001": [
                TempoWorklog("10001", 1800, date(2026, 5, 1), "Alice"),
                TempoWorklog("10001", 3600, date(2026, 4, 20), "Bob"),
            ],
        },
    )

    assert items[0].tempo_seconds == 1800
    assert items[0].total_seconds == 5400
    assert [
        (entry.user, entry.seconds) for entry in items[0].total_time_spent_by_user
    ] == [
        ("Bob", 3600),
        ("Alice", 1800),
    ]


def test_build_sprint_review_splits_expected_discussion_sections() -> None:
    over_estimate = Issue(
        "10001",
        "ABC-1",
        "Termine trop cher",
        "Done",
        "done",
        "Alice",
        original_estimate_seconds=3600,
    )
    completed_within_estimate = Issue(
        "10004",
        "ABC-4",
        "Termine dans l'estimation",
        "Done",
        "done",
        "Alice",
        original_estimate_seconds=7200,
    )
    unfinished = Issue(
        "10002",
        "ABC-2",
        "Encore en cours",
        "In Progress",
        "indeterminate",
        "Bob",
    )
    not_started = Issue(
        "10003",
        "ABC-3",
        "Pas commence",
        "To Do",
        "new",
        None,
    )

    review = build_sprint_review(
        [over_estimate, completed_within_estimate, unfinished, not_started],
        {
            "10001": [TempoWorklog("10001", 7200, date(2026, 5, 1), "Alice")],
            "10002": [TempoWorklog("10002", 1800, date(2026, 5, 1), "Bob")],
            "10004": [TempoWorklog("10004", 3600, date(2026, 5, 1), "Alice")],
        },
        done_status_categories={"done"},
        min_seconds=1,
    )

    assert [item.issue.key for item in review.completed] == ["ABC-1", "ABC-4"]
    assert [item.is_over_original_estimate for item in review.completed] == [
        True,
        False,
    ]
    assert [item.issue.key for item in review.unfinished_with_time] == ["ABC-2"]
    assert [item.issue.key for item in review.not_started] == ["ABC-3"]


def test_build_out_of_sprint_items_excludes_sprint_issues_and_groups_by_issue() -> None:
    sprint_issue = Issue("10001", "ABC-1", "Sprint", "Done", "done", "Alice")
    outside_issue = Issue(
        "10002",
        "ABC-2",
        "Hors sprint",
        "In Progress",
        "indeterminate",
        "Bob",
        issue_type="Bug",
    )
    other_outside_issue = Issue(
        "10003",
        "ABC-3",
        "Autre hors sprint",
        "In Progress",
        "indeterminate",
        "Bob",
        issue_type="Task",
    )
    worklogs = [
        TempoWorklog("10001", 3600, date(2026, 5, 2), "Alice", issue_key="ABC-1"),
        TempoWorklog("10002", 1800, date(2026, 5, 3), "Bob", issue_key="ABC-2"),
        TempoWorklog("10002", 3600, date(2026, 5, 4), "Alice", issue_key="ABC-2"),
        TempoWorklog("10003", 900, date(2026, 5, 5), "Bob", issue_key="ABC-3"),
        TempoWorklog("10004", 900, date(2026, 5, 6), "Bob", issue_key="ABC-404"),
    ]

    items = build_out_of_sprint_items(
        sprint_issue_keys={sprint_issue.key},
        issues_by_key={
            outside_issue.key: outside_issue,
            other_outside_issue.key: other_outside_issue,
        },
        worklogs=worklogs,
    )

    assert [item.issue.key for item in items] == ["ABC-2", "ABC-3"]
    assert items[0].tempo_seconds == 5400
    assert items[0].total_seconds == 5400
    assert [(entry.user, entry.seconds) for entry in items[0].time_spent_by_user] == [
        ("Alice", 3600),
        ("Bob", 1800),
    ]


def test_build_out_of_sprint_items_keeps_total_time_separate_from_sprint_time() -> None:
    outside_issue = Issue(
        "10002",
        "ABC-2",
        "Hors sprint",
        "In Progress",
        "indeterminate",
        "Bob",
    )

    items = build_out_of_sprint_items(
        sprint_issue_keys=set(),
        issues_by_key={outside_issue.key: outside_issue},
        worklogs=[
            TempoWorklog("10002", 1800, date(2026, 5, 3), "Bob", issue_key="ABC-2"),
        ],
        total_worklogs_by_issue_key={
            "ABC-2": [
                TempoWorklog("10002", 1800, date(2026, 5, 3), "Bob"),
                TempoWorklog("10002", 3600, date(2026, 4, 20), "Alice"),
            ],
        },
    )

    assert items[0].tempo_seconds == 1800
    assert items[0].total_seconds == 5400
    assert [
        (entry.user, entry.seconds) for entry in items[0].total_time_spent_by_user
    ] == [
        ("Alice", 3600),
        ("Bob", 1800),
    ]
