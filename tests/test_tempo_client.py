from datetime import date
from typing import Any

import pytest
import requests

from resprint.helpers.tempo import TempoTeamWorklogClient


class FakeTempoTeamWorklogClient(TempoTeamWorklogClient):
    def __init__(
        self,
        payload: object,
        jira_user_payloads: list[dict[str, object] | None] | None = None,
    ) -> None:
        self.payload = payload
        self.post_payloads = list(payload) if isinstance(payload, tuple) else None
        self.jira_user_payloads = list(jira_user_payloads or [])
        self.calls: list[str] = []
        self.gets: list[tuple[str, dict[str, str] | None]] = []
        self.posts: list[tuple[str, dict[str, object]]] = []

    def _get(self, path: str, params: dict[str, str] | None = None) -> object:
        if path == "/rest/api/2/user":
            self.gets.append((path, params))
            if self.jira_user_payloads:
                jira_user_payload = self.jira_user_payloads.pop(0)
                if jira_user_payload is not None:
                    return jira_user_payload
            response = requests.Response()
            response.status_code = 404
            raise requests.HTTPError(response=response)
        self.calls.append(path)
        return self.payload

    def _post(self, path: str, payload: dict[str, object]) -> object:
        self.posts.append((path, payload))
        if self.post_payloads is not None:
            return self.post_payloads.pop(0)
        return self.payload


def test_list_teams_parses_tempo_team_payload_list() -> None:
    client = FakeTempoTeamWorklogClient(
        [
            {"id": 10, "name": "Equipe ABC"},
            {"id": 20, "name": "Equipe DEF"},
        ]
    )

    teams = client.list_teams()

    assert [(team.id, team.name) for team in teams] == [
        (10, "Equipe ABC"),
        (20, "Equipe DEF"),
    ]


def test_tempo_team_client_uses_configured_ca_bundle() -> None:
    client = TempoTeamWorklogClient(
        base_url="https://jira.example.test",
        api_token="token",
        ca_bundle="/etc/ssl/certs/company-ca.pem",
    )

    assert client.session.verify == "/etc/ssl/certs/company-ca.pem"


def test_list_teams_parses_wrapped_tempo_team_payload() -> None:
    client = FakeTempoTeamWorklogClient(
        {
            "results": [
                {"teamId": 10, "teamName": "Equipe ABC"},
            ]
        }
    )

    teams = client.list_teams()

    assert [(team.id, team.name) for team in teams] == [(10, "Equipe ABC")]


def test_list_teams_ignores_unexpected_payload_items() -> None:
    payload: list[Any] = [
        {"id": 10, "name": "Equipe ABC"},
        "unexpected",
    ]
    client = FakeTempoTeamWorklogClient(payload)

    teams = client.list_teams()

    assert [(team.id, team.name) for team in teams] == [(10, "Equipe ABC")]


def test_search_team_worklogs_posts_team_and_dates() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "alice",
                        "displayName": "Alice",
                        "key": "JIRAUSER10000",
                    }
                }
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 5400,
                        "startDate": "2026-05-10",
                        "worker": {
                            "displayName": "Alice",
                            "name": "alice",
                            "key": "JIRAUSER10000",
                        },
                        "issue": {
                            "id": 10001,
                            "key": "ABC-1",
                        },
                        "comment": "Analyse",
                    }
                ]
            },
        )
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert client.posts == [
        (
            "/rest/tempo-teams/2/team/members",
            {
                "ids": ["42"],
                "onlyActive": True,
            },
        ),
        (
            "/rest/tempo-timesheets/4/worklogs/search",
            {
                "from": "2026-05-01",
                "to": "2026-05-15",
                "teamId": [42],
            },
        ),
    ]
    assert len(worklogs) == 1
    assert worklogs[0].issue_id == "10001"
    assert worklogs[0].issue_key == "ABC-1"
    assert worklogs[0].time_spent_seconds == 5400
    assert worklogs[0].start_date == date(2026, 5, 10)
    assert worklogs[0].author == "Alice"
    assert worklogs[0].author_key == "JIRAUSER10000"
    assert worklogs[0].description == "Analyse"


