# Demo fixtures

[Back to README](../README.md)

```bash
uv run --locked --no-dev resprint --demo
# If port 5000 is already in use:
uv run --locked --no-dev resprint --demo --port 5001
```

The command starts the web UI on `127.0.0.1` and local HTTP fixtures on free
loopback ports. It ignores local `settings.toml`, `.env` and production tokens;
all settings and credentials are fictional and held in memory. Ctrl+C or
SIGTERM stops the web server and both fixture services. Nothing is written to
the working directory. The demo flag serves the web interface; choose the
report scope in the UI rather than passing CLI export options to `--demo`.

## Dataset

Open `http://127.0.0.1:5000/`, continue from the single demo sprint, select the
Tempo team, and generate a report. Direct links are printed at startup:

- Project **ABC**, board **1**, sprint **456**, Tempo team **42**.
- Participants: Alice Martin, Bob Leroy and Carol Nguyen.
- Sprint dates: **2026-11-02** through **2026-11-13**.
- Direct report: `/report?sprint_id=456&tempo_team_id=42`.

The dataset includes completed, in-progress and not-started tickets, an
out-of-sprint ticket, shared reviews, abandoned and unknown reviews, two
ready-to-close reviews, mandatory approvals pending and requested changes.
**ABC-8** has no period worklog and is absent from displayed ticket categories,
but its review **D108** is still analysed. **ABC-12** has 121 worklogs and three
comments to exercise pagination. Review and Jira links open small local fixture
pages; they never redirect to a real instance.

## Supported JQL

Period/JQL reports can use the same dates and participants. Supported demo JQL
is deliberately limited to `project = ABC`, `sprint = 456`, `key in (...)`
(or `issue in (...)`), combinations with `AND`, and an optional `ORDER BY key`.
Unsupported queries return an explicit HTTP 400 instead of pretending to apply
filters. The fixture models REST API v2/v3 and the Data Center Tempo endpoints
used by ReSprint; it does not implement all Jira or Phorge capabilities.

## Use fixtures in development

See [TESTING.md](../TESTING.md) for automated test infrastructure and commands.

Tests can reuse `resprint.demo.demo_services()` as a context manager yielding
isolated `Settings`, with the real clients and report builder. For standalone
fixtures or container tests:

```bash
uv run --locked --no-dev python -m resprint.demo.mock_jira --port 8000
uv run --locked --no-dev python -m resprint.demo.mock_phorge --port 8001
```

The Jira fixture also serves Tempo. Its expected Jira token and the Phorge
fixture token are both `resprint-demo`. The review field is
`customfield_reviews`. The Docker smoke test uses these same fixtures to check
a full report and CLI export without external services.
