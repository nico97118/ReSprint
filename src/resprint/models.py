from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

REVIEW_STATE_CLOSED = "closed"
REVIEW_STATE_ABANDONED = "abandoned"
REVIEW_STATE_OPEN = "open"
REVIEW_STATE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class Board:
    id: int
    name: str
    type: str


@dataclass(frozen=True)
class TempoTeam:
    id: int
    name: str


@dataclass(frozen=True)
class UserIdentity:
    name: str | None = None
    display_name: str | None = None
    key: str | None = None
    account_id: str | None = None

    @property
    def label(self) -> str | None:
        return self.display_name or self.name or self.key or self.account_id

    @property
    def identifiers(self) -> frozenset[str]:
        return frozenset(
            value.casefold()
            for value in (self.name, self.display_name, self.key, self.account_id)
            if value
        )


@dataclass(frozen=True)
class TempoTeamMember:
    identity: UserIdentity

    @property
    def name(self) -> str | None:
        return self.identity.name

    @property
    def display_name(self) -> str | None:
        return self.identity.display_name

    @property
    def key(self) -> str | None:
        return self.identity.key or self.identity.account_id

    @property
    def identifiers(self) -> frozenset[str]:
        return self.identity.identifiers


@dataclass(frozen=True)
class Sprint:
    id: int
    name: str
    start_date: date
    end_date: date
    state: str | None = None


@dataclass(frozen=True)
class Issue:
    id: str
    key: str
    summary: str
    status: str
    status_category: str
    assignee: str | None
    project_key: str | None = None
    issue_type: str | None = None
    parent: str | None = None
    priority: str | None = None
    fix_versions: tuple[str, ...] = field(default_factory=tuple)
    original_estimate_seconds: int | None = None
    remaining_estimate_seconds: int | None = None
    comments: tuple[JiraComment, ...] = field(default_factory=tuple)
    changes: tuple[JiraIssueChange, ...] = field(default_factory=tuple)

    reviews: tuple[ReviewRef, ...] = field(default_factory=tuple)

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
    issue_key: str | None = None
    author_key: str | None = None
    author_identity: UserIdentity = field(default_factory=UserIdentity)


@dataclass(frozen=True)
class JiraComment:
    id: str
    issue_id: str
    author: str | None
    created_at: datetime
    body: str


@dataclass(frozen=True)
class JiraIssueChange:
    author: str | None
    created_at: datetime
    field: str
    from_value: str | None
    to_value: str | None


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
    total_seconds: int
    worklog_count: int
    authors: tuple[str, ...] = field(default_factory=tuple)
    time_spent_by_user: tuple[UserTimeSpent, ...] = field(default_factory=tuple)
    total_time_spent_by_user: tuple[UserTimeSpent, ...] = field(default_factory=tuple)
    comments: tuple[JiraComment, ...] = field(default_factory=tuple)
    changes: tuple[JiraIssueChange, ...] = field(default_factory=tuple)

    @property
    def tempo_hours(self) -> float:
        return self.tempo_seconds / 3600

    @property
    def total_hours(self) -> float:
        return self.total_seconds / 3600

    @property
    def is_over_original_estimate(self) -> bool:
        original_estimate = self.issue.original_estimate_seconds
        return original_estimate is not None and self.total_seconds > original_estimate


@dataclass(frozen=True)
class SprintReview:
    completed: tuple[IssueReviewItem, ...]
    unfinished_with_time: tuple[IssueReviewItem, ...]
    not_started: tuple[IssueReviewItem, ...]
    out_of_sprint: tuple[IssueReviewItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReviewRef:
    """One reference to a Phorge review (a Differential revision), as found
    on a Jira ticket. Only the numeric id is kept: the ``D`` label and the
    review URL are Phorge conventions rebuilt at render time."""

    id: int


@dataclass(frozen=True)
class ReviewDecision:
    """One distinct reviewer decision; name is optional when lookup fails."""

    phid: str
    status: str
    is_blocking: bool
    name: str | None = None


@dataclass(frozen=True)
class ReviewStatus:
    """The status of a Phorge review, as returned by the Differential API.

    ``status_name`` is the raw API label (``Closed``, ``Abandoned``,
    ``Changes Requested``, ...); ``state`` normalizes it into the small set
    the renderers understand."""

    id: int
    status_name: str | None = None
    title: str | None = None
    repository_phid: str | None = None
    created_at: datetime | None = None
    status_code: str | None = None
    reviewers: tuple[ReviewDecision, ...] | None = None
    validation_count: int | None = None
    pending_required_approval_count: int | None = None
    min_validations: int = 2
    max_pending_required_approvals: int = 0
    author_phid: str | None = None
    author_name: str | None = None

    @property
    def ready_to_close(self) -> bool | None:
        """Whether an open review meets the configured approval thresholds.

        None means that review state or reviewer data is unavailable.
        Closed and abandoned revisions are never candidates.
        """
        if self.state in (REVIEW_STATE_CLOSED, REVIEW_STATE_ABANDONED):
            return False
        if (
            self.state != REVIEW_STATE_OPEN
            or self.validation_count is None
            or self.pending_required_approval_count is None
        ):
            return None
        return (
            self.validation_count >= self.min_validations
            and self.pending_required_approval_count
            <= self.max_pending_required_approvals
        )

    @property
    def state(self) -> str:
        # Conduit status codes are stable across translations. An accepted
        # revision still counts as open until it lands.
        if self.status_code in ("0", "1", "2", "5"):
            return REVIEW_STATE_OPEN
        if self.status_code == "3":
            return REVIEW_STATE_CLOSED
        if self.status_code == "4":
            return REVIEW_STATE_ABANDONED
        if self.status_code is not None:
            return REVIEW_STATE_UNKNOWN
        # Older payloads and callers may supply only the display label.
        if self.status_name is None:
            return REVIEW_STATE_UNKNOWN
        if self.status_name == "Closed":
            return REVIEW_STATE_CLOSED
        if self.status_name == "Abandoned":
            return REVIEW_STATE_ABANDONED
        return REVIEW_STATE_OPEN
