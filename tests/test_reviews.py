from types import SimpleNamespace

import pytest
import requests

from resprint.helpers.phorge import PhorgeAPIError
from resprint.models import Issue, ReviewRef, ReviewStatus
from resprint.reviews import load_reviews


def settings(enabled=True):
    return SimpleNamespace(
        reviews_enabled=enabled,
        review_min_validations=2,
        review_max_pending_required_approvals=0,
        phorge_base_url="https://phorge.test",
        phorge_api_token="test",
        phorge_ca_bundle=None,
        jira_ca_bundle=None,
    )


def issue(key, *ids):
    return Issue(
        id=key,
        key=key,
        summary=key,
        status="In progress",
        status_category="indeterminate",
        assignee=None,
        reviews=tuple(ReviewRef(i) for i in ids),
    )


def test_disabled_and_empty_do_not_build_client(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected client")

    monkeypatch.setattr("resprint.reviews.PhorgeClient", fail)
    assert load_reviews(settings(False), [issue("A-1", 1)]) is None
    assert load_reviews(settings(), [])["items"] == []


def test_unique_reviews_keep_all_tickets_and_unknown_results(monkeypatch):
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def query_revisions(self, ids):
            assert ids == (1, 2)
            return {1: ReviewStatus(id=1, status_code="3")}

        def query_repository_names(self, ids):
            return {}

    monkeypatch.setattr("resprint.reviews.PhorgeClient", Client)
    result = load_reviews(settings(), [issue("A-1", 1, 2), issue("A-2", 1)])
    assert result["items"][0]["issue_keys"] == ["A-1", "A-2"]
    assert result["counts"] == dict(open=0, closed=1, abandoned=0, unknown=1)


def test_phorge_failure_keeps_references(monkeypatch):
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def query_revisions(self, ids):
            raise requests.Timeout()

        def query_repository_names(self, ids):
            return {}

    monkeypatch.setattr("resprint.reviews.PhorgeClient", Client)
    result = load_reviews(settings(), [issue("A-1", 1)])
    assert result["warning"] == "reviews.unavailable"
    assert result["items"][0]["state"] == "unknown"


def test_snapshot_renders_in_all_formats_even_without_classified_issues():
    import json
    from datetime import date

    from resprint.exporters.json import render_json
    from resprint.exporters.markdown import render_markdown
    from resprint.frontend.report.page import render_html
    from resprint.models import Sprint, SprintReview

    snapshot = dict(
        checked_at="2026-11-19T12:00:00+00:00",
        warning=None,
        counts=dict(open=0, closed=0, abandoned=0, unknown=1),
        items=[
            dict(
                id=12,
                label="D12",
                url="https://phorge.test/D12",
                title="<script>unsafe</script>",
                state="unknown",
                status_name=None,
                repository=None,
                age_days=None,
                issue_keys=["A-1"],
            )
        ],
    )
    review = SprintReview((), (), ())
    sprint = Sprint(1, "Sprint", date(2026, 11, 1), date(2026, 11, 15))
    assert (
        json.loads(render_json(review, sprint, code_reviews=snapshot))["code_reviews"]
        == snapshot
    )
    markdown = render_markdown(review, sprint, "https://jira.test", snapshot)
    assert "[D12](https://phorge.test/D12)" in markdown
    html = render_html(review, sprint, "https://jira.test", code_reviews=snapshot)
    assert 'id="code-reviews"' in html
    assert "https://jira.test/browse/A-1" in html
    assert "<script>unsafe</script>" not in html
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in html
    assert '"code_reviews"' not in render_json(review, sprint)


def test_configuration_activation_and_missing_token(tmp_path, monkeypatch, caplog):

    from resprint.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JIRA_API_TOKEN", "test")
    monkeypatch.delenv("PHORGE_API_TOKEN", raising=False)
    (tmp_path / "setting.toml").write_text("""
[jira]
base_url = "https://jira.test"
[phorge]
enabled = true
jira_fields = ["customfield_1", "customfield_1"]
base_url = "https://phorge.test/"
""")
    with caplog.at_level("WARNING", logger="resprint.config"):
        assert not Settings.from_sources().reviews_enabled
    assert "Phorge disabled" in caplog.text
    monkeypatch.setenv("PHORGE_API_TOKEN", "test")
    configured = Settings.from_sources()
    assert configured.reviews_enabled
    assert configured.review_fields == ("customfield_1",)
    assert configured.phorge_base_url == "https://phorge.test"


def test_jira_parsing_only_scans_configured_fields():
    from resprint.helpers.jira import _parse_issue

    raw = dict(
        id="1",
        key="A-1",
        fields=dict(
            customfield_1=["https://phorge.test/D12 D12 D0 XD99", None, "D13"],
            description="D99",
        ),
    )
    assert _parse_issue(raw).reviews == ()
    assert _parse_issue(raw, review_fields=("customfield_1",)).reviews == (
        ReviewRef(12),
        ReviewRef(13),
    )


def test_client_posts_unique_requested_ids_and_normalizes_states(monkeypatch):
    from resprint.helpers.phorge import PhorgeClient

    client = PhorgeClient("https://phorge.test", "test")

    def post(url, **kwargs):
        if url.endswith("/api/differential.revision.search"):
            return SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: {"result": {"data": []}}
            )
        assert url.endswith("/api/differential.query")
        assert kwargs["data"]["ids[0]"] == 12
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"result": [{"id": "12", "status": "2", "title": "Accepted"}]},
        )

    monkeypatch.setattr(client.session, "post", post)
    assert client.query_revisions((12,))[12].state == "open"


