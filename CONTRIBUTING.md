# Contributing to ReSprint

[Back to README](README.md)

Bug reports, documentation improvements and pull requests are welcome. Use the
[issue tracker](https://github.com/nico97118/ReSprint/issues) to describe a
problem or discuss a feature. Include reproduction steps, expected and actual
behavior, and relevant Jira/Tempo/Phorge versions. Remove credentials and private
service data from examples.

## Development setup

Use Python 3.11 or later, [uv](https://docs.astral.sh/uv/) and Node.js/npm.
The default Python version is 3.13; CI uses Node.js 22 for frontend checks.
From the repository root:

```bash
uv sync --dev --locked
npm ci
uv run --locked resprint --demo
```

The demo and automated tests need no production credentials. See
[demo fixtures](docs/demo.md) for the dataset, supported JQL and standalone
fixture commands.

## Python checks

```bash
uv run --locked ruff format --check
uv run --locked ruff check
uv run --locked pytest
```

Use `uv run --locked ruff format` to apply formatting. See
[TESTING.md](TESTING.md) for suite selection, fixtures, browser and Docker
infrastructure, coverage, CI and troubleshooting.

## Frontend assets

Third-party assets are committed under `src/resprint/frontend/static/vendor/`.
Application CSS/JavaScript is minified under `src/resprint/frontend/static/min/`.
Neither npm nor a CDN is required to run the application.

After changing frontend sources, asset dependencies or build scripts:

```bash
npm run assets
npm run minify:check
```

Commit generated assets with their source changes. `npm run vendor` refreshes
third-party assets; `npm run minify` regenerates application assets. CI checks
minified-file consistency without modifying the repository.

## Git hooks and pull requests

```bash
uv run --locked pre-commit install
uv run --locked pre-commit run --all-files
```

Hooks check Ruff, pytest and minified assets when relevant frontend files change.
They also prevent committing `.env`.

Keep changes focused, explain their user-visible effect and include relevant
validation. Add regression coverage for behavior changes and update documentation
when commands or configuration change. Run the relevant suites described in
[TESTING.md](TESTING.md) before submitting a pull request.

## Code organization

| Module | Responsibility |
| --- | --- |
| `resprint.models`, `resprint.analysis` | Domain models and issue classification. |
| `resprint.helpers` | Jira, Tempo and Phorge clients and identity helpers. |
| `resprint.report`, `resprint.reviews` | Report construction and review snapshots. |
| `resprint.exporters` | Markdown and JSON output. |
| `resprint.frontend` | Flask application, HTML rendering, templates and assets. |
| `resprint.cli` | Command-line entry point. |
| `resprint.demo` | Local API fixtures and demo lifecycle. |

Domain modules do not depend on Flask or HTML rendering. Network clients are
isolated in helpers; the frontend consumes analyzed domain objects.

Contributions are submitted under the project's [Apache License 2.0](LICENSE),
unless explicitly stated otherwise. See [AUTHORS.md](AUTHORS.md).
