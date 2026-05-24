from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jira_base_url: str
    jira_username: str | None
    jira_api_token: str
    jira_auth_method: str
    jira_rest_api_version: str
    jira_project_key: str | None
    tempo_api_token: str | None
    worklog_source: str
    done_status_categories: frozenset[str]
    min_seconds: int
    parent_field: str | None
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()

        missing = [
            name
            for name in (
                "JIRA_BASE_URL",
                "JIRA_API_TOKEN",
            )
            if not os.getenv(name)
        ]
        jira_auth_method = os.getenv("JIRA_AUTH_METHOD", "basic").lower()
        if jira_auth_method not in {"basic", "bearer"}:
            raise ValueError("JIRA_AUTH_METHOD doit valoir 'basic' ou 'bearer'")
        jira_rest_api_version = os.getenv("JIRA_REST_API_VERSION", "2")
        if jira_rest_api_version not in {"2", "3"}:
            raise ValueError("JIRA_REST_API_VERSION doit valoir '2' ou '3'")
        if jira_auth_method == "basic" and not _jira_username():
            missing.append("JIRA_USERNAME")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Variables d'environnement manquantes: {joined}")

        categories = os.getenv("RESPRINT_DONE_STATUS_CATEGORIES", "done")
        min_seconds = int(os.getenv("RESPRINT_MIN_SECONDS", "1"))
        worklog_source = os.getenv("RESPRINT_WORKLOG_SOURCE", "jira").lower()
        if worklog_source not in {"jira", "tempo"}:
            raise ValueError("RESPRINT_WORKLOG_SOURCE doit valoir 'jira' ou 'tempo'")
        tempo_api_token = os.getenv("TEMPO_API_TOKEN") or None
        if worklog_source == "tempo" and not tempo_api_token:
            raise ValueError(
                "TEMPO_API_TOKEN est requis avec la source de temps 'tempo'"
            )
        log_level = os.getenv("RESPRINT_LOG_LEVEL", "error").lower()
        if log_level not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError(
                "RESPRINT_LOG_LEVEL doit valoir 'debug', 'info', 'warning', "
                "'error' ou 'critical'"
            )

        return cls(
            jira_base_url=os.environ["JIRA_BASE_URL"].rstrip("/"),
            jira_username=_jira_username(),
            jira_api_token=os.environ["JIRA_API_TOKEN"],
            jira_auth_method=jira_auth_method,
            jira_rest_api_version=jira_rest_api_version,
            jira_project_key=os.getenv("JIRA_PROJECT_KEY") or None,
            tempo_api_token=tempo_api_token,
            worklog_source=worklog_source,
            done_status_categories=frozenset(
                item.strip().lower() for item in categories.split(",") if item.strip()
            ),
            min_seconds=min_seconds,
            parent_field=(
                os.getenv("RESPRINT_PARENT_FIELD")
                or os.getenv("RESPRINT_EPIC_FIELD")
                or None
            ),
            log_level=log_level,
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


def _jira_username() -> str | None:
    return os.getenv("JIRA_USERNAME") or os.getenv("JIRA_EMAIL")
