import pytest
import requests

from resprint.helpers.phorge import PhorgeClient, _parse_reviewer_counts
from resprint.models import ReviewStatus


def reviewer(phid, status="accepted", blocking=False):
    return dict(reviewerPHID=phid, status=status, isBlocking=blocking)


def attachment(*refs):
    return {"reviewers": {"reviewers": list(refs)}}


@pytest.mark.parametrize(
    ("refs", "expected"),
    [
        (attachment(), (0, 0)),
        (attachment(reviewer("A"), reviewer("B")), (2, 0)),
        (attachment(reviewer("A"), reviewer("A")), (1, 0)),
        (attachment(reviewer("A", "blocking", True)), (0, 1)),
        (attachment(reviewer("A", "added", True)), (0, 1)),
        (attachment(reviewer("A", "accepted-older")), (0, 0)),
        (attachment(reviewer("A", "accepted-older", True)), (0, 1)),
        (attachment(reviewer("A"), reviewer("A", "rejected")), None),
        ({}, None),
        (attachment({"reviewerPHID": "A", "status": "accepted"}), None),
        (attachment(reviewer("A", "new-status")), None),
    ],
)
def test_reviewer_counts_require_complete_distinct_decisions(refs, expected):
    assert _parse_reviewer_counts(refs) == expected


@pytest.mark.parametrize(
    ("code", "validations", "pending", "expected"),
    [
        ("2", 2, 0, True),
        ("2", 1, 0, False),
        ("2", 3, 1, False),
        ("2", None, None, None),
        ("3", 2, 0, False),
        ("4", 2, 0, False),
        ("99", 2, 0, None),
    ],
)
def test_ready_to_close(code, validations, pending, expected):
    status = ReviewStatus(
        1,
        status_code=code,
        validation_count=validations,
        pending_required_approval_count=pending,
    )
    assert status.ready_to_close is expected


def test_enrichment_paginates_and_retains_base_data_on_failure(monkeypatch):
    client = PhorgeClient("https://phorge.test", "test")
    calls = []

    def post(path, params):
        calls.append((path, params.copy()))
        if path == "/api/differential.query":
            return {"result": [{"id": "1", "status": "2"}, {"id": "2", "status": "2"}]}
        if path == "/api/phid.query":
            return {"result": {"A": {"fullName": "Alice"}}}
        assert path == "/api/differential.revision.search"
        if params.get("after"):
            raise requests.Timeout()
        return {
            "result": {
                "data": [
                    {"id": 1, "attachments": attachment(reviewer("A"), reviewer("B"))}
                ],
                "cursor": {"after": "next"},
            }
        }

    monkeypatch.setattr(client, "_post", post)
    result = client.query_revisions((1, 2))
    assert result[1].ready_to_close is True
    assert result[2].state == "open"
    assert result[2].ready_to_close is None
    assert calls[1][1]["attachments[reviewers]"] == 1
    assert calls[2][1]["after"] == "next"


def test_batches_limit_search_to_100_ids(monkeypatch):
    client = PhorgeClient("https://phorge.test", "test")
    batches = []

    def post(path, params):
        batches.append(sum(key.startswith("constraints[ids]") for key in params))
        return {"result": {"data": []}}

    monkeypatch.setattr(client, "_post", post)
    statuses = {i: ReviewStatus(i) for i in range(1, 202)}
    client._enrich_reviewer_decisions(statuses)
    assert batches == [100, 100, 1]


def test_name_lookup_keeps_decisions_on_transport_failure(monkeypatch):
    from resprint.models import ReviewDecision

    client = PhorgeClient("https://phorge.test", "test")
    statuses = {
        1: ReviewStatus(
            1,
            status_code="2",
            validation_count=2,
            pending_required_approval_count=0,
            reviewers=(
                ReviewDecision("A", "accepted", False),
                ReviewDecision("B", "accepted", False),
            ),
        )
    }

    def fail(path, params):
        raise requests.Timeout()

    monkeypatch.setattr(client, "_post", fail)
    client._enrich_reviewer_names(statuses)
    assert statuses[1].ready_to_close is True
    assert statuses[1].reviewers[0].name is None


