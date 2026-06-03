import os
from pathlib import Path

import pytest

from resprint.config import DEFAULT_IGNORED_CHANGELOG_FIELDS, Settings, load_env


def write_setting_toml(tmp_dir: Path, **overrides: str) -> None:
    """Write a complete ``setting.toml`` into ``tmp_dir``.

    ``overrides`` is a mapping of fully‑qualified TOML keys (e.g.
    ``"jira.base_url"``) to the desired value. Values are written using the
    appropriate TOML syntax (strings are quoted, lists are rendered with
    brackets, etc.).
    """
    # Default configuration – non‑secret values only.
    defaults = {
        "jira.base_url": "https://jira.example.test",
        "jira.auth_method": "basic",
        "jira.rest_api_version": "2",
        "jira.project_key": None,
        "jira.ca_bundle": None,
        "resprint.done_status_categories": ["done"],
        "resprint.min_seconds": 1,
        "resprint.log_level": "error",
        "resprint.language": "fr",
        "resprint.out_of_sprint_analysis": False,
        "resprint.request_concurrency": 4,
        "resprint.jira_issue_request_timeout": 10,
        "resprint.parent_field": None,
        "resprint.ignored_changelog_fields": None,
        "resprint.excluded_issue_keys": None,
    }
    # Apply any test‑specific overrides.
    defaults.update(overrides)

    lines: list[str] = ["[jira]"]
    for key in (
        "base_url",
        "auth_method",
        "rest_api_version",
        "project_key",
        "ca_bundle",
    ):
        val = defaults.get(f"jira.{key}")
        if val is None:
            continue
        lines.append(f'{key} = "{val}"')

    lines.append("\n[resprint]")
    for key in (
        "log_level",
        "language",
        "min_seconds",
        "out_of_sprint_analysis",
        "request_concurrency",
        "jira_issue_request_timeout",
    ):
        val = defaults.get(f"resprint.{key}")
        if isinstance(val, str):
            lines.append(f'{key} = "{val}"')
        elif isinstance(val, bool):
            lines.append(f"{key} = {str(val).lower()}")
        else:
            lines.append(f"{key} = {val}")

    # Optional list values.
    if defaults["resprint.done_status_categories"]:
        cats = ", ".join(f'"{c}"' for c in defaults["resprint.done_status_categories"])
        lines.append(f"done_status_categories = [{cats}]")
    if defaults["resprint.ignored_changelog_fields"]:
        ignored = ", ".join(
            f'"{c}"' for c in defaults["resprint.ignored_changelog_fields"]
        )
        lines.append(f"ignored_changelog_fields = [{ignored}]")
    if defaults["resprint.excluded_issue_keys"]:
        excluded = ", ".join(f'"{c}"' for c in defaults["resprint.excluded_issue_keys"])
        lines.append(f"excluded_issue_keys = [{excluded}]")
    if defaults["resprint.parent_field"]:
        lines.append(f'parent_field = "{defaults["resprint.parent_field"]}"')

    (tmp_dir / "setting.toml").write_text("\n".join(lines))


@pytest.fixture(autouse=True)
def isolate_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Work inside a temporary directory for every test.
    monkeypatch.chdir(tmp_path)
    # Initialise a full ``setting.toml`` with defaults.
    write_setting_toml(tmp_path)
    # Ensure ``load_env`` does not accidentally read a real ``.env`` file.
    monkeypatch.setattr(os.path, "exists", lambda _path: False)


def test_settings_accepts_jira_username_without_tempo_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Secrets (read from the environment)
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    # The project key is also required in the TOML for the non‑secret path.
    write_setting_toml(
        Path.cwd(),
        **{"jira.project_key": "ABC"},
    )

    settings = Settings.from_sources()

    assert settings.jira_rest_api_version == "2"
    assert settings.jira_project_key == "ABC"
    assert settings.log_level == "error"
    assert settings.language == "fr"
    assert settings.out_of_sprint_analysis is False
    assert settings.request_concurrency == 4
    assert settings.jira_issue_request_timeout == 10
    assert settings.ignored_changelog_fields == DEFAULT_IGNORED_CHANGELOG_FIELDS
    assert settings.excluded_issue_keys == frozenset()


