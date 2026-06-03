from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import requests

from resprint.helpers.user_identity import (
    user_identity_from_mapping,
    user_identity_from_value,
    user_key,
    user_label,
)
from resprint.logging import get_logger
from resprint.models import TempoTeam, TempoTeamMember, TempoWorklog, UserIdentity

logger = get_logger(__name__)


class TempoTeamWorklogClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        ca_bundle: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        logger.debug(
            "Initializing Tempo team worklog client base_url=%s",
            self.base_url,
        )
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}
        )
        self.session.verify = ca_bundle or True
        self._jira_user_cache: dict[str, UserIdentity | None] = {}

    def list_teams(self) -> list[TempoTeam]:
        logger.info("Listing Tempo teams")
        payload = self._get("/rest/tempo-teams/2/team")
        teams = [_parse_team(item) for item in _payload_items(payload)]
        logger.info("Loaded %s Tempo teams", len(teams))
        return teams

    def list_team_members(self, team_id: int) -> list[TempoTeamMember]:
        logger.info("Listing Tempo team members for team %s", team_id)
        payload = self._post(
            "/rest/tempo-teams/2/team/members",
            {
                "ids": [str(team_id)],
                "onlyActive": True,
            },
        )
        members = [_parse_team_member(item) for item in _payload_items(payload)]
        members = self._resolve_jira_team_members(members)
        logger.info("Loaded %s Tempo team members for team %s", len(members), team_id)
        return members

    def search_team_worklogs(
        self,
        team_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        logger.info(
            "Searching Tempo team worklogs team=%s period=%s..%s",
            team_id,
            start_date,
            end_date,
        )
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
            logger.warning(
                "Tempo team %s has no resolvable member identifiers; "
                "keeping all worklogs",
                team_id,
            )
            return worklogs
        team_worklogs = []
        for worklog in worklogs:
            author_identifiers = _worklog_author_identifiers(worklog)
            if not author_identifiers & team_member_identifiers:
                logger.debug(
                    "Ignoring Tempo worklog for non-team author issue=%s",
                    worklog.issue_key,
                )
                continue
            team_worklogs.append(
                _with_resolved_author(worklog, member_display_by_identifier)
            )
        logger.info(
            "Tempo team worklog search returned %s worklogs "
            "after filtering %s raw worklogs",
            len(team_worklogs),
            len(worklogs),
        )
        return team_worklogs

    def _resolve_jira_team_members(
        self,
        members: list[TempoTeamMember],
    ) -> list[TempoTeamMember]:
        resolved_members = []
        for member in members:
            jira_identity = self._resolve_jira_user_identity(member.identity)
            if jira_identity is None:
                resolved_members.append(member)
                continue
            resolved_members.append(
                replace(
                    member,
                    identity=_merge_tempo_jira_identity(
                        member.identity,
                        jira_identity,
                    ),
                )
            )
        return resolved_members

    def _resolve_jira_user_identity(
        self,
        identity: UserIdentity,
    ) -> UserIdentity | None:
        for params in _jira_user_lookup_params(identity):
            cache_key = _jira_user_cache_key(params)
            jira_user_cache = getattr(self, "_jira_user_cache", None)
            if jira_user_cache is None:
                jira_user_cache = {}
                self._jira_user_cache = jira_user_cache
            if cache_key in jira_user_cache:
                cached_identity = jira_user_cache[cache_key]
                if cached_identity is not None:
                    return cached_identity
                continue
            try:
                payload = self._get("/rest/api/2/user", params=params)
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 404:
                    logger.debug("Jira user not found for params=%s", params)
                    jira_user_cache[cache_key] = None
                    continue
                raise
            resolved_identity = user_identity_from_mapping(payload)
            jira_user_cache[cache_key] = resolved_identity
            if resolved_identity.label:
                return resolved_identity
        return None

    def _get(self, path: str, params: dict[str, str] | None = None) -> object:
        logger.debug("Tempo GET %s params=%s", path, params)
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> object:
        logger.debug("Tempo POST %s payload_keys=%s", path, sorted(payload))
        response = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def _parse_team_worklog(raw: dict[str, Any]) -> TempoWorklog:
    issue = raw.get("issue") or {}
    worker = user_identity_from_value(raw.get("worker") or raw.get("author") or {})
    issue_id = raw.get("originTaskId") or issue.get("id") or issue.get("issueId")
    issue_key = issue.get("key") or raw.get("issueKey")
    return TempoWorklog(
        issue_id=str(issue_id or issue_key or ""),
        issue_key=str(issue_key) if issue_key else None,
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=_parse_worklog_date(raw),
        author=user_label(worker),
        author_key=user_key(worker),
        author_identity=worker,
        description=raw.get("comment") or raw.get("description"),
    )


def _jira_user_lookup_params(identity: UserIdentity) -> tuple[dict[str, str], ...]:
    lookup_values = (
        ("key", identity.key),
        ("username", identity.name),
        ("username", identity.display_name),
    )
    params = []
    seen = set()
    for param_name, value in lookup_values:
        if not value:
            continue
        cache_key = f"{param_name}:{value.casefold()}"
        if cache_key in seen:
            continue
        seen.add(cache_key)
        params.append({param_name: value})
    return tuple(params)


def _merge_tempo_jira_identity(
    tempo_identity: UserIdentity,
    jira_identity: UserIdentity,
) -> UserIdentity:
    return UserIdentity(
        name=tempo_identity.name or tempo_identity.display_name or jira_identity.name,
        display_name=jira_identity.display_name or tempo_identity.display_name,
        key=tempo_identity.key or jira_identity.key,
        account_id=tempo_identity.account_id or jira_identity.account_id,
    )


def _jira_user_cache_key(params: dict[str, str]) -> str:
    return "&".join(
        f"{key}={value.casefold()}" for key, value in sorted(params.items())
    )


def _parse_worklog_date(raw: dict[str, Any]) -> date:
    value = raw.get("startDate") or raw.get("date") or raw.get("started")
    if not value:
        logger.error("Tempo worklog date is missing")
        raise ValueError("Tempo worklog date is missing")
    return date.fromisoformat(str(value)[:10])


def _payload_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        logger.warning(
            "Ignoring unexpected Tempo payload type: %s", type(payload).__name__
        )
        return []
    for key in ("results", "values", "teams"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    logger.warning("Tempo payload contains no supported item collection")
    return []


def _parse_team(raw: dict[str, Any]) -> TempoTeam:
    team_id = raw.get("id") or raw.get("teamId")
    name = raw.get("name") or raw.get("teamName") or f"Team {team_id}"
    return TempoTeam(id=int(team_id), name=str(name))


def _parse_team_member(raw: dict[str, Any]) -> TempoTeamMember:
    member = raw.get("member") or raw.get("user") or raw
    if not isinstance(member, dict):
        return TempoTeamMember(identity=user_identity_from_value(member))
    return TempoTeamMember(identity=user_identity_from_mapping(member))


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
        label = member.identity.label
        if not label:
            continue
        for identifier in member.identifiers:
            labels[identifier] = label
    return labels


def _worklog_author_identifiers(worklog: TempoWorklog) -> frozenset[str]:
    identifiers = set(worklog.author_identity.identifiers)
    identifiers.update(
        value.casefold() for value in (worklog.author, worklog.author_key) if value
    )
    return frozenset(identifiers)


def _with_resolved_author(
    worklog: TempoWorklog,
    member_display_by_identifier: dict[str, str],
) -> TempoWorklog:
    for identifier in _worklog_author_identifiers(worklog):
        display = member_display_by_identifier.get(identifier)
        if display:
            return replace(
                worklog,
                author=display,
                author_identity=replace(worklog.author_identity, display_name=display),
            )
    return worklog