def test_names_are_batched_and_shared_between_reviews(monkeypatch):
    from resprint.models import ReviewDecision

    client = PhorgeClient("https://phorge.test", "test")
    statuses = {
        i: ReviewStatus(i, reviewers=(ReviewDecision("GROUP", "blocking", True),))
        for i in range(1, 102)
    }
    calls = []

    def post(path, params):
        calls.append(params)
        assert path == "/api/phid.query"
        return {"result": {"GROUP": {"fullName": "Review team"}}}

    monkeypatch.setattr(client, "_post", post)
    client._enrich_reviewer_names(statuses)
    assert len(calls) == 1
    assert statuses[101].reviewers[0].name == "Review team"


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [
        (2, 0, False),
        (1, 1, True),
        (2, 1, False),
        (0, 0, False),
    ],
)
def test_report_applies_configured_closure_thresholds(
    monkeypatch, minimum, maximum, expected
):
    from types import SimpleNamespace

    from resprint.models import Issue, ReviewRef
    from resprint.reviews import load_reviews

    settings = SimpleNamespace(
        reviews_enabled=True,
        phorge_base_url="https://phorge.test",
        phorge_api_token="test",
        phorge_ca_bundle=None,
        jira_ca_bundle=None,
        review_min_validations=minimum,
        review_max_pending_required_approvals=maximum,
    )
    monkeypatch.setattr(
        PhorgeClient,
        "query_revisions",
        lambda self, ids: {
            1: ReviewStatus(
                1,
                status_code="2",
                validation_count=1,
                pending_required_approval_count=1,
            )
        },
    )
    snapshot = load_reviews(
        settings,
        [Issue("1", "A-1", "Issue", "Open", "new", None, reviews=(ReviewRef(1),))],
    )
    assert snapshot["items"][0]["ready_to_close"] is expected
    assert snapshot["closure_criteria"] == dict(
        min_validations=minimum, max_pending_required_approvals=maximum
    )


def test_author_name_is_resolved_without_reviewer_data(monkeypatch):
    client = PhorgeClient("https://phorge.test", "test")
    calls = []

    def post(path, params):
        calls.append((path, params.copy()))
        if path == "/api/differential.query":
            return {"result": [{"id": "1", "status": "2", "authorPHID": "AUTHOR"}]}
        if path == "/api/differential.revision.search":
            raise requests.Timeout()
        assert path == "/api/phid.query"
        assert params == {"api.token": "test", "phids[0]": "AUTHOR"}
        return {"result": {"AUTHOR": {"fullName": "Alice Author"}}}

    monkeypatch.setattr(client, "_post", post)
    status = client.query_revisions((1,))[1]
    assert status.author_phid == "AUTHOR"
    assert status.author_name == "Alice Author"
    assert status.validation_count is None
    assert len(calls) == 3


def test_author_and_reviewer_share_one_name_lookup(monkeypatch):
    from resprint.models import ReviewDecision

    client = PhorgeClient("https://phorge.test", "test")
    statuses = {
        1: ReviewStatus(
            1, author_phid="A", reviewers=(ReviewDecision("A", "accepted", False),)
        )
    }

    def post(path, params):
        assert params == {"api.token": "test", "phids[0]": "A"}
        return {"result": {"A": {"name": "Alice"}}}

    monkeypatch.setattr(client, "_post", post)
    client._enrich_reviewer_names(statuses)
    assert statuses[1].author_name == "Alice"
    assert statuses[1].reviewers[0].name == "Alice"


@pytest.mark.parametrize(
    "label, expected",
    [
        (None, "unknown"),
        ("Closed", "closed"),
        ("Abandoned", "abandoned"),
        ("Accepted", "open"),
        ("Needs Review", "open"),
    ],
)
def test_legacy_status_labels_are_used_when_no_status_code_is_available(
    label, expected
):
    status = ReviewStatus(1, status_name=label)
    assert status.state == expected
    assert status.ready_to_close is (
        False if expected in {"closed", "abandoned"} else None
    )


def test_unknown_status_code_does_not_fall_back_to_a_misleading_label():
    status = ReviewStatus(1, status_code="new-code", status_name="Closed")
    assert status.state == "unknown"
    assert status.ready_to_close is None
