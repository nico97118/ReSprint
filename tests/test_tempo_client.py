from datetime import date
from typing import Any

from resprint.helpers.tempo import TempoTeamWorklogClient


class FakeTempoTeamWorklogClient(TempoTeamWorklogClient):
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.post_payloads = list(payload) if isinstance(payload, tuple) else None
        self.calls: list[str] = []
        self.posts: list[tuple[str, dict[str, object]]] = []

    def _get(self, path: str) -> object:
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
    assert client.calls == ["/rest/tempo-teams/2/team"]


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
