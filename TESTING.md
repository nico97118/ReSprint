# Testing ReSprint

[README](README.md) · [Contributing](CONTRIBUTING.md)

ReSprint tests run against fakes and local Jira, Tempo and Phorge fixtures.
No production account, token or external service is required. Dependency and
browser installation need network access unless already cached.

## Setup

Run commands from the repository root. Install Python development dependencies
with uv and frontend dependencies with npm:

```bash
uv sync --dev --locked
npm ci
```

Python 3.11 or later is supported; the default interpreter is 3.13. CI uses
Node.js 22. Node.js is also needed by Python tests that execute the frontend
duration formatter. Browser tests additionally require Playwright browsers;
Docker smoke tests require Docker, Bash and host `python3`.

## Test suites

| Suite | Entry points | Infrastructure | Checks |
| --- | --- | --- | --- |
| Python without integration marker | `tests/test_*.py`, excluding `test_demo.py` | Fakes, monkeypatching, temporary files, Flask test clients; Node.js for duration checks | Classification, configuration, client contracts, exports, rendering and error handling. |
| Python integration | [tests/test_demo.py](tests/test_demo.py) | Real HTTP clients, loopback fixture servers, CLI subprocesses | Complete reports, API payloads, pagination, demo lifecycle and isolation. |
| Browser | [tests/e2e/report.spec.js](tests/e2e/report.spec.js) | Playwright browsers and an owned demo process | Navigation, filtering, sorting, charts, details, exports and theme behavior. |
| Docker smoke | [scripts/docker-smoke.sh](scripts/docker-smoke.sh) | Built image, temporary Docker network, Jira/Tempo and Phorge containers | Packaged runtime, assets, web report and CLI export. |

## Python tests

```bash
# Full Python suite
uv run --locked pytest
# Fast feedback without integration fixture servers and demo subprocesses
uv run --locked pytest -m "not integration"
# Real HTTP clients and CLI/demo integration
uv run --locked pytest -m integration
# Focus on one module
uv run --locked pytest tests/test_analyzer.py
```

The `integration` marker is declared in [pyproject.toml](pyproject.toml) and
applied to `tests/test_demo.py`. Flask test clients in other tests exercise
requests in process without starting a listening web server.

Shared autouse fixtures in [tests/conftest.py](tests/conftest.py) restore the
frontend language and root/application logging levels after each test.

### Local service fixtures

[resprint.demo.demo_services](src/resprint/demo/__init__.py) is a context manager
that starts two threaded HTTP services:

- A Jira fixture that also serves Tempo endpoints.
- A Phorge fixture for Differential reviews and identity lookup.

Each binds to a free port on `127.0.0.1`. The context yields isolated `Settings`
containing fixture URLs and fictional credentials. On exit it shuts down the
servers, joins their threads and closes sockets. The context does not load
production configuration or environment credentials.

The same fixture implementations support Python integration tests, the demo
used by Playwright, and Docker smoke tests. See [the demo guide](docs/demo.md)
for the dataset, supported JQL and standalone fixture commands. These fixtures
model the APIs used by ReSprint; they do not establish compatibility with every
deployed Jira, Tempo or Phorge version.

### Coverage

```bash
uv run --locked pytest --cov --cov-report=term-missing --cov-report=html --cov-report=xml
```

Coverage measures all Python modules under `src/resprint`, including demo code
and unimported modules, with branch measurement enabled. The configured gate is
**97% combined statement/branch coverage**. It is not a branch-only threshold.
CLI subprocess coverage is collected through coverage.py's `subprocess` patch.

Open `htmlcov/index.html` to inspect missing lines and branch destinations;
`coverage.xml` provides machine-readable output. Use the full suite for the
global gate: a focused selection can legitimately fail it. Python coverage does
not measure templates or JavaScript.

## Browser tests

```bash
npx playwright install chromium firefox
# Linux hosts needing browser system libraries:
# npx playwright install --with-deps chromium firefox
npm run minify:check
npm run test:e2e
```

