from datetime import date

from sprint_review.analyzer import build_review_items, build_sprint_review
from sprint_review.models import Issue, TempoWorklog


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
    assert items[0].authors == ("Alice", "Bob")
    assert [(entry.user, entry.seconds) for entry in items[0].time_spent_by_user] == [
        ("Alice", 3600),
        ("Bob", 1800),
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
