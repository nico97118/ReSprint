from typing import Any

from resprint.helpers.tempo import TempoDataCenterClient


class FakeTempoDataCenterClient(TempoDataCenterClient):
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def _get(self, path: str) -> object:
        self.calls.append(path)
        return self.payload


def test_list_teams_parses_tempo_team_payload_list() -> None:
    client = FakeTempoDataCenterClient(
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
    client = FakeTempoDataCenterClient(
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
    client = FakeTempoDataCenterClient(payload)

    teams = client.list_teams()

    assert [(team.id, team.name) for team in teams] == [(10, "Equipe ABC")]
