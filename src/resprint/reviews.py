"""Build a current snapshot of reviews referenced anywhere in the report scope."""

from dataclasses import asdict, replace
from datetime import UTC, datetime

import requests

from resprint.config import Settings
from resprint.helpers.phorge import PhorgeAPIError, PhorgeClient
from resprint.logging import get_logger
from resprint.models import Issue

logger = get_logger(__name__)


def load_reviews(settings: Settings, issues: list[Issue]) -> dict | None:
    """Resolve unique references; retain unknown reviews when Phorge fails."""
    if not settings.reviews_enabled:
        logger.debug("Phorge review analysis disabled")
        return None
    tickets: dict[int, list[str]] = {}
    for issue in issues:
        for ref in issue.reviews:
            keys = tickets.setdefault(ref.id, [])
            if issue.key not in keys:
                keys.append(issue.key)
    logger.info(
        "Loading Phorge review snapshot references=%s issues=%s",
        len(tickets),
        len(issues),
    )
    now = datetime.now(UTC)
    statuses = {}
    repositories = {}
    warning = None
    warning_detail = None
    if tickets:
        client = PhorgeClient(
            settings.phorge_base_url or "",
            settings.phorge_api_token or "",
            ca_bundle=settings.phorge_ca_bundle or settings.jira_ca_bundle,
        )
        try:
            statuses = {
                review_id: replace(
                    status,
                    min_validations=settings.review_min_validations,
                    max_pending_required_approvals=(
                        settings.review_max_pending_required_approvals
                    ),
                )
                for review_id, status in client.query_revisions(tuple(tickets)).items()
            }
        except (requests.RequestException, ValueError) as exc:
            warning = "reviews.unavailable"
            warning_detail = _failure_detail(exc)
            logger.warning(
                "Phorge review lookup failed; retaining unknown references: %s",
                warning_detail,
            )
        try:
            repositories = client.query_repository_names(
                tuple(
                    dict.fromkeys(
                        s.repository_phid
                        for s in statuses.values()
                        if s.repository_phid
                    )
                )
            )
        except (requests.RequestException, ValueError) as exc:
            warning = "reviews.repositories_unavailable"
            logger.warning(
                "Phorge repository lookup failed; retaining review states: %s",
                _failure_detail(exc),
            )
    rows = []
    for rid, keys in sorted(tickets.items()):
        status = statuses.get(rid)
        state = status.state if status else "unknown"
        rows.append(
            dict(
                id=rid,
                label=f"D{rid}",
                url=f"{settings.phorge_base_url}/D{rid}",
                title=status.title if status else None,
                author_phid=status.author_phid if status else None,
                author_name=status.author_name if status else None,
                state=state,
                status_name=status.status_name if status else None,
                validation_count=status.validation_count if status else None,
                pending_required_approval_count=(
                    status.pending_required_approval_count if status else None
                ),
                ready_to_close=status.ready_to_close if status else None,
                reviewers=(
                    [asdict(ref) for ref in status.reviewers]
                    if status and status.reviewers is not None
                    else None
                ),
                repository=repositories.get(status.repository_phid) if status else None,
                age_days=max(0, (now - status.created_at).days)
                if status and status.created_at and state == "open"
                else None,
                issue_keys=keys,
            )
        )
    logger.info(
        "Phorge snapshot completed reviews=%s unknown=%s",
        len(rows),
        sum(row["state"] == "unknown" for row in rows),
    )
    return dict(
        checked_at=now.isoformat(),
        closure_criteria={
            "min_validations": settings.review_min_validations,
            "max_pending_required_approvals": (
                settings.review_max_pending_required_approvals
            ),
        },
        warning=warning,
        warning_detail=warning_detail,
        items=rows,
        counts={
            state: sum(row["state"] == state for row in rows)
            for state in ("open", "closed", "abandoned", "unknown")
        },
    )


def _failure_detail(exc: Exception) -> str:
    """Return a diagnostic without URLs, credentials or response bodies."""
    if isinstance(exc, PhorgeAPIError):
        return f"Conduit: {exc.code}"
    if isinstance(exc, requests.exceptions.SSLError):
        return "TLS: certificat / certificate (phorge.ca_bundle)"
    if isinstance(exc, requests.Timeout):
        return "Timeout: API request timed out / délai API dépassé"
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, requests.ConnectionError):
        return "Connection: API unreachable / connexion API impossible"
    if isinstance(exc, ValueError):
        return "Invalid API response / réponse API invalide (JSON attendu)"
    return type(exc).__name__


def issue_review_inconsistency(refs: list[dict], is_done: bool) -> str | None:
    """Return the reason for a confirmed ticket/review state mismatch.

    Empty or unknown references never establish that a ticket is ready to
    finish. Abandoned reviews are ignored, including when all are abandoned.
    """
    refs = [ref for ref in refs if ref.get("state") != "abandoned"]
    if not refs:
        return None
    if is_done:
        if any(ref.get("state") == "open" for ref in refs):
            return "reviews.inconsistent_done"
        return None
    if all(ref.get("state") == "closed" for ref in refs):
        return "reviews.inconsistent_closed"
    if all(
        ref.get("state") == "closed"
        or (ref.get("state") == "open" and ref.get("ready_to_close") is True)
        for ref in refs
    ):
        return "reviews.inconsistent_ready"
    return None
