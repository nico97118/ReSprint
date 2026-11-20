from resprint.frontend.wsgi import create_application


def test_wsgi_factory_loads_runtime_configuration_without_remote_calls(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    (tmp_path / "setting.toml").write_text(
        '[jira]\nbase_url = "http://127.0.0.1:9"\n'
        '[resprint]\nhours_per_day = 7.5\nlanguage = "en"\n'
    )
    app = create_application()
    client = app.test_client()
    assert client.get("/healthz").data == b"ok"
    assert client.get("/assets/min/table.min.js").status_code == 200
    assert client.get("/report").status_code == 400