def test_report_only_calls_phorge_query_and_search_endpoints(monkeypatch):
    """Exercise the real client and loader while recording every HTTP request."""
    calls = []

    def request(session, method, url, **kwargs):
        calls.append((method, url, kwargs["data"].copy()))
        if url == "https://phorge.test/api/differential.query":
            payload = {
                "result": [
                    {"id": "12", "status": "2", "repositoryPHID": "PHID-REPO-test"}
                ]
            }
        elif url == "https://phorge.test/api/differential.revision.search":
            payload = {
                "result": {
                    "data": [
                        {
                            "id": 12,
                            "attachments": {
                                "reviewers": {
                                    "reviewers": [
                                        {
                                            "reviewerPHID": "A",
                                            "status": "accepted",
                                            "isBlocking": False,
                                        },
                                        {
                                            "reviewerPHID": "B",
                                            "status": "accepted",
                                            "isBlocking": False,
                                        },
                                    ]
                                }
                            },
                        }
                    ]
                }
            }
        elif url == "https://phorge.test/api/phid.query":
            payload = {"result": {"A": {"fullName": "Alice"}, "B": {"name": "Bob"}}}
        elif url == "https://phorge.test/api/diffusion.repository.search":
            payload = {
                "result": {
                    "data": [
                        {"phid": "PHID-REPO-test", "fields": {"name": "Repository"}}
                    ],
                    "cursor": {"after": None},
                }
            }
        else:
            raise AssertionError(f"Unexpected Phorge endpoint: {url}")
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr(requests.Session, "request", request)
    result = load_reviews(settings(), [issue("A-1", 12), issue("A-2", 12)])
    assert [(method, url) for method, url, _ in calls] == [
        ("POST", "https://phorge.test/api/differential.query"),
        ("POST", "https://phorge.test/api/differential.revision.search"),
        ("POST", "https://phorge.test/api/phid.query"),
        ("POST", "https://phorge.test/api/diffusion.repository.search"),
    ]
    assert calls[0][2] == {"api.token": "test", "ids[0]": 12}
    assert calls[1][2] == {
        "api.token": "test",
        "constraints[ids][0]": 12,
        "attachments[reviewers]": 1,
    }
    assert calls[2][2] == {"api.token": "test", "phids[0]": "A", "phids[1]": "B"}
    assert calls[3][2] == {
        "api.token": "test",
        "constraints[phids][0]": "PHID-REPO-test",
    }
    assert result["items"][0]["repository"] == "Repository"

    assert result["items"][0]["reviewers"][0]["name"] == "Alice"
    assert result["items"][0]["validation_count"] == 2
    assert result["items"][0]["pending_required_approval_count"] == 0
    assert result["items"][0]["ready_to_close"] is True


def test_conduit_error_is_reported_without_response_secrets(monkeypatch):
    def request(session, method, url, **kwargs):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "result": None,
                "error_code": "ERR-INVALID-AUTH",
                "error_info": "secret-token-and-private-data",
            },
        )

    monkeypatch.setattr(requests.Session, "request", request)
    result = load_reviews(settings(), [issue("A-1", 12)])
    assert result["warning_detail"] == "Conduit: ERR-INVALID-AUTH"
    assert result["items"][0]["state"] == "unknown"
    assert "secret-token" not in str(result)


