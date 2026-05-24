from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date

from resprint.analysis import build_out_of_sprint_items, build_sprint_review
from resprint.config import Settings
from resprint.helpers.jira import JiraClient
from resprint.helpers.tempo import TempoIssueWorklogClient, TempoTeamWorklogClient
from resprint.models import Issue, IssueReviewItem, Sprint, SprintReview


@dataclass(frozen=True)
class ReportContext:
    review: SprintReview
    sprint: Sprint
    jira_base_url: str
    jql: str | None = None


def create_jira_client(settings: Settings) -> JiraClient:
    return JiraClient(
        settings.jira_base_url,
        settings.jira_username,
        settings.jira_api_token,
        settings.epic_field,
        settings.jira_auth_method,
        settings.jira_rest_api_version,
    )


def create_tempo_team_worklog_client(settings: Settings) -> TempoTeamWorklogClient:
    return TempoTeamWorklogClient(
        settings.jira_base_url,
        settings.jira_username,
        settings.jira_api_token,
        settings.jira_auth_method,
    )


def build_report(
    settings: Settings,
    sprint_id: int | None = None,
    board_id: int | None = None,
    jql: str | None = None,
    min_hours: float | None = None,
    worklog_source: str | None = None,
    sprint_start: date | None = None,
    sprint_end: date | None = None,
    sprint_name: str | None = None,
    tempo_team_id: int | None = None,
) -> ReportContext:
    jira = create_jira_client(settings)
    min_seconds = (
        int(min_hours * 3600) if min_hours is not None else settings.min_seconds
    )
    selected_worklog_source = worklog_source or settings.worklog_source
    if selected_worklog_source == "tempo" and not settings.tempo_api_token:
        raise ValueError("TEMPO_API_TOKEN est requis avec la source de temps 'tempo'")
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
    if jql:
        issues = jira.search_issues(_report_jql(jql, sprint_id))
    else:
        if sprint_id is None:
            raise ValueError("Un sprint_id est requis sans requete JQL")
        issues = jira.get_sprint_issues(sprint_id, board_id)
    issues = jira.enrich_epic_summaries(issues)

    total_worklogs_by_issue_id = None
    if tempo:
        worklogs_by_issue_id = {
            issue.id: tempo.get_issue_worklogs(
                issue.id,
                sprint.start_date,
                sprint.end_date,
            )
            for issue in issues
        }
    else:
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
    )
    if tempo_team_id is not None:
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
    review = _with_comments(
        review,
        (
            replace(
                item,
                comments=tuple(
                    jira.get_issue_comments(
                        item.issue.key,
                        sprint.start_date,
                        sprint.end_date,
                    )
                ),
            )
            for item in _iter_review_items(review)
        ),
    )

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
            raise ValueError(
                "--sprint-start et --sprint-end doivent etre fournis ensemble"
            )
        return Sprint(
            id=sprint_id or 0,
            name=sprint_name or _period_name(sprint_start, sprint_end, sprint_id),
            start_date=sprint_start,
            end_date=sprint_end,
        )
    if sprint_id is None:
        raise ValueError(
            "Un sprint_id est requis sans dates de debut et de fin explicites"
        )
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
    return f"Periode {sprint_start.isoformat()} - {sprint_end.isoformat()}"


def _iter_review_items(review: SprintReview) -> Iterable[IssueReviewItem]:
    yield from review.completed
    yield from review.unfinished_with_time
    yield from review.not_started


def _build_out_of_sprint_items(
    settings: Settings,
    jira: JiraClient,
    sprint_issues: list[Issue],
    sprint: Sprint,
    tempo_team_id: int,
) -> tuple[IssueReviewItem, ...]:
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
    enriched_out_issues = jira.enrich_epic_summaries(
        jira.get_issues_by_keys(out_issue_keys)
    )
    issues_by_key = {issue.key: issue for issue in enriched_out_issues}
    return build_out_of_sprint_items(
        sprint_issue_keys,
        issues_by_key,
        worklogs,
    )


def _with_comments(
    review: SprintReview,
    enriched_items: Iterable[IssueReviewItem],
) -> SprintReview:
    by_key = {item.issue.key: item for item in enriched_items}
    return SprintReview(
        completed=tuple(by_key[item.issue.key] for item in review.completed),
        unfinished_with_time=tuple(
            by_key[item.issue.key] for item in review.unfinished_with_time
        ),
        not_started=tuple(by_key[item.issue.key] for item in review.not_started),
        out_of_sprint=review.out_of_sprint,
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
