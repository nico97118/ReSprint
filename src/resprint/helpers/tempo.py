from __future__ import annotations

from datetime import date
from typing import Any

import requests

from resprint.models import TempoTeam, TempoWorklog


class TempoClient:
    def __init__(self, api_token: str, base_url: str = "https://api.tempo.io") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_token}",
            }
        )

    def get_issue_worklogs(
        self,
        issue_id: str,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        params: dict[str, Any] = {
            "issueId": issue_id,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "limit": 100,
        }
        worklogs: list[TempoWorklog] = []

        url: str | None = f"{self.base_url}/4/worklogs"
        while url:
            response = self.session.get(
                url,
                params=params if "?" not in url else None,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            worklogs.extend(
                _parse_worklog(item, issue_id) for item in payload.get("results", [])
            )
            url = (payload.get("metadata") or {}).get("next")
            params = {}

        return worklogs


class TempoDataCenterClient:
    def __init__(
        self,
        base_url: str,
        username: str | None,
        api_token: str,
        auth_method: str = "basic",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if auth_method == "basic":
            if not username:
                raise ValueError("Un username Jira est requis avec l'auth basic")
            self.session.auth = (username, api_token)
        elif auth_method == "bearer":
            self.session.headers.update({"Authorization": f"Bearer {api_token}"})
        else:
            raise ValueError("auth_method doit valoir 'basic' ou 'bearer'")

    def list_teams(self) -> list[TempoTeam]:
        payload = self._get("/rest/tempo-teams/2/team")
        return [_parse_team(item) for item in _payload_items(payload)]

    def _get(self, path: str) -> object:
        response = self.session.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()


def _parse_worklog(raw: dict[str, Any], fallback_issue_id: str) -> TempoWorklog:
    issue = raw.get("issue") or {}
    author = raw.get("author") or {}
    return TempoWorklog(
        issue_id=str(issue.get("id") or fallback_issue_id),
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=date.fromisoformat(raw["startDate"]),
        author=author.get("displayName") or author.get("accountId"),
        description=raw.get("description"),
    )


def _payload_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "values", "teams"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _parse_team(raw: dict[str, Any]) -> TempoTeam:
    team_id = raw.get("id") or raw.get("teamId")
    name = raw.get("name") or raw.get("teamName") or f"Team {team_id}"
    return TempoTeam(id=int(team_id), name=str(name))
