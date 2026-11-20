import pytest

from resprint.frontend.report.reviews import issue_review_count
from resprint.frontend.report.tables import render_report_sections
from resprint.models import Issue, IssueReviewItem, SprintReview
from resprint.reviews import issue_review_inconsistency


@pytest.mark.parametrize(
    ("done", "states", "expected"),
    [
        (True, [], None),
        (False, [], None),
        (True, [("closed", False)], None),
        (True, [("open", False)], "reviews.inconsistent_done"),
        (True, [("abandoned", False)], None),
        (False, [("abandoned", False)], None),
        (True, [("unknown", None)], None),
        (False, [("closed", False)], "reviews.inconsistent_closed"),
        (False, [("closed", False), ("open", True)], "reviews.inconsistent_ready"),
        (False, [("open", True)], "reviews.inconsistent_ready"),
        (False, [("open", False)], None),
        (False, [("open", None)], None),
        (False, [("closed", False), ("unknown", None)], None),
        (
            False,
            [("closed", False), ("abandoned", False)],
            "reviews.inconsistent_closed",
        ),
        (True, [("closed", False), ("abandoned", False)], None),
        (False, [("open", True), ("abandoned", False)], "reviews.inconsistent_ready"),
        (False, [("open", False), ("abandoned", False)], None),
        (True, [("open", False), ("abandoned", False)], "reviews.inconsistent_done"),
        (False, [("unknown", None), ("abandoned", False)], None),
    ],
)
def test_only_confirmed_mismatches_are_flagged(done, states, expected):
    refs = [dict(state=state, ready_to_close=ready) for state, ready in states]
    assert issue_review_inconsistency(refs, done) == expected


def test_warning_uses_report_classification_and_excludes_outside_scope():
    # Report classification can consider custom Jira categories complete.
    issue = Issue("1", "A-1", "Issue", "Custom done", "custom-done", None)
    item = IssueReviewItem(issue, 0, 0, 0)
    snapshot = {
        "items": [
            dict(
                state="open",
                ready_to_close=False,
                issue_keys=["A-1"],
                label="D1",
                url="https://phorge.test/D1",
            )
        ]
    }
    completed = render_report_sections(
        SprintReview((item,), (), ()), "https://jira.test", snapshot
    )
    assert "issue-review-warning" in completed
    assert "aria-label=" in completed
    outside = render_report_sections(
        SprintReview((), (), (), (item,)), "https://jira.test", snapshot
    )
    assert "issue-review-warning" not in outside
    cell = issue_review_count(snapshot, "A-1", True)
    assert "0/1" in cell.html
    assert cell.sort_value == 0
