from resprint.frontend.wsgi import create_application


def test_wsgi_factory_loads_runtime_configuration_without_remote_calls(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    (tmp_path / "settings.toml").write_text(
        '[jira]\nbase_url = "http://127.0.0.1:9"\n'
        '[resprint]\nhours_per_day = 7.5\nlanguage = "en"\nlog_level = "info"\n'
    )
    with caplog.at_level("INFO", logger="resprint"):
        app = create_application()
    assert "WSGI application ready" in caplog.text
    client = app.test_client()
    assert client.get("/healthz").data == b"ok"
    assert client.get("/assets/min/table.min.js").status_code == 200
    assert client.get("/report").status_code == 400


def test_wsgi_startup_failure_is_logged_and_preserves_the_exception(
    monkeypatch, caplog
):
    import pytest

    error = ValueError("private configuration contents")

    def fail():
        raise error

    monkeypatch.setattr("resprint.frontend.wsgi.Settings.from_sources", fail)
    with (
        caplog.at_level("INFO", logger="resprint"),
        pytest.raises(ValueError) as raised,
    ):
        create_application()
    assert raised.value is error
    records = [r for r in caplog.records if r.name == "resprint.frontend.wsgi"]
    assert len(records) == 1
    assert records[0].levelname == "ERROR"
    assert "WSGI application startup failed: ValueError" in records[0].message
    assert records[0].exc_info is None
    assert "private configuration contents" not in caplog.text