def test_tls_diagnostic_does_not_expose_exception_details():
    from resprint.reviews import _failure_detail

    detail = _failure_detail(requests.exceptions.SSLError("secret-token"))
    assert "TLS" in detail
    assert "phorge.ca_bundle" in detail
    assert "secret-token" not in detail


def test_ticket_review_counts_and_detail_badges():
    from resprint.frontend.report.reviews import (
        issue_review_count,
        render_issue_reviews,
    )

    snapshot = {
        "items": [
            dict(
                label=f"D{number}",
                url=f"https://phorge.test/D{number}",
                state=state,
                issue_keys=["A-1"],
            )
            for number, state in enumerate(
                ("open", "closed", "abandoned", "unknown"), 1
            )
        ]
    }
    assert issue_review_count(snapshot, "A-1").html == "1/4"
    assert issue_review_count(snapshot, "A-2").html == "—"
    details = render_issue_reviews(snapshot, "A-1")
    assert "Reviews" in details
    assert 'href="https://phorge.test/D1"' in details
    assert "badge-status-indeterminate" in details
    assert "badge-status-done" in details
    assert details.count("badge-status-unknown") == 2
    assert render_issue_reviews(None, "A-1") == ""
    assert render_issue_reviews(snapshot, "A-2") == ""


def test_ready_to_close_badge_in_recap_and_ticket_details():
    from resprint.frontend.i18n import configure_language, current_language
    from resprint.frontend.report.reviews import render_issue_reviews, render_reviews

    previous = current_language()
    configure_language("fr")
    try:
        row = dict(
            id=12,
            label="D12",
            url="https://phorge.test/D12",
            state="open",
            title="Review",
            status_name="Accepted",
            repository=None,
            age_days=2,
            issue_keys=["A-1"],
            ready_to_close=True,
            validation_count=2,
            pending_required_approval_count=0,
        )
        snapshot = dict(items=[row], counts={"open": 1}, warning=None)
        html = render_reviews(snapshot, "https://jira.test")
        assert "À clôturer" in html
        assert "badge-review-ready" in html
        assert ">Action<" not in html
        assert "2 validations" not in html
        assert "data-table-filter" in html
        details = render_issue_reviews(snapshot, "A-1")
        assert "À clôturer" in details
        assert details.count('class="badge ') == 1
        assert "data-filter-option" in html
        assert 'value="à clôturer"' in html
        row["ready_to_close"] = None
        assert "À clôturer" not in render_reviews(snapshot, "https://jira.test")
        assert "À clôturer" not in render_issue_reviews(snapshot, "A-1")
    finally:
        configure_language(previous)


def test_review_details_distinguish_decisions_and_escape_names():
    from resprint.frontend.report.reviews import review_decision_details

    row = {
        "reviewers": [
            dict(status="accepted", is_blocking=False, name="<Alice>"),
            dict(status="blocking", is_blocking=True, name="Team"),
            dict(status="rejected", is_blocking=False, name="Bob"),
            dict(status="accepted-older", is_blocking=False, name="Old approval"),
            dict(status="added", is_blocking=False, name="Waiting"),
            dict(status="blocking", is_blocking=True, name=None),
        ]
    }
    html = review_decision_details(row).html
    assert "&lt;Alice&gt;" in html
    assert "<Alice>" not in html
    assert "Team" in html and "Bob" in html
    assert "review-decision-approved" in html
    assert "review-decision-required_pending" in html
    assert "review-decision-changes_requested" in html
    assert 'role="img" aria-label=' in html
    assert "Old approval" not in html and "Waiting" not in html
    assert review_decision_details({"reviewers": None}).html == "—"
    assert review_decision_details({"reviewers": []}).html == "—"


def test_review_status_and_decisions_are_in_expandable_row_details():
    from resprint.frontend.report.reviews import render_reviews

    snapshot = dict(
        items=[
            dict(
                id=1,
                label="D1",
                url="https://phorge.test/D1",
                title="Review",
                author_name="<Alice Author>",
                state="open",
                status_name="<Accepted>",
                repository="Repo",
                age_days=1,
                issue_keys=["A-1"],
                reviewers=[dict(status="accepted", is_blocking=False, name="Alice")],
            )
        ],
        counts={"open": 1},
        warning=None,
    )
    html = render_reviews(snapshot, "https://jira.test")
    header = html.split("<thead>")[1].split("</thead>")[0]
    assert "Statut Phorge" not in header and "Phorge status" not in header
    assert "Auteur" in header or "Author" in header
    assert "&lt;Alice Author&gt;" in html
    assert "<Alice Author>" not in html
    assert ">Détails<" not in header and ">Details<" not in header
    assert "data-row-toggle" in html
    assert "data-table-detail-row" in html
    assert 'aria-expanded="false"' in html
    detail = html.split('class="table-detail-content"')[1]
    assert "&lt;Accepted&gt;" in detail
    assert "<Accepted>" not in html
    assert "Alice" in detail and "review-decision-approved" in detail
    assert "data-search=" in html or "data-search-text=" in html


