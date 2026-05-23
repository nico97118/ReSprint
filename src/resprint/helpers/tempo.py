from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import requests

from resprint.models import TempoTeam, TempoTeamMember, TempoWorklog


class TempoIssueWorklogClient:
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
                _parse_issue_worklog(item, issue_id)
                for item in payload.get("results", [])
            )
            url = (payload.get("metadata") or {}).get("next")
            params = {}

        return worklogs


class TempoTeamWorklogClient:
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

    def list_team_members(self, team_id: int) -> list[TempoTeamMember]:
        payload = self._post(
            "/rest/tempo-teams/2/team/members",
            {
                "ids": [str(team_id)],
                "onlyActive": True,
            },
        )
        return [_parse_team_member(item) for item in _payload_items(payload)]

    def search_team_worklogs(
        self,
        team_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        team_members = self.list_team_members(team_id)
        team_member_identifiers = _team_member_identifiers(team_members)
        member_display_by_identifier = _member_display_by_identifier(team_members)
        payload = self._post(
            "/rest/tempo-timesheets/4/worklogs/search",
            {
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "teamId": [team_id],
            },
        )
        worklogs = [_parse_team_worklog(item) for item in _payload_items(payload)]
        if not team_member_identifiers:
            return worklogs
        team_worklogs = []
        for worklog in worklogs:
            author_identifiers = _worklog_author_identifiers(worklog)
            if not author_identifiers & team_member_identifiers:
                continue
            team_worklogs.append(
                _with_resolved_author(worklog, member_display_by_identifier)
            )
        return team_worklogs

    def _get(self, path: str) -> object:
        response = self.session.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> object:
        response = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def _parse_issue_worklog(raw: dict[str, Any], fallback_issue_id: str) -> TempoWorklog:
    issue = raw.get("issue") or {}
    author = raw.get("author") or {}
    return TempoWorklog(
        issue_id=str(issue.get("id") or fallback_issue_id),
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=date.fromisoformat(raw["startDate"]),
        issue_key=issue.get("key"),
        author=author.get("displayName") or author.get("accountId"),
        author_key=author.get("accountId"),
        description=raw.get("description"),
    )


def _parse_team_worklog(raw: dict[str, Any]) -> TempoWorklog:
    issue = raw.get("issue") or {}
    worker = raw.get("worker") or raw.get("author") or {}
    issue_id = raw.get("originTaskId") or issue.get("id") or issue.get("issueId")
    issue_key = issue.get("key") or raw.get("issueKey")
    return TempoWorklog(
        issue_id=str(issue_id or issue_key or ""),
        issue_key=str(issue_key) if issue_key else None,
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=_parse_worklog_date(raw),
        author=_parse_worker(worker),
        author_key=_parse_worker_key(worker),
        description=raw.get("comment") or raw.get("description"),
    )


def _parse_worklog_date(raw: dict[str, Any]) -> date:
    value = raw.get("startDate") or raw.get("date") or raw.get("started")
    if not value:
        raise ValueError("Tempo worklog date is missing")
    return date.fromisoformat(str(value)[:10])


def _parse_worker(worker: Any) -> str | None:
    if isinstance(worker, str):
        return worker
    if not isinstance(worker, dict):
        return None
    return (
        worker.get("displayName")
        or worker.get("name")
        or worker.get("key")
        or worker.get("accountId")
    )


def _parse_worker_key(worker: Any) -> str | None:
    if isinstance(worker, str):
        return worker
    if not isinstance(worker, dict):
        return None
    return worker.get("key") or worker.get("name") or worker.get("accountId")


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


def _parse_team_member(raw: dict[str, Any]) -> TempoTeamMember:
    member = raw.get("member") or raw.get("user") or raw
    if not isinstance(member, dict):
        return TempoTeamMember(name=str(member))
    return TempoTeamMember(
        name=member.get("name") or member.get("username"),
        display_name=member.get("displayName") or member.get("fullName"),
        key=member.get("key") or member.get("userKey") or member.get("accountId"),
    )


def _team_member_identifiers(members: list[TempoTeamMember]) -> frozenset[str]:
    identifiers = set()
    for member in members:
        identifiers.update(member.identifiers)
    return frozenset(identifiers)


def _member_display_by_identifier(
    members: list[TempoTeamMember],
) -> dict[str, str]:
    labels = {}
    for member in members:
        label = member.display_name or member.name or member.key
        if not label:
            continue
        for identifier in member.identifiers:
            labels[identifier] = label
    return labels


def _worklog_author_identifiers(worklog: TempoWorklog) -> frozenset[str]:
    return frozenset(
        value.casefold() for value in (worklog.author, worklog.author_key) if value
    )


def _with_resolved_author(
    worklog: TempoWorklog,
    member_display_by_identifier: dict[str, str],
) -> TempoWorklog:
    for identifier in _worklog_author_identifiers(worklog):
        display = member_display_by_identifier.get(identifier)
        if display:
            return replace(worklog, author=display)
    return worklog
