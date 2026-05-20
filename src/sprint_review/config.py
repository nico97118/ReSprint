from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    tempo_api_token: str
    done_status_categories: frozenset[str]
    min_seconds: int
    epic_field: str | None

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()

        missing = [
            name
            for name in (
                "JIRA_BASE_URL",
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "TEMPO_API_TOKEN",
            )
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Variables d'environnement manquantes: {joined}")

        categories = os.getenv("SPRINT_REVIEW_DONE_STATUS_CATEGORIES", "done")
        min_seconds = int(os.getenv("SPRINT_REVIEW_MIN_SECONDS", "1"))

        return cls(
            jira_base_url=os.environ["JIRA_BASE_URL"].rstrip("/"),
            jira_email=os.environ["JIRA_EMAIL"],
            jira_api_token=os.environ["JIRA_API_TOKEN"],
            tempo_api_token=os.environ["TEMPO_API_TOKEN"],
            done_status_categories=frozenset(
                item.strip().lower() for item in categories.split(",") if item.strip()
            ),
            min_seconds=min_seconds,
            epic_field=os.getenv("SPRINT_REVIEW_EPIC_FIELD") or None,
        )


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
