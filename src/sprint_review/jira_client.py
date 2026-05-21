from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import requests

from sprint_review.models import Board, Issue, JiraComment, Sprint, TempoWorklog


class JiraClient:
    def __init__(
        self,
        base_url: str,
        username: str | None,
        api_token: str,
        epic_field: str | None = None,
        auth_method: str = "basic",
        rest_api_version: str = "2",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.epic_field = epic_field
        if rest_api_version not in {"2", "3"}:
            raise ValueError("rest_api_version doit valoir '2' ou '3'")
        self.rest_api_base = f"/rest/api/{rest_api_version}"
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

    def get_sprint(self, sprint_id: int) -> Sprint:
        payload = self._get(f"/rest/agile/1.0/sprint/{sprint_id}")
        return _parse_sprint(payload)

    def list_boards(
        self,
        project_key: str,
        board_type: str | None = None,
    ) -> list[Board]:
        boards: list[Board] = []
        start_at = 0
        max_results = 50

        while True:
            params: dict[str, Any] = {
                "projectKeyOrId": project_key,
                "startAt": start_at,
                "maxResults": max_results,
            }
            if board_type:
                params["type"] = board_type
            payload = self._get(
                "/rest/agile/1.0/board",
                params=params,
            )
            batch = payload.get("values", [])
            boards.extend(_parse_board(item) for item in batch)
            start_at += len(batch)
            if payload.get("isLast", True) or not batch:
                return boards

    def list_board_sprints(
        self,
        board_id: int,
        states: tuple[str, ...] = ("active", "closed"),
    ) -> list[Sprint]:
        sprints: list[Sprint] = []
        start_at = 0
        max_results = 50

        while True:
            payload = self._get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={
                    "state": ",".join(states),
                    "startAt": start_at,
                    "maxResults": max_results,
                },
            )
            batch = payload.get("values", [])
            sprints.extend(_parse_sprint(item) for item in batch)
            start_at += len(batch)
            if payload.get("isLast", True) or not batch:
                return sprints

    def get_sprint_issues(
        self,
        sprint_id: int,
        board_id: int | None = None,
    ) -> list[Issue]:
        if board_id is not None:
            path = f"/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue"
            issue_keys = self._paged_agile_issue_keys(path)
            return self.get_issues_by_keys(issue_keys)

        jql = f"sprint = {sprint_id}"
        return self.search_issues(jql)

    def get_issues_by_keys(self, issue_keys: list[str]) -> list[Issue]:
        if not issue_keys:
            return []

        issues_by_key: dict[str, Issue] = {}
        for key_batch in _chunks(issue_keys, 100):
            quoted_keys = ", ".join(key_batch)
            for issue in self.search_issues(f"key in ({quoted_keys})"):
                issues_by_key[issue.key] = issue

        return [issues_by_key[key] for key in issue_keys if key in issues_by_key]

    def enrich_epic_summaries(self, issues: list[Issue]) -> list[Issue]:
        epic_keys = sorted(
            {issue.epic for issue in issues if _looks_like_issue_key(issue.epic)}
        )
        if not epic_keys:
            return issues

        epics_by_key = {
            issue.key: issue for issue in self.get_issues_by_keys(epic_keys)
        }
        enriched_issues = []
        for issue in issues:
            epic = epics_by_key.get(issue.epic or "")
            if epic and issue.epic:
                enriched_issues.append(
                    replace(issue, epic=_format_epic_parts(issue.epic, epic.summary))
                )
            else:
                enriched_issues.append(issue)
        return enriched_issues

    def search_issues(self, jql: str) -> list[Issue]:
        issues: list[Issue] = []
        start_at = 0
        max_results = 100
        fields = self._issue_fields()

        while True:
            payload = self._get(
                f"{self.rest_api_base}/search",
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": ",".join(fields),
                },
            )
            batch = payload.get("issues", [])
            issues.extend(_parse_issue(item, self.epic_field) for item in batch)
            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                return issues

    def get_issue_worklogs(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[TempoWorklog]:
        return [
            worklog
            for worklog in self.get_all_issue_worklogs(issue_id_or_key)
            if sprint_start <= worklog.start_date <= sprint_end
        ]

    def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
        worklogs: list[TempoWorklog] = []
        start_at = 0
        max_results = 100

        while True:
            payload = self._get(
                f"{self.rest_api_base}/issue/{issue_id_or_key}/worklog",
                params={
                    "startAt": start_at,
                    "maxResults": max_results,
                },
            )
            batch = payload.get("worklogs", [])
            for raw_worklog in batch:
                worklogs.append(_parse_jira_worklog(raw_worklog))

            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                return worklogs

    def get_issue_comments(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[JiraComment]:
        comments: list[JiraComment] = []
        start_at = 0
        max_results = 100

        while True:
            payload = self._get(
                f"{self.rest_api_base}/issue/{issue_id_or_key}/comment",
                params={
                    "startAt": start_at,
                    "maxResults": max_results,
                    "orderBy": "created",
                },
            )
            batch = payload.get("comments", [])
            for raw_comment in batch:
                comment = _parse_comment(raw_comment)
                created_date = comment.created_at.date()
                if sprint_start <= created_date <= sprint_end:
                    comments.append(comment)

            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                return comments

    def _paged_agile_issue_keys(self, path: str) -> list[str]:
        issue_keys: list[str] = []
        start_at = 0
        max_results = 100

        while True:
            payload = self._get(
                path,
                params={
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": ",".join(self._issue_fields()),
                },
            )
            batch = payload.get("issues", [])
            issue_keys.extend(item["key"] for item in batch)
            if payload.get("isLast", True) or not batch:
                return issue_keys
            start_at += len(batch)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _issue_fields(self) -> list[str]:
        fields = [
            "summary",
            "status",
            "assignee",
            "issuetype",
            "priority",
            "fixVersions",
            "parent",
            "timetracking",
            "timeoriginalestimate",
            "timeestimate",
        ]
        if self.epic_field:
            fields.append(self.epic_field)
        return fields


def _parse_issue(raw: dict[str, Any], epic_field: str | None = None) -> Issue:
    fields = raw.get("fields") or {}
    status = fields.get("status") or {}
    status_category = status.get("statusCategory") or {}
    assignee = fields.get("assignee") or {}
    issue_type = fields.get("issuetype") or {}
    priority = fields.get("priority") or {}
    timetracking = fields.get("timetracking") or {}

    return Issue(
        id=str(raw["id"]),
        key=raw["key"],
        summary=fields.get("summary", ""),
        status=status.get("name", ""),
        status_category=status_category.get("key", status_category.get("name", "")),
        assignee=assignee.get("displayName") if assignee else None,
        issue_type=issue_type.get("name") if issue_type else None,
        epic=_extract_epic(fields, epic_field),
        priority=priority.get("name") if priority else None,
        fix_versions=_extract_fix_versions(fields.get("fixVersions")),
        original_estimate_seconds=_extract_estimate_seconds(
            timetracking,
            "originalEstimateSeconds",
            fields.get("timeoriginalestimate"),
        ),
        remaining_estimate_seconds=_extract_estimate_seconds(
            timetracking,
            "remainingEstimateSeconds",
            fields.get("timeestimate"),
        ),
    )


def _parse_board(raw: dict[str, Any]) -> Board:
    return Board(
        id=int(raw["id"]),
        name=raw.get("name", f"Board {raw['id']}"),
        type=raw.get("type", ""),
    )


def _parse_sprint(raw: dict[str, Any]) -> Sprint:
    sprint_id = int(raw["id"])
    return Sprint(
        id=sprint_id,
        name=raw.get("name", f"Sprint {sprint_id}"),
        start_date=_parse_jira_date(raw["startDate"]),
        end_date=_parse_jira_date(raw["endDate"]),
        state=raw.get("state"),
    )


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _parse_comment(raw: dict[str, Any]) -> JiraComment:
    author = raw.get("author") or {}
    return JiraComment(
        id=str(raw["id"]),
        issue_id=str(raw.get("issueId", "")),
        author=author.get("displayName") if author else None,
        created_at=_parse_jira_datetime(raw["created"]),
        body=_plain_text_from_adf(raw.get("body", "")),
    )


def _parse_jira_worklog(raw: dict[str, Any]) -> TempoWorklog:
    author = raw.get("author") or {}
    issue_id = raw.get("issueId", "")
    started = _parse_jira_datetime(raw["started"])
    return TempoWorklog(
        issue_id=str(issue_id),
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=started.date(),
        author=author.get("displayName")
        or author.get("name")
        or author.get("accountId"),
        description=_plain_text_from_adf(raw.get("comment", "")),
    )


def _extract_fix_versions(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    versions = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            versions.append(str(item["name"]))
        elif isinstance(item, str):
            versions.append(item)
    return tuple(versions)


def _extract_epic(fields: dict[str, Any], epic_field: str | None = None) -> str | None:
    if epic_field:
        epic = _format_epic_value(fields.get(epic_field))
        if epic:
            return epic

    parent = fields.get("parent") or {}
    if not isinstance(parent, dict):
        return None

    parent_fields = parent.get("fields") or {}
    issue_type = parent_fields.get("issuetype") or {}
    parent_key = parent.get("key")
    parent_summary = parent_fields.get("summary")

    if issue_type.get("name") == "Epic" and parent_key:
        return _format_epic_parts(parent_key, parent_summary)
    if parent_key and parent_summary:
        return _format_epic_parts(parent_key, parent_summary)
    if parent_key:
        return str(parent_key)
    return None


def _format_epic_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if not isinstance(value, dict):
        return None

    key = value.get("key")
    summary = (value.get("fields") or {}).get("summary") or value.get("name")
    if key:
        return _format_epic_parts(str(key), summary)
    if summary:
        return str(summary)
    return None


def _format_epic_parts(key: str, summary: Any) -> str:
    if summary:
        return f"{key} - {summary}"
    return key


def _looks_like_issue_key(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", value))


def _extract_estimate_seconds(
    timetracking: dict[str, Any],
    key: str,
    fallback: Any,
) -> int | None:
    value = timetracking.get(key, fallback)
    if value is None:
        return None
    return int(value)


def _parse_jira_date(value: str) -> date:
    return _parse_jira_datetime(value).date()


def _parse_jira_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _plain_text_from_adf(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""

    fragments: list[str] = []
    _collect_adf_text(value, fragments)
    return " ".join(" ".join(fragments).split())


def _collect_adf_text(node: Any, fragments: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_adf_text(item, fragments)
        return

    if not isinstance(node, dict):
        return

    text = node.get("text")
    if isinstance(text, str):
        fragments.append(text)

    content = node.get("content")
    if isinstance(content, list):
        _collect_adf_text(content, fragments)
