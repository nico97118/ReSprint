"""Read-only client for Phorge Differential and Diffusion."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import requests

from resprint.http import request_error_summary
from resprint.logging import get_logger
from resprint.models import ReviewDecision, ReviewStatus

logger = get_logger(__name__)


class PhorgeAPIError(ValueError):
    """A Conduit error, exposing only its sanitized code, never response text."""

    def __init__(self, code: object) -> None:
        self.code = (
            code
            if isinstance(code, str) and re.fullmatch(r"[A-Z0-9_-]{1,80}", code)
            else "CONDUIT_ERROR"
        )
        super().__init__(self.code)


class PhorgeClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        ca_bundle: str | None = None,
        request_timeout: float = 30,
    ) -> None:
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        logger.debug("Initializing Phorge client timeout=%s", request_timeout)
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"oauth {api_token}"})
        self.session.verify = ca_bundle or True

    def query_revisions(self, review_ids: tuple[int, ...]) -> dict[int, ReviewStatus]:
        """The status of every requested review, keyed by review id.

        The Differential API answers with a ``result`` list of revisions;
        entries without a usable id are skipped, and an empty request does
        not hit the network at all. Transport and payload failures are not
        swallowed: they raise (``requests.RequestException`` or
        ``ValueError``) and the caller decides how to degrade.
        """
        if not review_ids:
            logger.debug("No Phorge review references to query")
            return {}
        logger.info("Querying Phorge for %s reviews", len(review_ids))
        params: dict[str, Any] = {"api.token": self.api_token}
        for index, review_id in enumerate(review_ids):
            params[f"ids[{index}]"] = review_id
        payload = self._post("/api/differential.query", params)
        statuses = _parse_revision_statuses(payload)
        logger.info(
            "Resolved %s of the %s requested Phorge reviews",
            len(statuses),
            len(review_ids),
        )
        self._enrich_reviewer_decisions(statuses)
        self._enrich_reviewer_names(statuses)
        return statuses

    def _enrich_reviewer_decisions(self, statuses: dict[int, ReviewStatus]) -> None:
        """Read paginated reviewer attachments without discarding base review data.

        An unsupported endpoint, an absent attachment or a malformed reviewer
        leaves the corresponding counts unknown. Already resolved pages survive
        subsequent failures. Only IDs resolved by the base query are enriched.
        """
        ids = tuple(statuses)
        logger.debug("Loading reviewer decisions for %s Phorge reviews", len(ids))
        failure_reported = False
        for start in range(0, len(ids), 100):
            params: dict[str, Any] = {
                "api.token": self.api_token,
                "attachments[reviewers]": 1,
            }
            for index, review_id in enumerate(ids[start : start + 100]):
                params[f"constraints[ids][{index}]"] = review_id
            seen_cursors: set[str] = set()
            while True:
                try:
                    payload = self._post("/api/differential.revision.search", params)
                    result = (
                        payload.get("result") if isinstance(payload, dict) else None
                    )
                    if not isinstance(result, dict) or not isinstance(
                        result.get("data"), list
                    ):
                        raise ValueError("Invalid revision search response")
                except (requests.RequestException, ValueError) as exc:
                    # Do not log response bodies or exception strings: these may
                    # include credentials supplied by the remote service.
                    code = (
                        exc.code
                        if isinstance(exc, PhorgeAPIError)
                        else type(exc).__name__
                    )
                    logger.warning("Phorge reviewer decisions unavailable: %s", code)
                    failure_reported = True
                    break
                for raw in result["data"]:
                    if not isinstance(raw, dict):
                        continue
                    review_id = _review_id(raw.get("id"))
                    if review_id not in statuses:
                        continue
                    counts = _parse_reviewer_counts(raw.get("attachments"))
                    if counts is not None:
                        statuses[review_id] = replace(
                            statuses[review_id],
                            reviewers=_parse_reviewer_decisions(raw.get("attachments")),
                            validation_count=counts[0],
                            pending_required_approval_count=counts[1],
                        )
                cursor = result.get("cursor")
                after = (
                    _optional_str(cursor.get("after"))
                    if isinstance(cursor, dict)
                    else None
                )
                if after is None:
                    break
                if after in seen_cursors:
                    logger.warning(
                        "Phorge reviewer pagination repeated a cursor; stopping"
                    )
                    failure_reported = True
                    break
                seen_cursors.add(after)
                params["after"] = after

        incomplete = sum(status.reviewers is None for status in statuses.values())
        if incomplete and not failure_reported:
            logger.warning(
                "Phorge reviewer decisions incomplete reviews=%s", incomplete
            )
        logger.debug(
            "Reviewer decisions completed reviews=%s incomplete=%s",
            len(ids),
            incomplete,
        )

    def _enrich_reviewer_names(self, statuses: dict[int, ReviewStatus]) -> None:
        """Resolve authors and user/project reviewers in read-only PHID batches.

        Retain decisions and counts if names are unavailable or inaccessible.
        """
        reviewer_phids = [
            ref.phid
            for status in statuses.values()
            for ref in (status.reviewers or ())
            if ref.status in {"accepted", "rejected", "blocking"} or ref.is_blocking
        ]
        author_phids = [
            status.author_phid for status in statuses.values() if status.author_phid
        ]
        phids = tuple(dict.fromkeys(reviewer_phids + author_phids))
        names: dict[str, str] = {}
        logger.debug("Resolving %s Phorge author/reviewer names", len(phids))
        for start in range(0, len(phids), 100):
            params: dict[str, Any] = {"api.token": self.api_token}
            batch = phids[start : start + 100]
            for index, phid in enumerate(batch):
                params[f"phids[{index}]"] = phid
            try:
                payload = self._post("/api/phid.query", params)
                result = payload.get("result") if isinstance(payload, dict) else None
                if not isinstance(result, dict):
                    raise ValueError("Invalid PHID lookup response")
            except (requests.RequestException, ValueError) as exc:
                logger.warning(
                    "Phorge author/reviewer names unavailable: %s", type(exc).__name__
                )
                continue
            for phid in batch:
                entry = result.get(phid)
                if isinstance(entry, dict):
                    name = _optional_str(entry.get("fullName")) or _optional_str(
                        entry.get("name")
                    )
                    if name:
                        names[phid] = name
        for review_id, status in statuses.items():
            statuses[review_id] = replace(
                status,
                author_name=names.get(status.author_phid)
                if status.author_phid
                else None,
                reviewers=(
                    tuple(
                        replace(ref, name=names.get(ref.phid))
                        for ref in status.reviewers
                    )
                    if status.reviewers is not None
                    else None
                ),
            )

        logger.debug(
            "Phorge name resolution completed resolved=%s requested=%s",
            len(names),
            len(phids),
        )

    def query_repository_names(self, phids: tuple[str, ...]) -> dict[str, str]:
        """Resolve repository names in batches, preserving results on failure."""
        if not phids:
            logger.debug("No Phorge repositories to resolve")
            return {}
        logger.debug("Resolving %s Phorge repositories", len(phids))
        params: dict[str, Any] = {"api.token": self.api_token}
        for index, phid in enumerate(phids):
            params[f"constraints[phids][{index}]"] = phid

        names: dict[str, str] = {}
        seen_cursors: set[str] = set()
        while True:
            try:
                payload = self._post("/api/diffusion.repository.search", params)
            except requests.RequestException as exc:
                logger.warning(
                    "Phorge repositories unavailable: %s", request_error_summary(exc)
                )
                break
            result = payload.get("result") if isinstance(payload, dict) else None
            if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                logger.warning(
                    "Phorge repositories unavailable: invalid search response"
                )
                break
            for entry in result["data"]:
                if not isinstance(entry, dict):
                    continue
                repository_phid = _optional_str(entry.get("phid"))
                fields = entry.get("fields")
                name = (
                    _optional_str(fields.get("name"))
                    if isinstance(fields, dict)
                    else None
                )
                if repository_phid and name:
                    names[repository_phid] = name

            cursor = result.get("cursor")
            after = (
                _optional_str(cursor.get("after")) if isinstance(cursor, dict) else None
            )
            # A repeated cursor would otherwise keep the report waiting forever.
            if after is None:
                break
            if after in seen_cursors:
                logger.warning(
                    "Phorge repository pagination repeated a cursor; stopping"
                )
                break
            seen_cursors.add(after)
            params["after"] = after
        logger.debug(
            "Phorge repository resolution completed resolved=%s requested=%s",
            len(names),
            len(phids),
        )
        return names

    def _post(self, path: str, data: dict[str, Any]) -> Any:
        logger.debug("Phorge POST %s fields=%s", path, sorted(data))
        response = self.session.post(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error_code"):
            raise PhorgeAPIError(payload["error_code"])
        return payload


def _parse_revision_statuses(payload: Any) -> dict[int, ReviewStatus]:
    """Maps the ``result`` list of a ``differential.query`` payload into
    the review statuses. The payload must be an object carrying a
    ``result`` list, otherwise the response is rejected with a
    ``ValueError``."""
    if not isinstance(payload, dict):
        raise ValueError("Phorge response is not a JSON object")
    result = payload.get("result")
    if not isinstance(result, list):
        raise ValueError("Phorge response has no result list")
    statuses: dict[int, ReviewStatus] = {}
    for raw in result:
        if not isinstance(raw, dict):
            continue
        review_id = _review_id(raw.get("id"))
        if review_id is None:
            continue
        statuses[review_id] = ReviewStatus(
            id=review_id,
            status_name=_optional_str(raw.get("statusName")),
            status_code=_optional_str(raw.get("status")),
            title=_optional_str(raw.get("title")),
            author_phid=_optional_str(raw.get("authorPHID")),
            repository_phid=_optional_str(raw.get("repositoryPHID")),
            created_at=_parse_creation_time(raw.get("dateCreated")),
        )
    return statuses


def _parse_creation_time(value: Any) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        timestamp = int(value)
        return datetime.fromtimestamp(timestamp, UTC) if timestamp > 0 else None
    except (ValueError, OverflowError, OSError):
        return None


def _review_id(value: Any) -> int | None:
    """The numeric id of a revision entry, or None when it is unusable
    (missing, zero or not convertible)."""
    try:
        review_id = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return review_id or None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


_REVIEWER_STATUSES = frozenset(
    {
        "blocking",
        "added",
        "accepted",
        "rejected",
        "commented",
        "accepted-older",
        "rejected-older",
        "resigned",
    }
)


def _parse_reviewer_decisions(attachments: Any) -> tuple[ReviewDecision, ...] | None:
    """Count distinct reviewer decisions; never infer zero from absent data.

    Only accepted decisions count as validations (not accepted-older).
    Contradictory duplicates and unknown statuses make the data indeterminate.
    User and project reviewer entries each contribute at most one approval.
    """
    if not isinstance(attachments, dict):
        return None
    attachment = attachments.get("reviewers")
    refs = attachment.get("reviewers") if isinstance(attachment, dict) else None
    if not isinstance(refs, list):
        return None
    decisions: dict[str, tuple[str, bool]] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            return None
        phid = _optional_str(ref.get("reviewerPHID"))
        state = ref.get("status")
        blocking = ref.get("isBlocking")
        if (
            not phid
            or not isinstance(state, str)
            or state not in _REVIEWER_STATUSES
            or not isinstance(blocking, bool)
        ):
            return None
        decision = (state, blocking)
        if phid in decisions and decisions[phid] != decision:
            return None
        decisions[phid] = decision
    return tuple(
        ReviewDecision(phid, state, blocking)
        for phid, (state, blocking) in decisions.items()
    )


def _parse_reviewer_counts(attachments: Any) -> tuple[int, int] | None:
    """Count approvals and mandatory approvals pending from complete decisions."""
    refs = _parse_reviewer_decisions(attachments)
    if refs is None:
        return None
    return (
        sum(ref.status == "accepted" for ref in refs),
        sum(
            (ref.is_blocking or ref.status == "blocking") and ref.status != "accepted"
            for ref in refs
        ),
    )
