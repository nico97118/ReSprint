from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from resprint.analysis import build_out_of_sprint_items, build_sprint_review
from resprint.config import Settings
from resprint.frontend.i18n import t
from resprint.helpers.jira import JiraClient
from resprint.helpers.tempo import TempoIssueWorklogClient, TempoTeamWorklogClient
from resprint.logging import get_logger
from resprint.models import Issue, IssueReviewItem, Sprint, SprintReview

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReportContext:
    review: SprintReview
    sprint: Sprint
    jira_base_url: str
    jql: str | None = None


def create_jira_client(settings: Settings) -> JiraClient:
    logger.debug(
        "Creating Jira client for %s rest_api=%s",
        settings.jira_base_url,
        settings.jira_rest_api_version,
    )
    return JiraClient(
        base_url=settings.jira_base_url,
        api_token=settings.jira_api_token,
        parent_field=settings.parent_field,
        rest_api_version=settings.jira_rest_api_version,
        ignored_changelog_fields=settings.ignored_changelog_fields,
    )


def create_tempo_team_worklog_client(settings: Settings) -> TempoTeamWorklogClient:
    logger.debug("Creating Tempo team worklog client for %s", settings.jira_base_url)
    return TempoTeamWorklogClient(
        settings.jira_base_url,
        settings.jira_api_token,
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
    tempo = (
        TempoIssueWorklogClient(settings.tempo_api_token)
        if selected_worklog_source == "tempo" and settings.tempo_api_token
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
        issues = jira.search_issues(_report_jql(jql, sprint_id), include_activity=True)
    else:
        if sprint_id is None:
            logger.error("Missing sprint_id without JQL")
            raise ValueError(t("report.missing_sprint_id_without_jql"))
        logger.info("Loading sprint issues from Jira sprint %s", sprint_id)
        issues = jira.search_issues(
            f"sprint = {sprint_id}",
            include_activity=True,
        )
    logger.info("Loaded %s sprint issues", len(issues))
    issues = jira.enrich_parent_summaries(issues)

    total_worklogs_by_issue_id = None
    if tempo:
        logger.info("Loading issue worklogs from Tempo")
        worklogs_by_issue_id = {
            issue.id: tempo.get_issue_worklogs(
                issue.id,
                sprint.start_date,
                sprint.end_date,
            )
            for issue in issues
        }
    else:
        logger.info("Loading issue worklogs from Jira")
        total_worklogs_by_issue_id = {
            issue.id: jira.get_all_issue_worklogs(issue.key) for issue in issues
        }
        worklogs_by_issue_id = {
            issue.id: [
                worklog
                for worklog in total_worklogs_by_issue_id[issue.id]
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
        review = _with_out_of_sprint_items(
            review,
            _build_out_of_sprint_items(
                settings,
                jira,
                issues,
                sprint,
                tempo_team_id,
            ),
        )
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
    settings: Settings,
    jira: JiraClient,
    sprint_issues: list[Issue],
    sprint: Sprint,
    tempo_team_id: int,
) -> tuple[IssueReviewItem, ...]:
    logger.debug("Searching Tempo team worklogs for out-of-sprint analysis")
    tempo_team_worklogs = create_tempo_team_worklog_client(settings)
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
    logger.info(
        "Identified %s out-of-sprint issue keys from %s team worklogs",
        len(out_issue_keys),
        len(worklogs),
    )
    enriched_out_issues = jira.enrich_parent_summaries(
        jira.get_issues_by_keys(out_issue_keys)
    )
    issues_by_key = {issue.key: issue for issue in enriched_out_issues}
    return build_out_of_sprint_items(
        sprint_issue_keys,
        issues_by_key,
        worklogs,
        sprint.start_date,
        sprint.end_date,
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
