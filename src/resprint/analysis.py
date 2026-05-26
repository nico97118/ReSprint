from __future__ import annotations

from collections import defaultdict

from resprint.helpers.user_identity import user_label_or_unknown
from resprint.logging import get_logger
from resprint.models import (
    Issue,
    IssueReviewItem,
    SprintReview,
    TempoWorklog,
    UserTimeSpent,
)

logger = get_logger(__name__)


def build_sprint_review(
    issues: list[Issue],
    worklogs_by_issue_id: dict[str, list[TempoWorklog]],
    done_status_categories: set[str] | frozenset[str],
    min_seconds: int,
    total_worklogs_by_issue_id: dict[str, list[TempoWorklog]] | None = None,
) -> SprintReview:
    logger.debug(
        "Building sprint review for %s issues with min_seconds=%s",
        len(issues),
        min_seconds,
    )
    completed: list[IssueReviewItem] = []
    unfinished_with_time: list[IssueReviewItem] = []
    not_started: list[IssueReviewItem] = []
    done = {status.lower() for status in done_status_categories}

    for issue in issues:
        worklogs = worklogs_by_issue_id.get(issue.id, [])
        total_worklogs = (total_worklogs_by_issue_id or worklogs_by_issue_id).get(
            issue.id,
            [],
        )
        item = _build_issue_review_item(issue, worklogs, total_worklogs)
        is_done = issue.status_category.lower() in done

        if is_done:
            logger.debug("Issue %s classified as completed", issue.key)
            completed.append(item)
            continue

        if not is_done and item.tempo_seconds >= min_seconds:
            logger.debug(
                "Issue %s classified as unfinished with time (%ss)",
                issue.key,
                item.tempo_seconds,
            )
            unfinished_with_time.append(item)
            continue

        if _is_not_started(item, min_seconds, is_done):
            logger.debug("Issue %s classified as not started", issue.key)
            not_started.append(item)

    logger.info(
        "Sprint review classification completed: "
        "completed=%s unfinished=%s not_started=%s",
        len(completed),
        len(unfinished_with_time),
        len(not_started),
    )
    return SprintReview(
        completed=tuple(
            sorted(
                completed,
                key=lambda item: (
                    not item.is_over_original_estimate,
                    -_estimate_delta(item),
                    item.issue.key,
                ),
            )
        ),
        unfinished_with_time=tuple(
            sorted(
                unfinished_with_time,
                key=lambda item: (
                    not item.is_over_original_estimate,
                    -item.tempo_seconds,
                    item.issue.key,
                ),
            )
        ),
        not_started=tuple(
            sorted(
                not_started,
                key=lambda item: (
                    not item.is_over_original_estimate,
                    item.issue.key,
                ),
            )
        ),
    )


def build_review_items(
    issues: list[Issue],
    worklogs_by_issue_id: dict[str, list[TempoWorklog]],
    done_status_categories: set[str] | frozenset[str],
    min_seconds: int,
    total_worklogs_by_issue_id: dict[str, list[TempoWorklog]] | None = None,
) -> list[IssueReviewItem]:
    review = build_sprint_review(
        issues,
        worklogs_by_issue_id,
        done_status_categories,
        min_seconds,
        total_worklogs_by_issue_id,
    )
    return list(review.unfinished_with_time)


def build_out_of_sprint_items(
    sprint_issue_keys: set[str],
    issues_by_key: dict[str, Issue],
    worklogs: list[TempoWorklog],
) -> tuple[IssueReviewItem, ...]:
    logger.debug(
        "Building out-of-sprint items from %s worklogs",
        len(worklogs),
    )
    worklogs_by_issue_key: dict[str, list[TempoWorklog]] = defaultdict(list)
    for worklog in worklogs:
        if not worklog.issue_key or worklog.issue_key in sprint_issue_keys:
            if not worklog.issue_key:
                logger.warning("Ignoring Tempo worklog without issue key")
            continue
        worklogs_by_issue_key[worklog.issue_key].append(worklog)

    items = []
    for issue_key, issue_worklogs in worklogs_by_issue_key.items():
        issue = issues_by_key.get(issue_key)
        if issue is None:
            logger.warning(
                "Ignoring out-of-sprint worklogs for issue %s "
                "because details are missing",
                issue_key,
            )
            continue
        items.append(_build_issue_review_item(issue, issue_worklogs, issue_worklogs))

    logger.info("Built %s out-of-sprint review items", len(items))
    return tuple(
        sorted(
            items,
            key=lambda item: (-item.tempo_seconds, item.issue.key),
        )
    )


def _build_issue_review_item(
    issue: Issue,
    sprint_worklogs: list[TempoWorklog],
    total_worklogs: list[TempoWorklog],
) -> IssueReviewItem:
    sprint_seconds = sum(worklog.time_spent_seconds for worklog in sprint_worklogs)
    total_seconds = sum(worklog.time_spent_seconds for worklog in total_worklogs)
    sprint_time_by_user = _time_spent_by_user(sprint_worklogs)
    total_time_by_user = _time_spent_by_user(total_worklogs)
    authors = sorted(
        {
            worklog.author
            for worklog in sprint_worklogs
            if worklog.author and worklog.time_spent_seconds > 0
        }
    )
    return IssueReviewItem(
        issue=issue,
        tempo_seconds=sprint_seconds,
        total_seconds=total_seconds,
        worklog_count=len(sprint_worklogs),
        authors=tuple(authors),
        time_spent_by_user=sprint_time_by_user,
        total_time_spent_by_user=total_time_by_user,
    )


def _time_spent_by_user(worklogs: list[TempoWorklog]) -> tuple[UserTimeSpent, ...]:
    seconds_by_user: dict[str, int] = defaultdict(int)
    for worklog in worklogs:
        if worklog.time_spent_seconds <= 0:
            continue
        user = worklog.author or user_label_or_unknown(worklog.author_identity)
        seconds_by_user[user] += worklog.time_spent_seconds

    return tuple(
        UserTimeSpent(user=user, seconds=seconds)
        for user, seconds in sorted(
            seconds_by_user.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )


def _is_not_started(
    item: IssueReviewItem,
    min_seconds: int,
    is_done: bool,
) -> bool:
    return (
        not is_done
        and item.issue.status_category.lower() == "new"
        and item.tempo_seconds < min_seconds
    )


def _estimate_delta(item: IssueReviewItem) -> int:
    return item.tempo_seconds - (item.issue.original_estimate_seconds or 0)


def group_worklogs_by_issue(
    worklogs: list[TempoWorklog],
) -> dict[str, list[TempoWorklog]]:
    grouped: dict[str, list[TempoWorklog]] = defaultdict(list)
    for worklog in worklogs:
        grouped[worklog.issue_id].append(worklog)
    return dict(grouped)
