from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomli

from resprint.durations import DEFAULT_HOURS_PER_DAY, validate_hours_per_day
from resprint.logging import get_logger

logger = get_logger(__name__)


# Load secret values from a .env file (no override)
def load_env(path: str = ".env") -> None:
    """Load secret environment variables from a .env file."""
    from dotenv import load_dotenv

    logger.debug("Checking dotenv configuration")
    if os.path.exists(path):
        load_dotenv(path, override=False)
        logger.debug("Loaded dotenv values without overriding the environment")


# Load mandatory configuration from setting.toml
def load_toml(path: str = "setting.toml") -> dict:
    """Read the optional TOML configuration file.

    The function looks for *path* relative to the current working directory.
    If the file does not exist, it returns an empty dictionary – callers then
    rely on environment variables or defaults.
    """
    logger.debug("Loading TOML configuration")
    toml_path = Path(path)
    if not toml_path.is_file():
        logger.debug("No TOML configuration file found")
        return {}
    with toml_path.open("rb") as f:
        configuration = tomli.load(f)
    logger.debug("Loaded TOML configuration")
    return configuration


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
    jira_ca_bundle: str | None
    done_status_categories: frozenset[str]
    min_seconds: int
    parent_field: str | None
    log_level: str
    language: str = "fr"
    out_of_sprint_analysis: bool = False
    request_concurrency: int = 4
    jira_issue_request_timeout: float = 10
    ignored_changelog_fields: frozenset[str] = DEFAULT_IGNORED_CHANGELOG_FIELDS
    excluded_issue_keys: frozenset[str] = frozenset()

    review_fields: tuple[str, ...] = ()
    phorge_base_url: str | None = None
    phorge_api_token: str | None = None
    phorge_ca_bundle: str | None = None
    phorge_enabled_in_config: bool = False
    review_min_validations: int = 2
    review_max_pending_required_approvals: int = 0
    hours_per_day: float = DEFAULT_HOURS_PER_DAY

    @property
    def reviews_enabled(self) -> bool:
        return bool(
            self.phorge_enabled_in_config
            and self.review_fields
            and self.phorge_base_url
            and self.phorge_api_token
        )

    @classmethod
    def from_sources(cls) -> Settings:
        logger.debug("Loading runtime settings")
        # Load secrets from .env and configuration from setting.toml
        load_env()
        cfg = load_toml()

        # Secrets – only from environment variables
        missing = []
        if not os.getenv("JIRA_API_TOKEN"):
            missing.append("JIRA_API_TOKEN")

        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

        # Configuration – only from the TOML file (mandatory)
        def _toml_get(
            section: str, key: str, *, required: bool = True, default: object = None
        ) -> object:
            table = cfg.get(section, {})
            if key in table:
                return table[key]
            if required:
                raise ValueError(
                    f"{key.upper()} is required in the [{section}] section of "
                    "setting.toml"
                )
            return default

        # Jira configuration
        jira_base_url = _toml_get("jira", "base_url")

        jira_rest_api_version = str(
            _toml_get("jira", "rest_api_version", required=False, default="2")
        )
        if jira_rest_api_version not in {"2", "3"}:
            raise ValueError("JIRA_REST_API_VERSION must be '2' or '3'")

        jira_project_key = _toml_get("jira", "project_key", required=False)
        jira_ca_bundle = _toml_get("jira", "ca_bundle", required=False)

        # --- Resprint configuration --------------------------------------------
        categories = _toml_get(
            "resprint", "done_status_categories", required=False, default=["done"]
        )
        # Ensure we have an iterable of strings
        if isinstance(categories, str):
            categories = [categories]
        done_status_categories = frozenset(
            str(item).strip().lower() for item in categories if str(item).strip()
        )

        hours_per_day = validate_hours_per_day(
            _toml_get(
                "resprint",
                "hours_per_day",
                required=False,
                default=DEFAULT_HOURS_PER_DAY,
            )
        )
        min_seconds = int(
            _toml_get("resprint", "min_seconds", required=False, default=1)
        )

        log_level = str(
            _toml_get("resprint", "log_level", required=False, default="warning")
        ).lower()
        if log_level not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError(
                "RESPRINT_LOG_LEVEL must be "
                "'debug', 'info', 'warning', 'error' or 'critical'"
            )

        language = str(
            _toml_get("resprint", "language", required=False, default="fr")
        ).lower()
        if language not in {"fr", "en"}:
            raise ValueError("RESPRINT_LANGUAGE must be 'fr' or 'en'")

        out_of_sprint_analysis = _toml_bool(
            _toml_get(
                "resprint",
                "out_of_sprint_analysis",
                required=False,
                default=False,
            ),
            "RESPRINT_OUT_OF_SPRINT_ANALYSIS",
        )

        request_concurrency = int(
            _toml_get("resprint", "request_concurrency", required=False, default=4)
        )
        if request_concurrency < 1:
            raise ValueError("RESPRINT_REQUEST_CONCURRENCY must be at least 1")

        jira_issue_request_timeout_raw = _toml_get(
            "resprint",
            "jira_issue_request_timeout",
            required=False,
            default=10,
        )
        try:
            jira_issue_request_timeout = float(jira_issue_request_timeout_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "RESPRINT_JIRA_ISSUE_REQUEST_TIMEOUT must be a positive number"
            ) from exc
        if jira_issue_request_timeout <= 0:
            raise ValueError(
                "RESPRINT_JIRA_ISSUE_REQUEST_TIMEOUT must be a positive number"
            )

        ignored_raw = _toml_get("resprint", "ignored_changelog_fields", required=False)
        if isinstance(ignored_raw, list):
            # Convert list to comma‑separated string for the existing helper
            ignored_raw = ",".join(ignored_raw)
        ignored_changelog_fields = _csv_frozenset(
            ignored_raw,
            DEFAULT_IGNORED_CHANGELOG_FIELDS,
        )

        excluded_raw = _toml_get("resprint", "excluded_issue_keys", required=False)
        if isinstance(excluded_raw, list):
            excluded_raw = ",".join(excluded_raw)
        excluded_issue_keys = _csv_frozenset(excluded_raw, frozenset())

        # Parent field – read exclusively from the TOML configuration.
        # It is now an optional value; if omitted the attribute will be ``None``.
        parent_field = _toml_get("resprint", "parent_field", required=False)

        phorge = cfg.get("phorge", {})
        enabled = _toml_bool(phorge.get("enabled", False), "PHORGE_ENABLED")
        min_validations = _nonnegative_int(
            phorge.get("ready_to_close_min_validations", 2),
            "[phorge] ready_to_close_min_validations",
        )
        max_pending = _nonnegative_int(
            phorge.get("ready_to_close_max_pending_required_approvals", 0),
            "[phorge] ready_to_close_max_pending_required_approvals",
        )
        fields = phorge.get("jira_fields", [])
        if isinstance(fields, str):
            fields = [fields]
        if not isinstance(fields, list) or any(not isinstance(x, str) for x in fields):
            raise ValueError("[phorge] jira_fields must contain strings")
        fields = tuple(dict.fromkeys(x.strip() for x in fields if x.strip()))
        for key in ("base_url", "ca_bundle"):
            if key in phorge and not isinstance(phorge[key], str):
                raise ValueError(f"[phorge] {key} must be a string")
        url = (phorge.get("base_url") or "").strip().rstrip("/") or None
        token = os.getenv("PHORGE_API_TOKEN") or None
        if enabled and not (fields and url and token):
            logger.warning(
                "Phorge disabled: missing jira_fields, base_url or PHORGE_API_TOKEN"
            )
        settings = cls(
            review_fields=fields,
            phorge_base_url=url,
            phorge_api_token=token,
            phorge_ca_bundle=phorge.get("ca_bundle"),
            phorge_enabled_in_config=enabled,
            review_min_validations=min_validations,
            review_max_pending_required_approvals=max_pending,
            jira_base_url=jira_base_url.rstrip("/"),
            jira_api_token=os.getenv("JIRA_API_TOKEN"),
            jira_rest_api_version=jira_rest_api_version,
            jira_project_key=jira_project_key,
            jira_ca_bundle=jira_ca_bundle,
            done_status_categories=done_status_categories,
            min_seconds=min_seconds,
            parent_field=parent_field,
            log_level=log_level,
            language=language,
            hours_per_day=hours_per_day,
            out_of_sprint_analysis=out_of_sprint_analysis,
            request_concurrency=request_concurrency,
            jira_issue_request_timeout=jira_issue_request_timeout,
            ignored_changelog_fields=ignored_changelog_fields,
            excluded_issue_keys=excluded_issue_keys,
        )
        logger.debug(
            "Settings validated language=%s concurrency=%s reviews_enabled=%s",
            settings.language,
            settings.request_concurrency,
            settings.reviews_enabled,
        )
        return settings


def _csv_frozenset(value: str | None, default: frozenset[str]) -> frozenset[str]:
    if value is None:
        return default
    return frozenset(
        item.strip().casefold() for item in value.split(",") if item.strip()
    )


def _toml_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean")


def _nonnegative_int(value: object, name: str) -> int:
    """Validate a TOML integer threshold without coercing booleans or floats."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