def test_search_team_worklogs_filters_out_non_team_members() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {"name": "alice", "displayName": "Alice"},
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"name": "alice", "displayName": "Alice"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                    {
                        "originTaskId": 10002,
                        "timeSpentSeconds": 3600,
                        "startDate": "2026-05-10",
                        "worker": {
                            "name": "other.team",
                            "displayName": "Other Team",
                        },
                        "issue": {"id": 10002, "key": "ABC-2"},
                    },
                ]
            },
        )
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert [worklog.issue_key for worklog in worklogs] == ["ABC-1"]


def test_search_team_worklogs_resolves_jirauser_author_from_team_member() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "prenom.nom",
                        "displayName": "Prenom Nom",
                        "key": "JIRAUSER12345",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"key": "JIRAUSER12345"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        )
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert worklogs[0].author == "Prenom Nom"


def test_search_team_worklogs_resolves_name_author_from_team_member() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "nom.prenom",
                        "displayName": "Prenom Nom",
                        "key": "JIRAUSER12345",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"name": "nom.prenom"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        )
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert worklogs[0].author == "Prenom Nom"
    assert worklogs[0].author_key == "nom.prenom"
    assert worklogs[0].author_identity.name == "nom.prenom"
    assert worklogs[0].author_identity.display_name == "Prenom Nom"


def test_search_team_worklogs_resolves_team_member_from_jira_datacenter() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "nom.prenom",
                        "displayName": "nom.prenom",
                        "key": "JIRAUSER12345",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"name": "nom.prenom"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        ),
        jira_user_payloads=[
            {
                "name": "nom.prenom",
                "displayName": "Prenom Nom",
                "key": "JIRAUSER12345",
            },
        ],
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert client.gets == [
        ("/rest/api/2/user", {"key": "JIRAUSER12345"}),
    ]
    assert worklogs[0].author == "Prenom Nom"
    assert worklogs[0].author_identity.display_name == "Prenom Nom"


def test_search_team_worklogs_keeps_tempo_identifier_after_jira_resolution() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "nom.prenom",
                        "displayName": "nom.prenom",
                        "key": "JIRAUSER12345",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"name": "nom.prenom"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        ),
        jira_user_payloads=[
            {
                "name": "jira.internal.username",
                "displayName": "Prenom Nom",
                "key": "JIRAUSER12345",
            },
        ],
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert [worklog.issue_key for worklog in worklogs] == ["ABC-1"]
    assert worklogs[0].author == "Prenom Nom"
    assert worklogs[0].author_identity.display_name == "Prenom Nom"


def test_search_team_worklogs_continues_after_cached_jira_user_miss() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "name": "nom.prenom",
                        "displayName": "nom.prenom",
                        "key": "unknown-key",
                    },
                },
                {
                    "member": {
                        "name": "nom.prenom",
                        "displayName": "nom.prenom",
                        "key": "unknown-key",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"name": "nom.prenom"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        ),
        jira_user_payloads=[
            None,
            {
                "name": "nom.prenom",
                "displayName": "Prenom Nom",
                "key": "JIRAUSER12345",
            },
        ],
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert client.gets == [
        ("/rest/api/2/user", {"key": "unknown-key"}),
        ("/rest/api/2/user", {"username": "nom.prenom"}),
    ]
    assert worklogs[0].author == "Prenom Nom"


def test_search_team_worklogs_resolves_tempo_display_name_from_jira_datacenter() -> (
    None
):
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "displayName": "nom.prenom",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"displayName": "nom.prenom"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                ]
            },
        ),
        jira_user_payloads=[
            {
                "name": "nom.prenom",
                "displayName": "Prenom Nom",
                "key": "JIRAUSER12345",
            },
        ],
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert client.gets == [
        ("/rest/api/2/user", {"username": "nom.prenom"}),
    ]
    assert worklogs[0].author == "Prenom Nom"


