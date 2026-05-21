from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class Sprint:
    id: int
    name: str
    start_date: date
    end_date: date


@dataclass(frozen=True)
class Issue:
    id: str
    key: str
    summary: str
    status: str
    status_category: str
    assignee: str | None
    issue_type: str | None = None
    epic: str | None = None
    priority: str | None = None
    fix_versions: tuple[str, ...] = field(default_factory=tuple)
    original_estimate_seconds: int | None = None
    remaining_estimate_seconds: int | None = None

    @property
    def url_key(self) -> str:
        return self.key


@dataclass(frozen=True)
class TempoWorklog:
    issue_id: str
    time_spent_seconds: int
    start_date: date
    author: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class JiraComment:
    id: str
    issue_id: str
    author: str | None
    created_at: datetime
    body: str


@dataclass(frozen=True)
class UserTimeSpent:
    user: str
    seconds: int

    @property
    def hours(self) -> float:
        return self.seconds / 3600


@dataclass(frozen=True)
class IssueReviewItem:
    issue: Issue
    tempo_seconds: int
    worklog_count: int
    authors: tuple[str, ...] = field(default_factory=tuple)
    time_spent_by_user: tuple[UserTimeSpent, ...] = field(default_factory=tuple)
    comments: tuple[JiraComment, ...] = field(default_factory=tuple)

    @property
    def tempo_hours(self) -> float:
        return self.tempo_seconds / 3600


@dataclass(frozen=True)
class SprintReview:
    completed_over_original_estimate: tuple[IssueReviewItem, ...]
    unfinished_with_time: tuple[IssueReviewItem, ...]
    not_started: tuple[IssueReviewItem, ...]
