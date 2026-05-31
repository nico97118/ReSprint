from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomli


# Load secret values from a .env file (no override)
def load_env(path: str = ".env") -> None:
    """Load secret environment variables from a .env file."""
    from dotenv import load_dotenv

    if os.path.exists(path):
        load_dotenv(path, override=False)


# Load mandatory configuration from setting.toml
def load_toml(path: str = "setting.toml") -> dict:
    """Read the optional TOML configuration file.

    The function looks for *path* relative to the current working directory.
    If the file does not exist, it returns an empty dictionary – callers then
    rely on environment variables or defaults.
    """
    toml_path = Path(path)
    if not toml_path.is_file():
        return {}
    with toml_path.open("rb") as f:
        return tomli.load(f)


DEFAULT_IGNORED_CHANGELOG_FIELDS = frozenset(
    {
        "worklogid",
        "timeestimate",
        "timespent",
    }
)


@dataclass(frozen=True)
class Settings:
    jira_base_url: str
    jira_api_token: str
    jira_rest_api_version: str
    jira_project_key: str | None
    tempo_api_token: str | None
    worklog_source: str
    done_status_categories: frozenset[str]
    min_seconds: int
    parent_field: str | None
    log_level: str
    language: str = "fr"
    ignored_changelog_fields: frozenset[str] = DEFAULT_IGNORED_CHANGELOG_FIELDS

    @classmethod
    def from_sources(cls) -> Settings:
        # Load secrets from .env and configuration from setting.toml
        load_env()
        cfg = load_toml()

        # Secrets – only from environment variables
        missing = []
        if not os.getenv("JIRA_API_TOKEN"):
            missing.append("JIRA_API_TOKEN")

        if missing:
            raise ValueError(
                f"Variables d'environnement manquantes: {', '.join(missing)}"
            )

        # Configuration – only from the TOML file (mandatory)
        def _toml_get(
            section: str, key: str, *, required: bool = True, default: object = None
        ) -> object:
            table = cfg.get(section, {})
            if key in table:
                return table[key]
            if required:
                raise ValueError(
                    f"{key.upper()} is required in the [{section}] section "
                    "of setting.toml"
                )
            return default

        # Jira configuration
        jira_base_url = _toml_get("jira", "base_url")

        jira_rest_api_version = str(
            _toml_get("jira", "rest_api_version", required=False, default="2")
        )
        if jira_rest_api_version not in {"2", "3"}:
            raise ValueError("JIRA_REST_API_VERSION doit valoir '2' ou '3'")

        jira_project_key = _toml_get("jira", "project_key", required=False)

        # --- Resprint configuration --------------------------------------------
        worklog_source = str(
            _toml_get("resprint", "worklog_source", required=False, default="jira")
        ).lower()
        if worklog_source not in {"jira", "tempo"}:
            raise ValueError("RESPRINT_WORKLOG_SOURCE doit valoir 'jira' ou 'tempo'")

        tempo_api_token = os.getenv("TEMPO_API_TOKEN") or None
        if worklog_source == "tempo" and not tempo_api_token:
            raise ValueError(
                "TEMPO_API_TOKEN est requis avec la source de temps 'tempo'"
            )

        categories = _toml_get(
            "resprint", "done_status_categories", required=False, default=["done"]
        )
        # Ensure we have an iterable of strings
        if isinstance(categories, str):
            categories = [categories]
        done_status_categories = frozenset(
            str(item).strip().lower() for item in categories if str(item).strip()
        )

        min_seconds = int(
            _toml_get("resprint", "min_seconds", required=False, default=1)
        )

        log_level = str(
            _toml_get("resprint", "log_level", required=False, default="error")
        ).lower()
        if log_level not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError(
                "RESPRINT_LOG_LEVEL doit valoir"
                "'debug', 'info', 'warning', 'error' ou 'critical'"
            )

        language = str(
            _toml_get("resprint", "language", required=False, default="fr")
        ).lower()
        if language not in {"fr"}:
            raise ValueError("RESPRINT_LANGUAGE doit valoir 'fr'")

        ignored_raw = _toml_get("resprint", "ignored_changelog_fields", required=False)
        if isinstance(ignored_raw, list):
            # Convert list to comma‑separated string for the existing helper
            ignored_raw = ",".join(ignored_raw)
        ignored_changelog_fields = _csv_frozenset(
            ignored_raw,
            DEFAULT_IGNORED_CHANGELOG_FIELDS,
        )

        # Parent field – read exclusively from the TOML configuration.
        # It is now an optional value; if omitted the attribute will be ``None``.
        parent_field = _toml_get("resprint", "parent_field", required=False)

        return cls(
            jira_base_url=jira_base_url.rstrip("/"),
            jira_api_token=os.getenv("JIRA_API_TOKEN"),
            jira_rest_api_version=jira_rest_api_version,
            jira_project_key=jira_project_key,
            tempo_api_token=tempo_api_token,
            worklog_source=worklog_source,
            done_status_categories=done_status_categories,
            min_seconds=min_seconds,
            parent_field=parent_field,
            log_level=log_level,
            language=language,
            ignored_changelog_fields=ignored_changelog_fields,
        )


def _jira_username() -> str | None:
    return os.getenv("JIRA_USERNAME") or os.getenv("JIRA_EMAIL")


def _csv_frozenset(value: str | None, default: frozenset[str]) -> frozenset[str]:
    if value is None:
        return default
    return frozenset(
        item.strip().casefold() for item in value.split(",") if item.strip()
    )