def test_search_team_worklogs_resolves_account_id_author_from_team_member() -> None:
    client = FakeTempoTeamWorklogClient(
        (
            [
                {
                    "member": {
                        "displayName": "Alice Dupont",
                        "accountId": "account-12345",
                    },
                },
            ],
            {
                "results": [
                    {
                        "originTaskId": 10001,
                        "timeSpentSeconds": 1800,
                        "startDate": "2026-05-10",
                        "worker": {"accountId": "account-12345"},
                        "issue": {"id": 10001, "key": "ABC-1"},
                    },
                    {
                        "originTaskId": 10002,
                        "timeSpentSeconds": 900,
                        "startDate": "2026-05-10",
                        "worker": {"accountId": "other-account"},
                        "issue": {"id": 10002, "key": "ABC-2"},
                    },
                ]
            },
        )
    )

    worklogs = client.search_team_worklogs(
        team_id=42,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert [worklog.issue_key for worklog in worklogs] == ["ABC-1"]
    assert worklogs[0].author == "Alice Dupont"
    assert worklogs[0].author_key == "account-12345"
    assert worklogs[0].author_identity.display_name == "Alice Dupont"
    assert worklogs[0].author_identity.account_id == "account-12345"


def test_search_worker_worklogs_posts_workers_and_dates() -> None:
    client = FakeTempoTeamWorklogClient(
        {
            "results": [
                {
                    "originTaskId": 10001,
                    "timeSpentSeconds": 1800,
                    "startDate": "2026-05-10",
                    "worker": {"name": "nom.prenom"},
                    "issue": {"id": 10001, "key": "ABC-1"},
                },
            ]
        },
        jira_user_payloads=[
            {
                "name": "nom.prenom",
                "displayName": "Prenom Nom",
                "key": "JIRAUSER12345",
            },
        ],
    )

    worklogs = client.search_worker_worklogs(
        worker_keys=("nom.prenom",),
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert client.posts == [
        (
            "/rest/tempo-timesheets/4/worklogs/search",
            {
                "from": "2026-05-01",
                "to": "2026-05-15",
                "worker": ["nom.prenom"],
            },
        ),
    ]
    assert worklogs[0].author == "Prenom Nom"
    assert worklogs[0].issue_key == "ABC-1"


def test_search_worker_worklogs_dedupes_workers() -> None:
    client = FakeTempoTeamWorklogClient({"results": []})

    worklogs = client.search_worker_worklogs(
        worker_keys=(" nom.prenom ", "NOM.PRENOM", "", "autre.user"),
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert worklogs == []
    assert client.posts == [
        (
            "/rest/tempo-timesheets/4/worklogs/search",
            {
                "from": "2026-05-01",
                "to": "2026-05-15",
                "worker": ["nom.prenom", "autre.user"],
            },
        ),
    ]


def test_search_worker_worklogs_skips_empty_worker_list() -> None:
    client = FakeTempoTeamWorklogClient({"results": []})

    worklogs = client.search_worker_worklogs(
        worker_keys=("", " "),
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 15),
    )

    assert worklogs == []
    assert client.posts == []


@pytest.mark.parametrize("wrapper", [None, "results", "values", "teams"])
def test_team_payload_variants_ignore_non_object_entries(wrapper):
    items = [{"id": 42}, None, "unexpected"]
    client = FakeTempoTeamWorklogClient(items if wrapper is None else {wrapper: items})
    assert [(team.id, team.name) for team in client.list_teams()] == [(42, "Team 42")]


@pytest.mark.parametrize("payload", [None, "invalid", 123, {}, {"results": "invalid"}])
def test_unsupported_team_payload_is_empty(payload):
    assert FakeTempoTeamWorklogClient(payload).list_teams() == []


@pytest.mark.parametrize("date_field", ["startDate", "date", "started"])
def test_worker_worklogs_accept_date_aliases_and_timestamp(date_field):
    client = FakeTempoTeamWorklogClient(
        [
            {
                "issueKey": "ABC-1",
                "timeSpentSeconds": "60",
                date_field: "2026-05-01T23:59:59+0200",
                "author": "alice",
            }
        ]
    )
    (worklog,) = client.search_worker_worklogs(
        ("alice",), date(2026, 5, 1), date(2026, 5, 2)
    )
    assert worklog.issue_id == worklog.issue_key == "ABC-1"
    assert worklog.time_spent_seconds == 60
    assert worklog.start_date == date(2026, 5, 1)
    assert worklog.author_key == "alice"


@pytest.mark.parametrize("date_value", [None, "not-a-date"])
def test_worker_worklogs_reject_missing_or_invalid_date(date_value):
    client = FakeTempoTeamWorklogClient(
        [{"issueKey": "ABC-1", "timeSpentSeconds": 60, "startDate": date_value}]
    )
    with pytest.raises(ValueError):
        client.search_worker_worklogs(("alice",), date(2026, 5, 1), date(2026, 5, 2))


def test_jira_user_resolution_does_not_hide_non_404_http_errors(monkeypatch):
    client = TempoTeamWorklogClient("https://jira.example.test", "token")
    response = requests.Response()
    response.status_code = 503

    def fail(*args, **kwargs):
        raise requests.HTTPError(response=response)

    monkeypatch.setattr(client, "_get", fail)
    with pytest.raises(requests.HTTPError) as error:
        client.resolve_workers(("alice",))
    assert error.value.response.status_code == 503


def test_team_without_identifiers_preserves_unresolved_worklogs():
    client = FakeTempoTeamWorklogClient(
        (
            [{"member": {}}],
            [
                {
                    "issueKey": "ABC-1",
                    "timeSpentSeconds": 60,
                    "date": "2026-05-01",
                    "worker": "alice",
                }
            ],
        )
    )
    worklogs = client.search_team_worklogs(42, date(2026, 5, 1), date(2026, 5, 2))
    assert [worklog.issue_key for worklog in worklogs] == ["ABC-1"]


def test_empty_jira_identity_does_not_mask_cached_username_fallback():
    client = FakeTempoTeamWorklogClient(
        [],
        jira_user_payloads=[
            {},
            {"name": "alice", "displayName": "Alice Martin"},
        ],
    )
    first = client.resolve_workers(("alice",))
    second = client.resolve_workers(("alice",))
    assert [member.display_name for member in first] == ["Alice Martin"]
    assert second == first
    assert client.gets == [
        ("/rest/api/2/user", {"key": "alice"}),
        ("/rest/api/2/user", {"username": "alice"}),
    ]


def test_scalar_team_members_resolve_without_discarding_unknown_entries():
    client = FakeTempoTeamWorklogClient(
        [{"member": "alice"}, {"member": 42}],
        jira_user_payloads=[{"name": "alice", "displayName": "Alice Martin"}],
    )
    members = client.list_team_members(42)
    assert [member.display_name for member in members] == ["Alice Martin", None]
    assert members[0].key == "alice"
    assert members[1].identifiers == frozenset()


@pytest.mark.parametrize("worker, expected", [(42, None), ({"name": "bob"}, "bob")])
def test_unresolved_worklog_author_keeps_duration_and_original_identity(
    worker, expected
):
    client = FakeTempoTeamWorklogClient(
        [
            {
                "issueKey": "ABC-1",
                "timeSpentSeconds": 60,
                "startDate": "2026-05-01",
                "worker": worker,
            }
        ]
    )
    (worklog,) = client.search_worker_worklogs(
        ("alice",), date(2026, 5, 1), date(2026, 5, 2)
    )
    assert worklog.author == expected
    assert worklog.time_spent_seconds == 60
    assert worklog.issue_key == "ABC-1"
