from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date

from resprint.analysis import build_sprint_review
from resprint.config import Settings
from resprint.helpers.jira import JiraClient
from resprint.helpers.tempo import TempoClient
from resprint.models import IssueReviewItem, Sprint, SprintReview


@dataclass(frozen=True)
class ReportContext:
    review: SprintReview
    sprint: Sprint
    jira_base_url: str


def create_jira_client(settings: Settings) -> JiraClient:
    return JiraClient(
        settings.jira_base_url,
        settings.jira_username,
        settings.jira_api_token,
        settings.epic_field,
        settings.jira_auth_method,
        settings.jira_rest_api_version,
    )


def build_report(
    settings: Settings,
    sprint_id: int,
    board_id: int | None = None,
    jql: str | None = None,
    min_hours: float | None = None,
    worklog_source: str | None = None,
    sprint_start: date | None = None,
    sprint_end: date | None = None,
    sprint_name: str | None = None,
) -> ReportContext:
    jira = create_jira_client(settings)
    min_seconds = (
        int(min_hours * 3600) if min_hours is not None else settings.min_seconds
    )
    selected_worklog_source = worklog_source or settings.worklog_source
    if selected_worklog_source == "tempo" and not settings.tempo_api_token:
        raise ValueError("TEMPO_API_TOKEN est requis avec la source de temps 'tempo'")
    tempo = (
        TempoClient(settings.tempo_api_token)
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
        issues = jira.search_issues(f"({jql}) AND sprint = {sprint_id}")
    else:
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
    )


def _resolve_sprint(
    jira: JiraClient,
    sprint_id: int,
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
            id=sprint_id,
            name=sprint_name or f"Sprint {sprint_id}",
            start_date=sprint_start,
            end_date=sprint_end,
        )
    return jira.get_sprint(sprint_id)


def _iter_review_items(review: SprintReview) -> Iterable[IssueReviewItem]:
    yield from review.completed
    yield from review.unfinished_with_time
    yield from review.not_started


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
    )
