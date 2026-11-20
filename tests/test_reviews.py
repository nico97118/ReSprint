from types import SimpleNamespace

from resprint.models import Issue, ReviewRef


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
