from __future__ import annotations

from datetime import date
from typing import Any

import requests

from sprint_review.models import TempoWorklog


class TempoClient:
    def __init__(self, api_token: str, base_url: str = "https://api.tempo.io") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_token}",
            }
        )

    def get_issue_worklogs(
        self,
        issue_id: str,
        start_date: date,
        end_date: date,
    ) -> list[TempoWorklog]:
        params: dict[str, Any] = {
            "issueId": issue_id,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "limit": 100,
        }
        worklogs: list[TempoWorklog] = []

        url: str | None = f"{self.base_url}/4/worklogs"
        while url:
            response = self.session.get(
                url,
                params=params if "?" not in url else None,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            worklogs.extend(
                _parse_worklog(item, issue_id) for item in payload.get("results", [])
            )
            url = (payload.get("metadata") or {}).get("next")
            params = {}

        return worklogs


def _parse_worklog(raw: dict[str, Any], fallback_issue_id: str) -> TempoWorklog:
    issue = raw.get("issue") or {}
    author = raw.get("author") or {}
    return TempoWorklog(
        issue_id=str(issue.get("id") or fallback_issue_id),
        time_spent_seconds=int(raw.get("timeSpentSeconds", 0)),
        start_date=date.fromisoformat(raw["startDate"]),
        author=author.get("displayName") or author.get("accountId"),
        description=raw.get("description"),
    )
