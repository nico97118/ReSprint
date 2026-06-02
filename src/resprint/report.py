from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from threading import local
from typing import Generic, TypeVar

import requests

from resprint.analysis import build_out_of_sprint_items, build_sprint_review
from resprint.config import Settings
from resprint.frontend.i18n import t
from resprint.helpers.jira import JiraClient
from resprint.helpers.tempo import TempoIssueWorklogClient, TempoTeamWorklogClient
from resprint.logging import get_logger
from resprint.models import Issue, IssueReviewItem, Sprint, SprintReview, TempoWorklog

logger = get_logger(__name__)
TIMEOUT_EXCEPTIONS = (TimeoutError, requests.exceptions.Timeout)
T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class ReportContext:
    review: SprintReview
    sprint: Sprint
    jira_base_url: str
    jql: str | None = None


def create_jira_client(
    settings: Settings,
    request_timeout: float = 30,
) -> JiraClient:
    logger.debug(
        "Creating Jira client for %s rest_api=%s",
        settings.jira_base_url,
        settings.jira_rest_api_version,
    )
    return JiraClient(
        base_url=settings.jira_base_url,
        api_token=settings.jira_api_token,
        ca_bundle=settings.jira_ca_bundle,
        parent_field=settings.parent_field,
        rest_api_version=settings.jira_rest_api_version,
        ignored_changelog_fields=settings.ignored_changelog_fields,
        request_timeout=request_timeout,
    )


def create_tempo_team_worklog_client(settings: Settings) -> TempoTeamWorklogClient:
    logger.debug("Creating Tempo team worklog client for %s", settings.jira_base_url)
    return TempoTeamWorklogClient(
        settings.jira_base_url,
        settings.jira_api_token,
        settings.jira_ca_bundle,
    )


def create_tempo_issue_worklog_client(settings: Settings) -> TempoIssueWorklogClient:
    logger.debug("Creating Tempo issue worklog client")
    if not settings.tempo_api_token:
        raise ValueError(t("report.tempo_token_required"))
    return TempoIssueWorklogClient(
        settings.tempo_api_token,
        ca_bundle=settings.jira_ca_bundle,
    )


