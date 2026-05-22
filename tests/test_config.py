import os

import pytest

from resprint.config import Settings


def test_settings_accepts_jira_username_without_tempo_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os.path, "exists", lambda _path: False)
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.test")
    monkeypatch.setenv("JIRA_USERNAME", "prenom.nom")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("JIRA_AUTH_METHOD", raising=False)
    monkeypatch.delenv("JIRA_REST_API_VERSION", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("TEMPO_API_TOKEN", raising=False)
    monkeypatch.delenv("RESPRINT_WORKLOG_SOURCE", raising=False)
    monkeypatch.setenv("JIRA_PROJECT_KEY", "ABC")

    settings = Settings.from_env()

    assert settings.jira_username == "prenom.nom"
    assert settings.jira_auth_method == "basic"
    assert settings.jira_rest_api_version == "2"
    assert settings.tempo_api_token is None
    assert settings.worklog_source == "jira"
    assert settings.jira_project_key == "ABC"


def test_settings_requires_tempo_token_for_tempo_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os.path, "exists", lambda _path: False)
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.test")
    monkeypatch.setenv("JIRA_USERNAME", "prenom.nom")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("JIRA_AUTH_METHOD", raising=False)
    monkeypatch.delenv("JIRA_REST_API_VERSION", raising=False)
    monkeypatch.setenv("RESPRINT_WORKLOG_SOURCE", "tempo")
    monkeypatch.delenv("TEMPO_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TEMPO_API_TOKEN"):
        Settings.from_env()


def test_settings_accepts_bearer_auth_without_username(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os.path, "exists", lambda _path: False)
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.setenv("JIRA_AUTH_METHOD", "bearer")
    monkeypatch.setenv("JIRA_REST_API_VERSION", "3")
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("TEMPO_API_TOKEN", raising=False)
    monkeypatch.delenv("RESPRINT_WORKLOG_SOURCE", raising=False)

    settings = Settings.from_env()

    assert settings.jira_username is None
    assert settings.jira_auth_method == "bearer"
    assert settings.jira_rest_api_version == "3"