[playwright.config.js](playwright.config.js) starts
`uv run --locked resprint --demo --port 8765` and waits for `/healthz`. Leave
`127.0.0.1:8765` free: existing servers are not reused. The demo ignores `.env`,
`settings.toml` and production tokens, and starts its upstream fixtures on free
loopback ports. Playwright stops the demo process with SIGTERM when finished.

The same scenarios run on desktop Chromium, desktop Firefox and mobile Chromium
with Pixel 7 emulation. Each test has an independent browser context. Tests run
in parallel, with two workers in CI; retries are disabled.

Tests exercise the committed minified assets served by Flask. Regenerate assets
with `npm run assets` after frontend changes, as described in
[CONTRIBUTING.md](CONTRIBUTING.md#frontend-assets).

For debugging and results:

```bash
npm run test:e2e:ui
npx playwright show-report
```

The HTML report is written to `playwright-report/`; failure screenshots and
traces are retained under `test-results/`. Assertions also detect uncaught
JavaScript exceptions and failed asset responses. Mobile emulation verifies
behavior at a small viewport; it does not establish physical-device coverage
or pixel-level visual accuracy.

## Docker smoke tests

```bash
docker build -t resprint:local .
bash scripts/docker-smoke.sh resprint:local
```

The smoke script creates a temporary configuration and a dedicated Docker
network. It starts Jira/Tempo and Phorge fixture containers from the same image,
then starts the application with fictional tokens and a read-only configuration
mount. Upstream fixtures listen on port 8000 inside their containers; the web
application publishes container port 5000 on a free host loopback port.

Checks cover UID 10001, CLI availability, health probes, bundled assets,
participant selection, a web report and its embedded JSON, and a CLI JSON
export. Assertions include pagination totals, out-of-sprint issues and review
readiness. No real Jira, Tempo or Phorge service is contacted.

An EXIT trap prints service logs on failure and removes service containers,
the temporary network and temporary files. The built image remains available.
See [Docker deployment](docs/deployment.md) for normal application hosting.

## Continuous integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on pushes and pull
requests targeting `dev`, and on manual dispatch. Dependencies are installed
from `uv.lock` and `package-lock.json`.

| Job | Environment | Checks and artifacts |
| --- | --- | --- |
| Quality | Ubuntu, default Python, Node.js 22 | Ruff format/lint and minified asset consistency; five-minute timeout. |
| Python | Ubuntu, Python 3.11/3.13/3.14, Node.js 22 | Full suite and coverage gate; coverage XML/HTML and JUnit reports. |
| Browser | Ubuntu, default Python, Node.js 22, Chromium/Firefox | Playwright scenarios; HTML report and failure traces/screenshots. |
| Docker | Ubuntu and Docker | Image build and smoke script against local fixtures. |

Python, browser and Docker jobs have ten-minute timeouts. Python and browser
artifacts are retained for 14 days, including on failure when produced. Newer
runs cancel superseded runs on the same ref. Repository permissions are
read-only; CI checks generated assets without committing changes.

Git hooks run Ruff, pytest and relevant minified-asset checks, and reject `.env`
commits. They do not run the browser or Docker suites. See
[.pre-commit-config.yaml](.pre-commit-config.yaml) for their exact triggers.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `node` missing during Python tests | Install Node.js; CI uses version 22. |
| Socket permission error in integration tests | Run in an environment permitting loopback listeners. Use `-m "not integration"` for work that does not need this suite. |
| Playwright browser executable or libraries missing | Run the browser installation command above; Linux may require `--with-deps`. |
| Playwright server startup fails | Free port 8765 and inspect the demo startup output. An existing server is deliberately not reused. |
| Minified assets differ from sources | Run `npm run assets` and include generated files with the source change. |
| Coverage fails for one test module | Run plain pytest for focused feedback and the full coverage command for the gate. |
| Docker smoke startup fails | Check Docker availability, host `python3`, and the service logs printed by the script. |