@pytest.mark.parametrize(
    "error, detail",
    [
        (requests.exceptions.SSLError("secret URL"), "TLS:"),
        (requests.ConnectionError("secret URL"), "Connection:"),
        (ValueError("secret response body"), "Invalid API response"),
        (PhorgeAPIError("ERR-INVALID-AUTH"), "Conduit: ERR-INVALID-AUTH"),
        (requests.RequestException("secret URL"), "RequestException"),
    ],
)
def test_review_errors_preserve_references_without_leaking_diagnostics(
    monkeypatch, caplog, error, detail
):
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def query_revisions(self, ids):
            raise error

        def query_repository_names(self, ids):
            assert ids == ()
            return {}

    monkeypatch.setattr("resprint.reviews.PhorgeClient", Client)
    with caplog.at_level("WARNING", logger="resprint"):
        snapshot = load_reviews(settings(), [issue("A-1", 1, 1)])
    assert all(record.levelname == "WARNING" for record in caplog.records)
    assert any(
        "retaining unknown references" in record.message for record in caplog.records
    )
    assert snapshot["warning"] == "reviews.unavailable"
    assert snapshot["warning_detail"].startswith(detail)
    assert "secret" not in snapshot["warning_detail"]
    assert len(snapshot["items"]) == 1
    assert snapshot["items"][0]["issue_keys"] == ["A-1"]
    assert snapshot["counts"]["unknown"] == 1


def test_repository_lookup_failure_keeps_known_review_status(monkeypatch):
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def query_revisions(self, ids):
            return {1: ReviewStatus(id=1, status_code="3", repository_phid="repo")}

        def query_repository_names(self, ids):
            assert ids == ("repo",)
            raise requests.Timeout()

    monkeypatch.setattr("resprint.reviews.PhorgeClient", Client)
    snapshot = load_reviews(settings(), [issue("A-1", 1)])
    assert snapshot["warning"] == "reviews.repositories_unavailable"
    assert snapshot["items"][0]["state"] == "closed"
    assert snapshot["items"][0]["repository"] is None
    assert snapshot["counts"]["closed"] == 1


@pytest.mark.parametrize("has_references", [False, True])
def test_empty_or_failed_review_lookup_is_explicit_in_all_report_formats(
    monkeypatch, has_references
):
    import json
    from datetime import date
    from unittest.mock import Mock

    from resprint.exporters.json import render_json
    from resprint.exporters.markdown import render_markdown
    from resprint.frontend.report.page import render_html
    from resprint.models import Sprint, SprintReview

    response = requests.Response()
    response.status_code = 503
    client = Mock()
    client.query_revisions.side_effect = requests.HTTPError(
        "secret response", response=response
    )
    client.query_repository_names.return_value = {}
    monkeypatch.setattr("resprint.reviews.PhorgeClient", Mock(return_value=client))
    snapshot = load_reviews(settings(), [issue("A-1", 1)] if has_references else [])
    review = SprintReview((), (), ())
    sprint = Sprint(1, "Sprint", date(2026, 5, 1), date(2026, 5, 15))
    html = render_html(review, sprint, "https://jira.test", code_reviews=snapshot)
    markdown = render_markdown(review, sprint, "https://jira.test", snapshot)
    exported = json.loads(render_json(review, sprint, code_reviews=snapshot))
    assert exported["code_reviews"] == snapshot
    if has_references:
        assert snapshot["warning_detail"] == "HTTP 503"
        assert "HTTP 503" in html and "HTTP 503" in markdown
        assert "secret response" not in html and "secret response" not in markdown
        assert snapshot["items"][0]["state"] == "unknown"
    else:
        client.query_revisions.assert_not_called()
        assert snapshot["items"] == []
        assert snapshot["warning"] is None
        assert "Aucune review référencée" in markdown
