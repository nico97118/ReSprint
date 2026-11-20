from types import SimpleNamespace

import requests

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
    assert '"code_reviews"' not in render_json(review, sprint)


def test_configuration_activation_and_missing_token(tmp_path, monkeypatch):
    import pytest

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
    with pytest.warns(UserWarning, match="Phorge disabled"):
        assert not Settings.from_sources().reviews_enabled
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
