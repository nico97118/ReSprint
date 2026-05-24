from datetime import date

import pytest

from resprint.cli import _build_parser, _validate_args, main
from resprint.config import Settings
from resprint.report import _resolve_sprint


class UnusedJiraClient:
    def get_sprint(self, sprint_id: int) -> None:
        raise AssertionError(f"Unexpected agile sprint lookup for {sprint_id}")


def test_resolve_sprint_uses_cli_dates_without_agile_lookup() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
            "--sprint-start",
            "2026-05-01",
            "--sprint-end",
            "2026-05-15",
            "--sprint-name",
            "Sprint 42",
        ]
    )

    sprint = _resolve_sprint(
        UnusedJiraClient(),
        args.sprint_id,
        args.sprint_start,
        args.sprint_end,
        args.sprint_name,
    )

    assert sprint.id == 456
    assert sprint.name == "Sprint 42"
    assert sprint.start_date == date(2026, 5, 1)
    assert sprint.end_date == date(2026, 5, 15)


def test_resolve_sprint_requires_start_and_end_together() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
            "--sprint-start",
            "2026-05-01",
        ]
    )

    with pytest.raises(ValueError, match="sprint-start"):
        _resolve_sprint(
            UnusedJiraClient(),
            args.sprint_id,
            args.sprint_start,
            args.sprint_end,
            args.sprint_name,
        )


def test_cli_requires_sprint_id_outside_serve() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2


def test_cli_accepts_jql_period_without_sprint_id() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--jql",
            "project = ABC",
            "--sprint-start",
            "2026-05-01",
            "--sprint-end",
            "2026-05-15",
        ]
    )

    _validate_args(parser, args)


def test_cli_rejects_board_without_sprint_id() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--jql",
            "project = ABC",
            "--sprint-start",
            "2026-05-01",
            "--sprint-end",
            "2026-05-15",
            "--board-id",
            "123",
        ]
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_args(parser, args)

    assert exc_info.value.code == 2


def test_cli_serve_does_not_require_sprint_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        jira_base_url="https://jira.example.test",
        jira_username="prenom.nom",
        jira_api_token="token",
        jira_auth_method="basic",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        tempo_api_token=None,
        worklog_source="jira",
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
    )
    run_calls: list[dict[str, object]] = []

    class FakeApp:
        def run(self, **kwargs: object) -> None:
            run_calls.append(kwargs)

    monkeypatch.setattr("resprint.cli.Settings.from_env", lambda: settings)
    monkeypatch.setattr("resprint.cli.create_app", lambda _settings: FakeApp())

    assert main(["--serve"]) == 0
    assert run_calls == [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "debug": False,
            "use_reloader": False,
        }
    ]