def build_report(
    settings: Settings,
    sprint_id: int | None = None,
    jql: str | None = None,
    min_hours: float | None = None,
    worklog_source: str | None = None,
    sprint_start: date | None = None,
    sprint_end: date | None = None,
    sprint_name: str | None = None,
    tempo_team_id: int | None = None,
) -> ReportContext:
    logger.info(
        "Building report sprint_id=%s jql=%s tempo_team_id=%s",
        sprint_id,
        bool(jql),
        tempo_team_id,
    )
    jira = create_jira_client(settings)
    jira_issue_clients = _ThreadLocalClientProvider(
        client_factory=lambda: create_jira_client(
            settings,
            request_timeout=settings.jira_issue_request_timeout,
        ),
        max_workers=settings.request_concurrency,
    )
    min_seconds = (
        int(min_hours * 3600) if min_hours is not None else settings.min_seconds
    )
    selected_worklog_source = worklog_source or settings.worklog_source
    logger.debug(
        "Report options min_seconds=%s worklog_source=%s",
        min_seconds,
        selected_worklog_source,
    )
    if selected_worklog_source == "tempo" and not settings.tempo_api_token:
        logger.error("Tempo worklog source selected without TEMPO_API_TOKEN")
        raise ValueError(t("report.tempo_token_required"))
    tempo_issue_clients = (
        _ThreadLocalClientProvider(
            client_factory=lambda: create_tempo_issue_worklog_client(settings),
            max_workers=settings.request_concurrency,
        )
        if selected_worklog_source == "tempo"
        else None
    )

    sprint = _resolve_sprint(
        jira,
        sprint_id,
        sprint_start,
        sprint_end,
        sprint_name,
    )
    logger.info(
        "Resolved report period %s from %s to %s",
        sprint.name,
        sprint.start_date,
        sprint.end_date,
    )
    if jql:
        logger.info("Loading sprint issues from JQL")
        issues = jira.search_issues(_report_jql(jql, sprint_id))
    else:
        if sprint_id is None:
            logger.error("Missing sprint_id without JQL")
            raise ValueError(t("report.missing_sprint_id_without_jql"))
        logger.info("Loading sprint issues from Jira sprint %s", sprint_id)
        issues = jira.search_issues(
            f"sprint = {sprint_id}",
        )
    logger.info("Loaded %s sprint issues", len(issues))
    issues = _filter_excluded_issues(issues, settings.excluded_issue_keys)
    issues = _safe_enrich_parent_summaries(jira, issues)
    issues = _with_issue_activity(jira_issue_clients, issues, sprint)

    total_worklogs_by_issue_id = None
    if tempo_issue_clients:
        logger.info("Loading issue worklogs from Tempo")
        worklogs_by_issue_id = _load_tempo_issue_worklogs(
            tempo_issue_clients,
            issues,
            sprint,
        )
    else:
        logger.info("Loading issue worklogs from Jira")
        total_worklogs_by_issue_key = _load_jira_issue_worklogs(
            jira_issue_clients,
            issues,
        )
        total_worklogs_by_issue_id = {
            issue.id: total_worklogs_by_issue_key.get(issue.key, []) for issue in issues
        }
        worklogs_by_issue_id = {
            issue.id: [
                worklog
                for worklog in total_worklogs_by_issue_key.get(issue.key, [])
                if sprint.start_date <= worklog.start_date <= sprint.end_date
            ]
            for issue in issues
        }

    review = build_sprint_review(
        issues,
        worklogs_by_issue_id,
        settings.done_status_categories,
        min_seconds,
        total_worklogs_by_issue_id,
        sprint.start_date,
        sprint.end_date,
    )
    logger.info(
        "Review classified issues: completed=%s unfinished_with_time=%s not_started=%s",
        len(review.completed),
        len(review.unfinished_with_time),
        len(review.not_started),
    )
    if tempo_team_id is not None:
        logger.info("Loading out-of-sprint worklogs for Tempo team %s", tempo_team_id)
        try:
            out_of_sprint_items = _build_out_of_sprint_items(
                jira,
                jira_issue_clients,
                create_tempo_team_worklog_client(settings),
                settings.excluded_issue_keys,
                settings.out_of_sprint_analysis,
                issues,
                sprint,
                tempo_team_id,
            )
        except Exception:
            logger.exception(
                "Could not load out-of-sprint Tempo worklogs; "
                "continuing without out-of-sprint section",
            )
            out_of_sprint_items = ()
        review = _with_out_of_sprint_items(review, out_of_sprint_items)
        logger.info("Found %s out-of-sprint issues", len(review.out_of_sprint))
    logger.info("Report context built")

    return ReportContext(
        review=review,
        sprint=sprint,
        jira_base_url=settings.jira_base_url,
        jql=jql if jql and sprint_id is None else None,
    )


def _resolve_sprint(
    jira: JiraClient,
    sprint_id: int | None,
    sprint_start: date | None,
    sprint_end: date | None,
    sprint_name: str | None,
) -> Sprint:
    if sprint_start or sprint_end:
        if not sprint_start or not sprint_end:
            logger.error("Incomplete explicit sprint period")
            raise ValueError(t("report.incomplete_explicit_sprint_period"))
        logger.debug("Using explicit sprint period")
        return Sprint(
            id=sprint_id or 0,
            name=sprint_name or _period_name(sprint_start, sprint_end, sprint_id),
            start_date=sprint_start,
            end_date=sprint_end,
        )
    if sprint_id is None:
        logger.error("Missing sprint_id and explicit sprint period")
        raise ValueError(t("report.missing_sprint_id_without_explicit_dates"))
    logger.debug("Resolving sprint %s from Jira", sprint_id)
    return jira.get_sprint(sprint_id)


