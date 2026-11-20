"""Integration coverage using actual HTTP clients, local fixtures and the CLI."""

import json
import os
import queue
import signal
import socket
import subprocess
import sys
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
import requests

from resprint.cli import main
from resprint.demo import REPORT_PATH, demo_services
from resprint.demo.data import END_DATE, START_DATE, TOKEN
from resprint.frontend.app import create_app
from resprint.frontend.i18n import configure_language, current_language
from resprint.report import build_report

pytestmark = pytest.mark.integration


class JsonExport(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        self.inside = tag == "script" and dict(attrs).get("id") == "report-export-json"

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.data += data


@pytest.fixture
def services():
    previous = current_language()
    try:
        with demo_services() as settings:
            yield settings
    finally:
        configure_language(previous)


def test_demo_covers_complete_sprint_flow_and_review_scenarios(services):
    client = create_app(services).test_client()
    home = client.get("/")
    assert home.status_code == 200
    assert "Sprint de démonstration" in home.text
    participants = client.get("/participants?sprint_id=456&tempo_team_id=42")
    assert participants.status_code == 200
    assert "Alice Martin" in participants.text
    assert "Bob Leroy" in participants.text
    assert "Carol Nguyen" in participants.text
    response = client.get(REPORT_PATH)
    assert response.status_code == 200
    assert "issue-review-warning" in response.text
    assert "À clôturer" in response.text
    assert "Équipe architecture" in response.text
    assert "review-decision-changes_requested" in response.text
    assert "1.00 j" in response.text
    parser = JsonExport()
    parser.feed(response.text)
    data = json.loads(parser.data)
    assert {item["key"] for item in data["completed"]} == {
        "ABC-1",
        "ABC-4",
        "ABC-10",
        "ABC-12",
    }
    assert {item["key"] for item in data["not_started"]} == {"ABC-5"}
    assert {item["key"] for item in data["out_of_sprint"]} == {"ABC-11"}
    heavy = next(item for item in data["completed"] if item["key"] == "ABC-12")
    assert heavy["total_seconds"] == 111600  # 120 paged entries plus one earlier entry.
    assert len(heavy["comments"]) == 3  # Two comment pages.
    assert heavy["changes"][0]["field"] == "status"
    reviews = {item["id"]: item for item in data["code_reviews"]["items"]}
    assert set(reviews) == {101, 102, 103, 104, 105, 106, 108, 109}
    assert reviews[101]["issue_keys"] == ["ABC-1", "ABC-10"]
    assert reviews[102]["ready_to_close"] is True
    assert reviews[103]["pending_required_approval_count"] == 1
    assert reviews[103]["ready_to_close"] is False
    assert reviews[105]["state"] == "abandoned"
    assert reviews[108]["issue_keys"] == [
        "ABC-8"
    ]  # Not in a displayed ticket category.
    assert reviews[109]["state"] == "unknown"
    assert reviews[101]["author_name"] == "Alice Martin"
    assert {item["repository"] for item in reviews.values()} == {"core", "web", None}


def test_demo_supports_period_worker_selection_and_configured_thresholds(services):
    from datetime import date

    configured = replace(
        services, review_min_validations=2, review_max_pending_required_approvals=1
    )
    report = build_report(
        configured,
        jql="sprint = 456",
        sprint_start=date.fromisoformat(START_DATE),
        sprint_end=date.fromisoformat(END_DATE),
        tempo_worker_keys=("bob",),
    )
    assert report.participants == ("Bob Leroy",)
    reviews = {item["id"]: item for item in report.code_reviews["items"]}
    assert reviews[103]["ready_to_close"] is True
    heavy = next(item for item in report.review.completed if item.issue.key == "ABC-12")
    assert heavy.tempo_seconds == 54000  # Bob logged half the period work.


def test_fixture_authentication_and_unsupported_queries(services):
    assert (
        requests.get(
            services.jira_base_url + "/rest/api/2/serverInfo", timeout=3
        ).status_code
        == 401
    )
    response = requests.get(
        services.jira_base_url + "/rest/api/2/search",
        headers={"Authorization": f"Bearer {TOKEN}"},
        params={"jql": "invalid jql"},
        timeout=3,
    )
    assert response.status_code == 400
    assert (
        requests.post(
            services.phorge_base_url + "/api/differential.query", timeout=3
        ).status_code
        == 401
    )
    response = requests.post(
        services.phorge_base_url + "/api/differential.revision.edit",
        data={"api.token": TOKEN},
        timeout=3,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_installed_demo_ignores_local_configuration_and_shuts_down(
    tmp_path, stop_signal
):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    # These would fail normal startup; --demo must never read either file.
    (tmp_path / "settings.toml").write_text("invalid production configuration")
    (tmp_path / ".env").write_text("JIRA_API_TOKEN=do-not-use\n")
    env = os.environ | {
        "JIRA_API_TOKEN": "do-not-use",
        "PHORGE_API_TOKEN": "do-not-use",
    }
    process = subprocess.Popen(
        [
            str(Path(sys.executable).with_name("resprint")),
            "--demo",
            "--port",
            str(port),
        ],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines = queue.Queue()

    def read_output():
        for line in process.stdout:
            lines.put(line)
        lines.put("EXIT")

    reader = Thread(target=read_output, daemon=True)
    reader.start()
    ports = {port}
    try:
        while True:
            line = lines.get(timeout=15)
            assert line != "EXIT", "Demo exited before startup"
            if line.startswith("ReSprint demo ready at "):
                break
        response = requests.get(f"http://127.0.0.1:{port}" + REPORT_PATH, timeout=15)
        response.raise_for_status()
        parser = JsonExport()
        parser.feed(response.text)
        reviews = json.loads(parser.data)["code_reviews"]["items"]
        assert reviews[0]["author_name"] == "Alice Martin"
        ports.add(urlsplit(reviews[0]["url"]).port)
        process.send_signal(stop_signal)
        assert process.wait(timeout=10) == 128 + stop_signal
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=2)
        process.stdout.close()
    assert (
        tmp_path / "settings.toml"
    ).read_text() == "invalid production configuration"
    assert (tmp_path / ".env").read_text() == "JIRA_API_TOKEN=do-not-use\n"
    assert {p.name for p in tmp_path.iterdir()} == {"settings.toml", ".env"}
    for released in ports:
        with socket.socket() as connection:
            assert connection.connect_ex(("127.0.0.1", released)) != 0


@pytest.mark.parametrize("port", ["0", "65536"])
def test_demo_rejects_invalid_port(port, capsys):
    assert main(["--demo", "--port", port]) == 2
    assert "choose a port" in capsys.readouterr().err


def test_demo_rejects_nonlocal_host():
    with pytest.raises(SystemExit) as error:
        main(["--demo", "--host", "0.0.0.0"])
    assert error.value.code == 2


def test_demo_does_not_silently_ignore_scope_options():
    with pytest.raises(SystemExit) as error:
        main(["--demo", "--sprint-id", "456"])
    assert error.value.code == 2


def test_fixture_context_releases_ports_on_failure():
    ports = []
    with pytest.raises(RuntimeError, match="test failure"):
        with demo_services() as settings:
            ports = [
                urlsplit(settings.jira_base_url).port,
                urlsplit(settings.phorge_base_url).port,
            ]
            raise RuntimeError("test failure")
    for port in ports:
        with socket.socket() as connection:
            assert connection.connect_ex(("127.0.0.1", port)) != 0


def test_demo_handles_occupied_port_and_restores_signal_handlers(capsys):
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        assert main(["--demo", "--port", str(listener.getsockname()[1])]) == 1
    assert "demo ready" not in capsys.readouterr().out
    assert {sig: signal.getsignal(sig) for sig in original} == original


def test_report_info_logs_cover_operational_stages_in_order(services, caplog):
    client = create_app(services).test_client()
    with caplog.at_level("INFO", logger="resprint"):
        response = client.get(REPORT_PATH)
    assert response.status_code == 200
    records = [
        record for record in caplog.records if record.name.startswith("resprint")
    ]
    stages = [
        "Generating web report",
        "Building report",
        "Loading issue activity",
        "Tempo worker search returned",
        "Loading Phorge review snapshot",
        "Phorge snapshot completed",
        "Report context built",
        "Rendering HTML report",
        "Web request completed endpoint=report status=200",
    ]
    positions = [
        next(i for i, r in enumerate(records) if stage in r.message) for stage in stages
    ]
    assert positions == sorted(positions)
    assert all(records[i].levelname == "INFO" for i in positions)
    assert all(record.levelname != "ERROR" for record in records)
    assert "elapsed_ms=" in records[positions[-1]].message
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "reason, code", [(None, 0), (KeyboardInterrupt(), 130), (SystemExit(143), 143)]
)
def test_demo_lifecycle_logs_readiness_and_graceful_shutdown(
    monkeypatch, caplog, reason, code
):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from resprint.demo import run_demo

    @contextmanager
    def services():
        yield SimpleNamespace(log_level="info")

    server = Mock()
    server.serve_forever.side_effect = reason
    monkeypatch.setattr("resprint.demo.demo_services", services)
    monkeypatch.setattr("resprint.demo.create_app", lambda _: object())
    monkeypatch.setattr("resprint.demo.make_server", lambda *a, **kw: server)
    with caplog.at_level("INFO", logger="resprint"):
        assert run_demo(8765) == code
    assert "Demo server ready" in caplog.text
    assert "Demo server closed" in caplog.text
    assert all(record.levelname != "ERROR" for record in caplog.records)
    server.server_close.assert_called_once()
