from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import requests

from resprint.config import DEFAULT_IGNORED_CHANGELOG_FIELDS
from resprint.helpers.user_identity import user_identity_from_mapping, user_label
from resprint.logging import get_logger
from resprint.models import (
    Board,
    Issue,
    JiraComment,
    JiraIssueChange,
    Sprint,
    TempoWorklog,
)

logger = get_logger(__name__)


class JiraClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        ca_bundle: str | None = None,
        parent_field: str | None = None,
        rest_api_version: str = "2",
        ignored_changelog_fields: frozenset[str] = DEFAULT_IGNORED_CHANGELOG_FIELDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.parent_field = parent_field
        self.ignored_changelog_fields = ignored_changelog_fields
        logger.debug(
            "Initializing Jira client base_url=%s rest_api=%s parent_field=%s",
            self.base_url,
            rest_api_version,
            bool(parent_field),
        )
        if rest_api_version not in {"2", "3"}:
            logger.error("Unsupported Jira REST API version: %s", rest_api_version)
            raise ValueError("rest_api_version must be '2' or '3'")
        self.rest_api_base = f"/rest/api/{rest_api_version}"
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}
        )
        self.session.verify = ca_bundle or True
        self._parent_summary_cache: dict[str, str] = {}

    def get_sprint(self, sprint_id: int) -> Sprint:
        logger.info("Fetching Jira sprint %s", sprint_id)
        payload = self._get(f"/rest/agile/1.0/sprint/{sprint_id}")
        sprint = _parse_sprint(payload)
        logger.debug("Fetched sprint %s (%s)", sprint.id, sprint.name)
        return sprint

    def list_boards(
        self,
        project_key: str,
        board_type: str | None = None,
    ) -> list[Board]:
        logger.info("Listing Jira boards for project %s", project_key)
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
            logger.debug(
                "Fetched Jira boards page start_at=%s count=%s",
                start_at,
                len(batch),
            )
            boards.extend(_parse_board(item) for item in batch)
            start_at += len(batch)
            if payload.get("isLast", True) or not batch:
                logger.info("Loaded %s Jira boards", len(boards))
                return boards

    def list_board_sprints(
        self,
        board_id: int,
        states: tuple[str, ...] = ("active", "closed"),
    ) -> list[Sprint]:
        logger.info("Listing Jira sprints for board %s", board_id)
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
            logger.debug(
                "Fetched Jira sprints page board=%s start_at=%s count=%s",
                board_id,
                start_at,
                len(batch),
            )
            sprints.extend(_parse_sprint(item) for item in batch)
            start_at += len(batch)
            if payload.get("isLast", True) or not batch:
                logger.info(
                    "Loaded %s Jira sprints for board %s",
                    len(sprints),
                    board_id,
                )
                return sprints

    def get_sprint_issues(
        self,
        sprint_id: int,
        board_id: int | None = None,
        include_activity: bool = False,
    ) -> list[Issue]:
        logger.info(
            "Fetching issues for sprint=%s board=%s",
            sprint_id,
            board_id,
        )
        return self.search_issues(
            f"sprint = {sprint_id}",
            include_activity=include_activity,
        )

    def get_issues_by_keys(
        self,
        issue_keys: list[str],
        include_activity: bool = False,
    ) -> list[Issue]:
        if not issue_keys:
            logger.debug("No issue keys provided")
            return []

        logger.info("Fetching %s Jira issues by key", len(issue_keys))
        issues_by_key: dict[str, Issue] = {}
        for key_batch in _chunks(issue_keys, 100):
            logger.debug("Fetching Jira issue key batch of size %s", len(key_batch))
            quoted_keys = ", ".join(key_batch)
            for issue in self.search_issues(
                f"key in ({quoted_keys})",
                include_activity=include_activity,
            ):
                issues_by_key[issue.key] = issue

        missing_keys = [key for key in issue_keys if key not in issues_by_key]
        if missing_keys:
            logger.warning(
                "Jira returned no details for %s requested issues",
                len(missing_keys),
            )
        return [issues_by_key[key] for key in issue_keys if key in issues_by_key]

    def enrich_parent_summaries(self, issues: list[Issue]) -> list[Issue]:
        parent_summary_cache = getattr(self, "_parent_summary_cache", None)
        if parent_summary_cache is None:
            parent_summary_cache = {}
            self._parent_summary_cache = parent_summary_cache
        parent_keys = sorted(
            {issue.parent for issue in issues if _looks_like_issue_key(issue.parent)}
        )
        if not parent_keys:
            logger.debug("No parent issue summaries to enrich")
            return issues

        missing_parent_keys = [
            parent_key
            for parent_key in parent_keys
            if parent_key not in parent_summary_cache
        ]
        if missing_parent_keys:
            logger.info("Enriching %s parent issue summaries", len(parent_keys))
            parent_issues = self.get_issues_by_keys(missing_parent_keys)
            parent_summary_cache.update(
                {issue.key: issue.summary for issue in parent_issues if issue.summary}
            )
        else:
            logger.debug("Parent issue summaries already cached")

        parent_summary_by_key = {
            parent_key: parent_summary_cache[parent_key]
            for parent_key in parent_keys
            if parent_key in parent_summary_cache
        }
        enriched_issues = []
        for issue in issues:
            parent_summary = parent_summary_by_key.get(issue.parent or "")
            if parent_summary and issue.parent:
                enriched_issues.append(
                    replace(
                        issue,
                        parent=_format_parent_parts(issue.parent, parent_summary),
                    )
                )
            else:
                if issue.parent and _looks_like_issue_key(issue.parent):
                    logger.warning("Parent summary missing for %s", issue.parent)
                enriched_issues.append(issue)
        return enriched_issues

    def search_issues(
        self,
        jql: str,
        include_activity: bool = False,
    ) -> list[Issue]:
        logger.info("Searching Jira issues")
        logger.debug("Jira search JQL: %s", jql)
        issues: list[Issue] = []
        start_at = 0
        max_results = 100
        fields = self._issue_fields()
        ignored_changelog_fields = getattr(
            self,
            "ignored_changelog_fields",
            DEFAULT_IGNORED_CHANGELOG_FIELDS,
        )
        if include_activity:
            fields.append("comment")

        while True:
            params: dict[str, Any] = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ",".join(fields),
            }
            if include_activity:
                params["expand"] = "changelog"
            payload = self._get(
                f"{self.rest_api_base}/search",
                params=params,
            )
            batch = payload.get("issues", [])
            logger.debug(
                "Fetched Jira search page start_at=%s count=%s total=%s",
                start_at,
                len(batch),
                payload.get("total", 0),
            )
            issues.extend(
                _parse_issue(
                    item,
                    self.parent_field,
                    ignored_changelog_fields=ignored_changelog_fields,
                    include_activity=include_activity,
                )
                for item in batch
            )
            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                logger.info("Jira search returned %s issues", len(issues))
                return issues

    def get_issue_worklogs(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[TempoWorklog]:
        logger.debug(
            "Filtering Jira worklogs for issue=%s period=%s..%s",
            issue_id_or_key,
            sprint_start,
            sprint_end,
        )
        return [
            worklog
            for worklog in self.get_all_issue_worklogs(issue_id_or_key)
            if sprint_start <= worklog.start_date <= sprint_end
        ]

    def get_all_issue_worklogs(self, issue_id_or_key: str) -> list[TempoWorklog]:
        logger.debug("Fetching all Jira worklogs for issue %s", issue_id_or_key)
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
            logger.debug(
                "Fetched Jira worklog page issue=%s start_at=%s count=%s total=%s",
                issue_id_or_key,
                start_at,
                len(batch),
                payload.get("total", 0),
            )
            for raw_worklog in batch:
                worklogs.append(_parse_jira_worklog(raw_worklog))

            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                logger.debug(
                    "Loaded %s Jira worklogs for issue %s",
                    len(worklogs),
                    issue_id_or_key,
                )
                return worklogs

    def get_issue_comments(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[JiraComment]:
        logger.debug(
            "Fetching Jira comments for issue=%s period=%s..%s",
            issue_id_or_key,
            sprint_start,
            sprint_end,
        )
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
            logger.debug(
                "Fetched Jira comments page issue=%s start_at=%s count=%s total=%s",
                issue_id_or_key,
                start_at,
                len(batch),
                payload.get("total", 0),
            )
            for raw_comment in batch:
                comment = _parse_comment(raw_comment)
                created_date = comment.created_at.date()
                if sprint_start <= created_date <= sprint_end:
                    comments.append(comment)

            start_at += len(batch)
            if start_at >= payload.get("total", 0) or not batch:
                logger.debug(
                    "Loaded %s Jira comments in period for issue %s",
                    len(comments),
                    issue_id_or_key,
                )
                return comments

    def get_issue_changes(
        self,
        issue_id_or_key: str,
        sprint_start: date,
        sprint_end: date,
    ) -> list[JiraIssueChange]:
        logger.debug(
            "Fetching Jira changelog for issue=%s period=%s..%s",
            issue_id_or_key,
            sprint_start,
            sprint_end,
        )
        histories = self._get_issue_changelog_histories(issue_id_or_key)
        changes = [
            change
            for history in histories
            for change in _parse_changelog_history(
                history,
                self.ignored_changelog_fields,
            )
            if sprint_start <= change.created_at.date() <= sprint_end
        ]
        logger.debug(
            "Loaded %s Jira changelog changes in period for issue %s",
            len(changes),
            issue_id_or_key,
        )
        return changes

    def _get_issue_changelog_histories(
        self,
        issue_id_or_key: str,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            f"{self.rest_api_base}/issue/{issue_id_or_key}",
            params={
                "fields": "key",
                "expand": "changelog",
            },
        )
        changelog = payload.get("changelog") or {}
        if not isinstance(changelog, dict):
            logger.warning("Ignoring unexpected Jira changelog payload")
            return []

        histories = _payload_list(changelog, "histories")
        paging = _changelog_paging(changelog)
        if paging is None:
            return histories

        start_at, _max_results, total = paging
        loaded_until = start_at + len(histories)
        if total <= loaded_until:
            return histories

        logger.warning(
            "Embedded Jira changelog is truncated for issue %s "
            "(loaded=%s total=%s); using embedded changelog only because "
            "this Jira instance may not support /issue/{key}/changelog",
            issue_id_or_key,
            len(histories),
            total,
        )
        return histories

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        logger.debug("Jira GET %s params=%s", path, params)
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
        if self.parent_field:
            fields.append(self.parent_field)
        return fields


def _parse_issue(
    raw: dict[str, Any],
    parent_field: str | None = None,
    ignored_changelog_fields: frozenset[str] = DEFAULT_IGNORED_CHANGELOG_FIELDS,
    include_activity: bool = False,
) -> Issue:
    fields = raw.get("fields") or {}
    status = fields.get("status") or {}
    status_category = status.get("statusCategory") or {}
    assignee = fields.get("assignee") or {}
    issue_type = fields.get("issuetype") or {}
    priority = fields.get("priority") or {}
    timetracking = fields.get("timetracking") or {}
    comments: tuple[JiraComment, ...] = ()
    changes: tuple[JiraIssueChange, ...] = ()
    if include_activity:
        comments = tuple(
            _parse_comment(item)
            for item in _payload_list(fields.get("comment") or {}, "comments")
        )
        changelog = raw.get("changelog") or {}
        if isinstance(changelog, dict):
            changes = tuple(
                change
                for history in _payload_list(changelog, "histories")
                for change in _parse_changelog_history(
                    history,
                    ignored_changelog_fields,
                )
            )
            paging = _changelog_paging(changelog)
            if paging is not None:
                start_at, _max_results, total = paging
                loaded_until = start_at + len(_payload_list(changelog, "histories"))
                if total > loaded_until:
                    logger.warning(
                        "Embedded Jira changelog is truncated for issue %s "
                        "(loaded=%s total=%s); using embedded changelog only",
                        raw.get("key"),
                        len(changes),
                        total,
                    )

    return Issue(
        id=str(raw["id"]),
        key=raw["key"],
        summary=fields.get("summary", ""),
        status=status.get("name", ""),
        status_category=status_category.get("key", status_category.get("name", "")),
        assignee=assignee.get("displayName") if assignee else None,
        issue_type=issue_type.get("name") if issue_type else None,
        parent=_extract_parent(fields, parent_field),
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
        comments=comments,
        changes=changes,
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
    author = user_identity_from_mapping(raw.get("author") or {})
    issue_id = raw.get("issueId", "")
    started = _parse_jira_datetime(raw["started"])
    return TempoWorklog(
        issue_id=str(issue_id),
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=started.date(),
        author=user_label(author),
        author_key=author.key or author.account_id or author.name,
        author_identity=author,
        description=_plain_text_from_adf(raw.get("comment", "")),
    )


def _parse_changelog_history(
    raw: dict[str, Any],
    ignored_fields: frozenset[str] = DEFAULT_IGNORED_CHANGELOG_FIELDS,
) -> list[JiraIssueChange]:
    author = raw.get("author") or {}
    created_at = _parse_jira_datetime(raw["created"])
    return [
        JiraIssueChange(
            author=author.get("displayName") if author else None,
            created_at=created_at,
            field=str(item.get("field") or ""),
            from_value=_optional_str(item.get("fromString")),
            to_value=_optional_str(item.get("toString")),
        )
        for item in raw.get("items", [])
        if isinstance(item, dict)
        and not _is_ignored_changelog_item(item, ignored_fields)
    ]


def _is_ignored_changelog_item(
    item: dict[str, Any],
    ignored_fields: frozenset[str],
) -> bool:
    return str(item.get("field") or "").casefold() in ignored_fields


def _changelog_paging(payload: dict[str, Any]) -> tuple[int, int, int] | None:
    if not {"startAt", "maxResults", "total"}.issubset(payload):
        return None
    return (
        _int_or_default(payload.get("startAt"), 0),
        _int_or_default(payload.get("maxResults"), 0),
        _int_or_default(payload.get("total"), 0),
    )


def _payload_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


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


def _extract_parent(
    fields: dict[str, Any], parent_field: str | None = None
) -> str | None:
    if parent_field:
        parent = _format_parent_value(fields.get(parent_field))
        if parent:
            return parent

    parent = fields.get("parent") or {}
    if not isinstance(parent, dict):
        return None

    parent_fields = parent.get("fields") or {}
    issue_type = parent_fields.get("issuetype") or {}
    parent_key = parent.get("key")
    parent_summary = parent_fields.get("summary")

    if issue_type.get("name") == "Epic" and parent_key:
        return _format_parent_parts(parent_key, parent_summary)
    if parent_key and parent_summary:
        return _format_parent_parts(parent_key, parent_summary)
    if parent_key:
        return str(parent_key)
    return None


def _format_parent_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if not isinstance(value, dict):
        return None

    key = value.get("key")
    summary = (value.get("fields") or {}).get("summary") or value.get("name")
    if key:
        return _format_parent_parts(str(key), summary)
    if summary:
        return str(summary)
    return None


def _format_parent_parts(key: str, summary: Any) -> str:
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
