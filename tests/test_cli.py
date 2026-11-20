from datetime import date

import pytest
import requests

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
            "--tempo-worker",
            "alice.tempo",
        ]
    )

    _validate_args(parser, args)


def test_cli_requires_tempo_selection_outside_serve() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
        ]
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_args(parser, args)

    assert exc_info.value.code == 2


def test_cli_accepts_repeated_tempo_workers() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
            "--tempo-worker",
            "alice.tempo",
            "--tempo-worker",
            "bob.tempo",
        ]
    )

    assert args.tempo_worker == ["alice.tempo", "bob.tempo"]


def test_cli_serve_does_not_require_sprint_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        jira_base_url="https://jira.example.test",
        jira_api_token="token",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        jira_ca_bundle=None,
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
        ignored_changelog_fields=frozenset({"worklogid", "timeestimate", "timespent"}),
    )
    run_calls: list[dict[str, object]] = []

    class FakeApp:
        def run(self, **kwargs: object) -> None:
            run_calls.append(kwargs)

    monkeypatch.setattr("resprint.cli.Settings.from_sources", lambda: settings)
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


def test_cli_logs_request_errors_with_clean_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        jira_base_url="https://jira.example.test",
        jira_api_token="token",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        jira_ca_bundle=None,
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
        ignored_changelog_fields=frozenset({"worklogid", "timeestimate", "timespent"}),
    )
    response = requests.Response()
    response.status_code = 504

    def build_report(*args: object, **kwargs: object) -> object:
        raise requests.HTTPError("Gateway timeout", response=response)

    monkeypatch.setattr("resprint.cli.Settings.from_sources", lambda: settings)
    monkeypatch.setattr("resprint.cli.build_report", build_report)

    exit_code = main(["--sprint-id", "456", "--tempo-worker", "alice"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: HTTPError: status=504" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("output_format", ["json", "markdown", "html"])
@pytest.mark.parametrize("to_file", [False, True])
def test_cli_exports_real_report_to_stdout_or_utf8_file(
    monkeypatch, tmp_path, capsys, output_format, to_file
):
    import json

    from resprint.models import Issue, IssueReviewItem, Sprint, SprintReview
    from resprint.report import ReportContext

    settings = Settings(
        jira_base_url="https://jira.example.test",
        jira_api_token="token",
        jira_rest_api_version="2",
        jira_project_key="ABC",
        jira_ca_bundle=None,
        done_status_categories=frozenset({"done"}),
        min_seconds=1,
        parent_field=None,
        log_level="error",
    )
    issue = Issue("1", "ABC-1", "Évolution à vérifier", "Done", "done", "Alice")
    context = ReportContext(
        SprintReview((IssueReviewItem(issue, 25200, 25200, 1),), (), ()),
        Sprint(456, "Sprint été", date(2026, 5, 1), date(2026, 5, 15)),
        settings.jira_base_url,
    )
    calls = []

    def build(settings_arg, **kwargs):
        calls.append((settings_arg, kwargs))
        return context

    monkeypatch.setattr("resprint.cli.Settings.from_sources", lambda: settings)
    monkeypatch.setattr("resprint.cli.build_report", build)
    destination = tmp_path / "rapport.txt"
    args = ["--sprint-id", "456", "--tempo-worker", "alice", "--format", output_format]
    if to_file:
        args.extend(["--output", str(destination)])
    assert main(args) == 0
    captured = capsys.readouterr()
    output = destination.read_text(encoding="utf-8") if to_file else captured.out
    assert "Évolution à vérifier" in output
    assert "Sprint été" in output
    if output_format == "json":
        assert json.loads(output)["completed"][0]["key"] == "ABC-1"
    elif output_format == "html":
        assert "<!doctype html>" in output
    else:
        assert "ABC-1" in output and "1.00 j" in output
    if to_file:
        assert captured.out == ""
    assert calls[0][0] is settings
    assert calls[0][1]["tempo_worker_keys"] == ("alice",)


def test_cli_configuration_failure_returns_actionable_error(monkeypatch, capsys):
    def invalid_settings():
        raise ValueError("Missing JIRA_API_TOKEN")

    monkeypatch.setattr("resprint.cli.Settings.from_sources", invalid_settings)
    assert main(["--sprint-id", "456", "--tempo-worker", "alice"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: Missing JIRA_API_TOKEN" in captured.err
    assert "Traceback" not in captured.err