def _report_jql(jql: str, sprint_id: int | None) -> str:
    if sprint_id is None:
        return jql
    return f"({jql}) AND sprint = {sprint_id}"


def _with_issue_activity(
    jira_issue_clients: _ThreadLocalClientProvider[JiraClient],
    issues: list[Issue],
    sprint: Sprint,
) -> list[Issue]:
    logger.info("Loading issue activity from Jira")

    def load_activity(issue: Issue) -> Issue:
        try:
            comments = jira_issue_clients.get().get_issue_comments(
                issue.key,
                sprint.start_date,
                sprint.end_date,
            )
        except TIMEOUT_EXCEPTIONS as error:
            logger.warning(
                "Jira comments timed out for issue %s; "
                "continuing with this issue comments incomplete (%s)",
                issue.key,
                error,
            )
            comments = []
        except Exception:
            logger.exception(
                "Could not load Jira comments for issue %s; "
                "continuing with this issue comments incomplete",
                issue.key,
            )
            comments = []

        try:
            changes = jira_issue_clients.get().get_issue_changes(
                issue.key,
                sprint.start_date,
                sprint.end_date,
            )
        except TIMEOUT_EXCEPTIONS as error:
            logger.warning(
                "Jira changelog timed out for issue %s; "
                "continuing with this issue activity incomplete (%s)",
                issue.key,
                error,
            )
            changes = []
        except Exception:
            logger.exception(
                "Could not load Jira changelog for issue %s; "
                "continuing with this issue activity incomplete",
                issue.key,
            )
            changes = []
        return replace(issue, comments=tuple(comments), changes=tuple(changes))

    return _parallel_map(issues, load_activity, jira_issue_clients.max_workers)


def _filter_excluded_issues(
    issues: list[Issue],
    excluded_issue_keys: frozenset[str],
) -> list[Issue]:
    if not excluded_issue_keys:
        return issues

    filtered_issues = [
        issue for issue in issues if issue.key.casefold() not in excluded_issue_keys
    ]
    excluded_count = len(issues) - len(filtered_issues)
    if excluded_count:
        logger.info("Excluded %s issues from report settings", excluded_count)
    return filtered_issues


def _safe_enrich_parent_summaries(
    jira: JiraClient,
    issues: list[Issue],
) -> list[Issue]:
    try:
        return jira.enrich_parent_summaries(issues)
    except Exception:
        logger.exception(
            "Could not enrich parent issue summaries; continuing with raw parent data",
        )
        return issues


def _load_jira_issue_worklogs(
    jira_issue_clients: _ThreadLocalClientProvider[JiraClient],
    issues: list[Issue],
) -> dict[str, list[TempoWorklog]]:
    def load_worklogs(issue: Issue) -> tuple[str, list[TempoWorklog] | None]:
        try:
            return issue.key, jira_issue_clients.get().get_all_issue_worklogs(issue.key)
        except TIMEOUT_EXCEPTIONS as error:
            logger.warning(
                "Jira worklogs timed out for issue %s; "
                "continuing with this issue worklog data incomplete (%s)",
                issue.key,
                error,
            )
            return issue.key, None
        except Exception:
            logger.exception(
                "Could not load Jira worklogs for issue %s; "
                "continuing with this issue worklog data incomplete",
                issue.key,
            )
            return issue.key, None

    worklog_results = _parallel_map(
        issues,
        load_worklogs,
        jira_issue_clients.max_workers,
    )
    return {
        issue_key: worklogs
        for issue_key, worklogs in worklog_results
        if worklogs is not None
    }