def test_settings_accepts_bearer_auth_without_username(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Secrets – only the API token is required for bearer auth.
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    # TOML specifies bearer auth, REST version 3 and a debug log level.
    write_setting_toml(
        Path.cwd(),
        **{
            "jira.rest_api_version": "3",
            "resprint.log_level": "debug",
        },
    )

    settings = Settings.from_sources()

    assert settings.jira_rest_api_version == "3"
    assert settings.log_level == "debug"


def test_settings_reads_jira_ca_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(
        Path.cwd(),
        **{"jira.ca_bundle": "/etc/ssl/certs/company-ca.pem"},
    )

    settings = Settings.from_sources()

    assert settings.jira_ca_bundle == "/etc/ssl/certs/company-ca.pem"


def test_settings_reads_parent_field(monkeypatch: pytest.MonkeyPatch) -> None:
    # Secrets needed for Settings.from_sources()
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    # Write the parent field into the TOML configuration.
    write_setting_toml(Path.cwd(), **{"resprint.parent_field": "customfield_10014"})
    settings = Settings.from_sources()
    assert settings.parent_field == "customfield_10014"

    # Override with a different value to ensure the TOML value is used.
    write_setting_toml(Path.cwd(), **{"resprint.parent_field": "customfield_20000"})
    settings = Settings.from_sources()
    assert settings.parent_field == "customfield_20000"


def test_settings_rejects_unknown_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    # Secrets – only the API token is needed for the validation path.
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    # Write an invalid log level directly into the TOML.
    write_setting_toml(
        Path.cwd(),
        **{"resprint.log_level": "trace"},
    )

    with pytest.raises(ValueError, match="RESPRINT_LOG_LEVEL"):
        Settings.from_sources()


def test_settings_rejects_unknown_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.language": "de"})

    with pytest.raises(ValueError, match="RESPRINT_LANGUAGE"):
        Settings.from_sources()


def test_settings_accepts_english_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.language": "en"})

    settings = Settings.from_sources()

    assert settings.language == "en"


def test_settings_reads_out_of_sprint_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.out_of_sprint_analysis": True})

    settings = Settings.from_sources()

    assert settings.out_of_sprint_analysis is True


def test_settings_rejects_non_boolean_out_of_sprint_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.out_of_sprint_analysis": "true"})

    with pytest.raises(ValueError, match="RESPRINT_OUT_OF_SPRINT_ANALYSIS"):
        Settings.from_sources()


def test_settings_reads_request_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.request_concurrency": 8})

    settings = Settings.from_sources()

    assert settings.request_concurrency == 8


def test_settings_rejects_request_concurrency_below_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.request_concurrency": 0})

    with pytest.raises(ValueError, match="RESPRINT_REQUEST_CONCURRENCY"):
        Settings.from_sources()


def test_settings_reads_jira_issue_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.jira_issue_request_timeout": 3.5})

    settings = Settings.from_sources()

    assert settings.jira_issue_request_timeout == 3.5


def test_settings_rejects_non_positive_jira_issue_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.jira_issue_request_timeout": 0})

    with pytest.raises(ValueError, match="RESPRINT_JIRA_ISSUE_REQUEST_TIMEOUT"):
        Settings.from_sources()


def test_settings_rejects_non_numeric_jira_issue_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(Path.cwd(), **{"resprint.jira_issue_request_timeout": "slow"})

    with pytest.raises(ValueError, match="RESPRINT_JIRA_ISSUE_REQUEST_TIMEOUT"):
        Settings.from_sources()


def test_settings_reads_ignored_changelog_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Secrets
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    # Provide the ignored fields list via TOML (list syntax).
    write_setting_toml(
        Path.cwd(),
        **{
            "resprint.ignored_changelog_fields": [
                "worklogId",
                "timeestimate",
                "timespent",
            ]
        },
    )

    settings = Settings.from_sources()
    assert settings.ignored_changelog_fields == frozenset(
        {"worklogid", "timeestimate", "timespent"}
    )


def test_settings_reads_excluded_issue_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    write_setting_toml(
        Path.cwd(),
        **{"resprint.excluded_issue_keys": ["ABC-1", "def-2"]},
    )

    settings = Settings.from_sources()

    assert settings.excluded_issue_keys == frozenset({"abc-1", "def-2"})


def test_load_env_uses_standard_dotenv_syntax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The .env file is now only used for secret values. We test that quoting and
    # standard dotenv syntax are handled correctly.
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "# secret token with spaces",
                'JIRA_API_TOKEN="token with spaces"',
                "# another secret (placeholder)",
                "JIRA_OTHER_SECRET=very-secret",
            )
        ),
        encoding="utf-8",
    )
    # Ensure the environment is clean for the keys we are about to load.
    for name in ("JIRA_API_TOKEN", "JIRA_OTHER_SECRET"):
        monkeypatch.delenv(name, raising=False)

    # Restore real ``os.path.exists``
    # so that ``load_env`` can actually find the temporary .env file.
    monkeypatch.setattr(os.path, "exists", lambda p: Path(p).exists())

    load_env(str(env_file))

    assert os.environ["JIRA_API_TOKEN"] == "token with spaces"
    assert os.environ["JIRA_OTHER_SECRET"] == "very-secret"