def _load_tempo_issue_worklogs(
    tempo_issue_clients: _ThreadLocalClientProvider[TempoIssueWorklogClient],
    issues: list[Issue],
    sprint: Sprint,
) -> dict[str, list[TempoWorklog]]:
    def load_worklogs(issue: Issue) -> tuple[str, list[TempoWorklog]]:
        try:
            worklogs = tempo_issue_clients.get().get_issue_worklogs(
                issue.id,
                sprint.start_date,
                sprint.end_date,
            )
        except TIMEOUT_EXCEPTIONS as error:
            logger.warning(
                "Tempo worklogs timed out for issue %s; "
                "continuing with this issue worklog data incomplete (%s)",
                issue.key,
                error,
            )
            worklogs = []
        except Exception:
            logger.exception(
                "Could not load Tempo worklogs for issue %s; "
                "continuing with this issue worklog data incomplete",
                issue.key,
            )
            worklogs = []
        return issue.id, worklogs

    return dict(_parallel_map(issues, load_worklogs, tempo_issue_clients.max_workers))


def _parallel_map(
    items: Iterable[T],
    worker: Callable[[T], R],
    max_workers: int,
) -> list[R]:
    item_list = list(items)
    if not item_list:
        return []

    worker_count = min(max(max_workers, 1), len(item_list))
    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="resprint-report",
    ) as executor:
        return list(executor.map(worker, item_list))


class _ThreadLocalClientProvider(Generic[T]):
    """Provide HTTP clients scoped to worker threads for per-issue requests."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], T],
        max_workers: int,
    ) -> None:
        self.max_workers = max_workers
        self._client_factory = client_factory
        self._thread_local = local()

    def get(self) -> T:
        client = getattr(self._thread_local, "client", None)
        if client is None:
            client = self._client_factory()
            self._thread_local.client = client
        return client


def _period_name(
    sprint_start: date,
    sprint_end: date,
    sprint_id: int | None,
) -> str:
    if sprint_id is not None:
        return f"Sprint {sprint_id}"
    return t(
        "report.period_name",
        start=sprint_start.isoformat(),
        end=sprint_end.isoformat(),
    )


def _build_out_of_sprint_items(
    jira: JiraClient,
    jira_issue_clients: _ThreadLocalClientProvider[JiraClient],
    tempo_team_worklogs: TempoTeamWorklogClient,
    excluded_issue_keys: frozenset[str],
    load_details: bool,
    sprint_issues: list[Issue],
    sprint: Sprint,
    tempo_team_id: int,
) -> tuple[IssueReviewItem, ...]:
    logger.debug("Searching Tempo team worklogs for out-of-sprint analysis")
    worklogs = tempo_team_worklogs.search_team_worklogs(
        tempo_team_id,
        sprint.start_date,
        sprint.end_date,
    )
    sprint_issue_keys = {issue.key for issue in sprint_issues}
    out_issue_keys = sorted(
        {
            worklog.issue_key
            for worklog in worklogs
            if worklog.issue_key and worklog.issue_key not in sprint_issue_keys
        }
    )
    if excluded_issue_keys:
        out_issue_keys = [
            issue_key
            for issue_key in out_issue_keys
            if issue_key.casefold() not in excluded_issue_keys
        ]
    logger.info(
        "Identified %s out-of-sprint issue keys from %s team worklogs",
        len(out_issue_keys),
        len(worklogs),
    )
    enriched_out_issues = _safe_enrich_parent_summaries(
        jira,
        jira.get_issues_by_keys(
            out_issue_keys,
        ),
    )
    if load_details:
        enriched_out_issues = _with_issue_activity(
            jira_issue_clients,
            enriched_out_issues,
            sprint,
        )
    issues_by_key = {issue.key: issue for issue in enriched_out_issues}
    total_worklogs_by_issue_key = (
        _load_jira_issue_worklogs(
            jira_issue_clients,
            enriched_out_issues,
        )
        if load_details
        else None
    )
    return build_out_of_sprint_items(
        sprint_issue_keys,
        issues_by_key,
        worklogs,
        sprint.start_date,
        sprint.end_date,
        total_worklogs_by_issue_key,
    )


def _with_out_of_sprint_items(
    review: SprintReview,
    out_of_sprint: tuple[IssueReviewItem, ...],
) -> SprintReview:
    return SprintReview(
        completed=review.completed,
        unfinished_with_time=review.unfinished_with_time,
        not_started=review.not_started,
        out_of_sprint=out_of_sprint,
    )
