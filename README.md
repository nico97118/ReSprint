# ReSprint

ReSprint is a Python tool that helps prepare Jira sprint reviews. It highlights issues that deserve discussion, especially unfinished issues with logged time during the analyzed period.

It can analyze a Jira sprint identified by a sprint ID, or analyze a custom period from a JQL query. Reports can be exported as HTML, Markdown, or JSON, and a local Flask frontend is available for interactive usage.

## Installation

```bash
uv sync
source .venv/bin/activate
cp .env.example .env
cp setting.toml.example setting.toml
```

Then fill `.env` with the required secrets:

- `JIRA_API_TOKEN`, required to use the tool.

The `.env` file is loaded with `python-dotenv`. Standard dotenv syntax is supported, including `export KEY=value`, quoted values, inline comments, and expansion of variables already present in the environment. Variables already defined in the environment are not overridden by `.env`.

Non-secret configuration lives in `setting.toml` at the project root. `setting.toml.example` provides a starting point.

```toml
[jira]
base_url = "https://your-domain.atlassian.net"
project_key = "ABC"
rest_api_version = "2"

[resprint]
hours_per_day = 7
done_status_categories = ["done"]
min_seconds = 1
log_level = "warning"
language = "fr"
out_of_sprint_analysis = false
request_concurrency = 4
jira_issue_request_timeout = 10
ignored_changelog_fields = ["worklogid", "timeestimate", "timespent"]
excluded_issue_keys = ["ABC-123"]
parent_field = "customfield_10014"
```

Configuration keys:

- `jira.base_url` is required.
- `jira.project_key` is optional for the CLI, but required by the local web UI to list Jira boards for the project.
- `jira.rest_api_version` is optional. The default is `2`; supported values are `2` and `3`.
- `jira.ca_bundle` is optional. It can point to a custom CA bundle file used to trust custom Jira and Tempo certificate authorities.
- `resprint.done_status_categories` is optional. The default is `["done"]`.
- `resprint.hours_per_day` is optional (default: `7`). It defines the hours in one working day for displayed durations. Positive fractional values such as `7.5` are supported.
- `resprint.min_seconds` is optional. The default is `1`.
- `resprint.log_level` is optional. The default is `warning`; supported values are `debug`, `info`, `warning`, `error`, and `critical`.
- `resprint.language` is optional. The default is `fr`; supported values are `fr` and `en`.
- `resprint.out_of_sprint_analysis` is optional. The default is `false`; out-of-sprint tickets are still listed when a Tempo team is selected, but setting this to `true` also loads their detailed activity and complete worklog totals.
- `resprint.request_concurrency` is optional. The default is `4`; it limits concurrent per-issue Jira requests.
- `resprint.jira_issue_request_timeout` is optional. The default is `10`; it limits each per-issue Jira request for comments, changelog, and complete worklogs so a very heavy issue cannot block the whole report for too long.
- `resprint.ignored_changelog_fields` is optional. The default is `["worklogid", "timeestimate", "timespent"]`.
- `resprint.excluded_issue_keys` is optional. It lists Jira issue keys to remove from sprint and out-of-sprint report sections.
- `resprint.parent_field` is optional. It can be used to read a Jira custom field that stores the parent or epic relationship.

For Jira Data Center, keep `rest_api_version = "2"`. Search, comment, and worklog endpoints will use `/rest/api/2`. The sprint flow uses the Jira Agile Data Center API to fetch sprint metadata, then loads sprint issues through Jira issue search and enriches issue details through REST API v2 or v3 depending on the configuration.

## Local Web UI

Start the local web server:

```bash
uv run resprint --serve
```

The server listens on `http://127.0.0.1:5000` by default. The UI uses `jira.project_key` to list boards for the configured project, then shows active and closed sprints for the selected board. The home page first selects the report scope, then the participants page selects the Tempo team members used for period time before generating the report synchronously. CLI exports remain available separately.

The home page provides two scope selection modes:

- Jira sprint analysis, open by default, to select a board and continue from one sprint.
- Period and JQL analysis, collapsed by default, to enter a start date, an end date, and a JQL query.

The participants page confirms the selected scope, displays a compact issue count grouped by issue type, and lets users choose a Tempo team. Team members are selected by default and can be excluded before report generation.

In period/JQL mode, the JQL query is displayed in the report header. Tempo participants are required; the out-of-sprint section represents issues booked by those participants during the period but absent from the JQL result. With `out_of_sprint_analysis = true`, these out-of-sprint issues are enriched with detailed activity and complete worklog totals.

From the HTML report page, the `Export` button downloads the current report as JSON or Markdown without rerunning the analysis. These exports include the out-of-sprint section when present.

ReSprint always uses Jira for sprint issues, estimates, remaining estimates, comments, activity, and global issue worklog totals. Sprint-period consumed time is loaded from Tempo worklogs for the selected Tempo participants. The same Tempo worklog search powers the out-of-sprint section.

The HTML report uses Chart.js for KPI charts and Material Design Icons for icons. These assets are bundled locally and served by ReSprint through `/assets/...`; viewing a report does not require a CDN or internet access.

## Local demo without Jira, Tempo or Phorge

```bash
uv run resprint --demo
# If port 5000 is already in use:
uv run resprint --demo --port 5001
```

The command starts the web UI on `127.0.0.1` and local HTTP fixtures on free
loopback ports. It ignores local `setting.toml`, `.env` and production tokens;
all settings and credentials are fictional and held in memory. Ctrl+C or
SIGTERM stops the web server and both fixture services. Nothing is written to
the working directory. The demo flag serves the web interface; choose the
report scope in the UI rather than passing CLI export options to `--demo`.

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

Period/JQL reports can use the same dates and participants. Supported demo JQL
is deliberately limited to `project = ABC`, `sprint = 456`, `key in (...)`
(or `issue in (...)`), combinations with `AND`, and an optional `ORDER BY key`.
Unsupported queries return an explicit HTTP 400 instead of pretending to apply
filters. The fixture models REST API v2/v3 and the Data Center Tempo endpoints
used by ReSprint; it does not implement all Jira or Phorge capabilities.

Tests can reuse `resprint.demo.demo_services()` as a context manager yielding
isolated `Settings`, with the real clients and report builder. For standalone
fixtures or container tests:

```bash
uv run python -m resprint.demo.mock_jira --port 8000
uv run python -m resprint.demo.mock_phorge --port 8001
```

The Jira fixture also serves Tempo. Its expected Jira token and the Phorge
fixture token are both `resprint-demo`. The review field is
`customfield_reviews`. The Docker smoke test uses these same fixtures to check
a full report and CLI export without external services.

## Docker deployment

Build the image from the repository root, then mount your existing
`setting.toml` read-only and provide API tokens at runtime:

```bash
docker build -t resprint:local .
docker run -d --name resprint \
  --publish 127.0.0.1:5000:5000 \
  --env-file .env \
  --mount "type=bind,source=$PWD/setting.toml,target=/app/setting.toml,readonly" \
  resprint:local
```

Open `http://127.0.0.1:5000/`. Use `docker logs resprint` for startup and
access logs, and `curl --fail http://127.0.0.1:5000/healthz` to check the web
process independently of Jira, Tempo or Phorge. Docker also runs this health
check automatically. To recreate the container after rebuilding or changing
configuration, remove it first with `docker rm -f resprint`.

The image installs the locked `server` extra and the application as a regular
package in a two-stage Python 3.13 build. The runtime includes Gunicorn, the CLI,
templates and bundled frontend assets; it runs as UID/GID 10001. Source secrets,
local configuration and development dependencies are excluded from the image.
No npm installation is needed to build or run it.

Docker environment files use plain `KEY=value` lines: omit shell quotes and
variable interpolation. Pass `JIRA_API_TOKEN` and, when enabled,
`PHORGE_API_TOKEN` this way or through your platform's secret mechanism. Mounted
configuration and certificate files must be readable by UID 10001. For a custom
CA, add a read-only mount and set `jira.ca_bundle` or `phorge.ca_bundle` to its
path **inside** the container. The web service needs outbound access to the
configured services and no persistent volume.

Gunicorn defaults to two synchronous workers and a 300-second worker timeout
because report generation makes multiple Jira/Tempo/Phorge requests. Tune worker
count and timeout for representative workloads; each report also uses the
configured request concurrency. Override the complete Gunicorn argument set
through `GUNICORN_CMD_ARGS`, for example:

```bash
docker run -d --name resprint \
  --publish 127.0.0.1:5000:5000 \
  --env-file .env \
  --env 'GUNICORN_CMD_ARGS=--bind=0.0.0.0:5000 --workers=2 --timeout=600 --no-control-socket --access-logfile=- --error-logfile=-' \
  --mount "type=bind,source=$PWD/setting.toml,target=/app/setting.toml,readonly" \
  resprint:local
```

Keep port 5000 inside the container for the built-in health check. For shared
hosting, place the service behind your authenticated HTTPS reverse proxy and
align its timeout with long report requests. Viewers use the configured Jira
account's permissions.

The same image can run CLI exports by overriding the server command:

```bash
docker run --rm --env-file .env \
  --mount "type=bind,source=$PWD/setting.toml,target=/app/setting.toml,readonly" \
  resprint:local resprint --sprint-id 456 --tempo-worker alice --format json \
  > report.json
```

To run the image checks locally, use `bash scripts/docker-smoke.sh resprint:local`.
CI builds the image and runs the same checks for the non-root runtime, assets,
full web report and JSON CLI export against local Jira/Tempo and Phorge
fixtures. No real service is contacted.

## CLI Usage

Analyze a Jira Software sprint from a board:

```bash
uv run resprint --sprint-id 456 --tempo-worker alice --format markdown
```

Analyze issues through JQL while keeping a Jira sprint identifier:

```bash
uv run resprint \
  --sprint-id 456 \
  --jql 'project = ABC' \
  --tempo-worker alice \
  --format json
```

Analyze a custom period from JQL:

```bash
uv run resprint \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --sprint-name "May iteration" \
  --jql 'project = ABC AND fixVersion = 2026.05' \
  --tempo-worker alice \
  --tempo-worker bob \
  --format html \
  --output review.html
```

In period/JQL mode, the JQL query defines the issues considered part of the analyzed period. `--tempo-worker` is required unless `--tempo-team-id` is provided, and can be provided multiple times. `--tempo-team-id` remains available for CLI users who want to compute period time from a whole Tempo team. With `out_of_sprint_analysis = true`, out-of-sprint issues are enriched with detailed activity and complete worklog totals.

Useful options:

```bash
uv run resprint --sprint-id 456 --tempo-worker alice --min-hours 2 --output review.md
uv run resprint --sprint-id 456 --tempo-worker alice --format html --output review.html
uv run resprint --sprint-id 456 --tempo-worker alice --tempo-worker bob
```

If needed, provide sprint dates directly while using JQL:

```bash
uv run resprint \
  --sprint-id 456 \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --jql 'project = ABC' \
  --tempo-worker alice
```

## Report Content

The report organizes issues into three sections:

- Completed issues, with visual highlighting when total consumed time exceeds the original estimate.
- Unfinished issues with at least `--min-hours` logged by the selected Tempo participants during the analyzed period.
- Not started issues, meaning issues still in the Jira `new` status category without significant logged time.

For these issues, the report also includes Jira comments and Jira activity created during the analyzed period when available. Issues and comments are loaded first through Jira search, then Jira worklogs and changelog entries are loaded per issue. Changelog entries are loaded through `expand=changelog` on each issue. If one issue activity or worklog load fails, the report continues with that issue marked by incomplete local data in logs.

The report table contains issue key, title, issue type, status, parent, original estimate, remaining estimate, total consumed time, and sprint consumed time. Each row can be expanded to inspect details: time progress, priority, fixVersion, consumed time by user, sprint comments, and summarized Jira changes in a who/when/what format. Comment and activity sections show a badge with the number of available items; comments are open by default and activity is collapsed by default.

## Frontend Assets

Third-party frontend assets are managed through a minimal npm setup. Vendored files are committed under `src/resprint/frontend/static/vendor/`, so npm is not required to run ReSprint.

Application CSS and JavaScript are minified into `src/resprint/frontend/static/min/` and served from `/assets/min/...`.

Regenerate assets from the lockfile:

```bash
npm ci
npm run vendor
npm run minify
```

Check that minified files are up to date without regenerating them:

```bash
npm run minify:check
```

Refresh all frontend assets in one command:

```bash
npm run assets
```

Run `npm run assets` whenever frontend asset sources or vendored asset dependencies change. This includes changes to application CSS or JavaScript, `package.json`, `package-lock.json`, or the asset build scripts.

## Tests

Install the locked development dependencies, then run the Python suite:

```bash
uv sync --dev --locked
uv run --locked pytest
# Fast feedback without local HTTP servers / demo subprocesses:
uv run --locked pytest -m "not integration"
# Real clients against loopback Jira, Tempo and Phorge fixtures:
uv run --locked pytest -m integration
# Full suite with branch coverage, HTML and machine-readable reports:
uv run --locked pytest --cov --cov-report=term-missing --cov-report=html --cov-report=xml
```

Coverage includes **all** Python modules under `src/resprint`, including demo
fixtures and unimported modules. No application modules are omitted to raise the
score. The blocking threshold is **97% combined statement/branch coverage**,
configured in `pyproject.toml`; this is not a 97% branch-only threshold.
Open `htmlcov/index.html` to inspect missing lines and branch destinations.
Run coverage on the full suite: a focused test selection can legitimately fail
the global threshold. Plain `pytest` remains convenient for focused development.
CLI subprocess coverage is collected and merged using coverage.py’s
[`subprocess` patch](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html),
including when the command runs from a temporary directory. HTML templates and
JavaScript are not measured by Python coverage.

The `integration` marker identifies `tests/test_demo.py`, which uses actual
HTTP clients, ephemeral loopback ports and the installed CLI. These tests need
permission to bind local sockets, but need no production services or credentials.
The other Python tests use fakes, temporary files and, for one frontend duration
check, Node.js. The shared fixture restores the frontend language after each
test so one test cannot change another test's translations.

### Browser tests

```bash
npm ci
npx playwright install chromium firefox
# Linux CI also needs OS libraries: npx playwright install --with-deps chromium firefox
npm run test:e2e
npm run test:e2e:ui
npx playwright show-report
```

Playwright starts and stops its own `resprint --demo` server on
`127.0.0.1:8765`. Leave that port free. It refuses to reuse an existing server,
so tests always use fictional Jira/Tempo/Phorge data. No `.env`, `setting.toml`
or production token is needed. Each test gets an independent browser context.
This follows Playwright's [webServer lifecycle](https://playwright.dev/docs/test-webserver).

The same scenarios run on desktop Chromium, desktop Firefox and mobile Chromium
(Pixel 7 emulation). They exercise the committed **minified assets** served by
Flask, including:

- Sprint and period/JQL navigation, team auto-submit, member selection and the
  disabled/enabled report-generation button; query fields survive navigation.
- Tab selection, Chart.js initialization, row expansion, search, counts, empty
  results and filtered duration totals; hidden details collapse.
- Natural ticket sorting, numeric duration sorting, row/detail association,
  combined filters/search and Escape dismissal of filter menus.
- Review search and reviewer decision details, JSON/Markdown downloads with
  content assertions, and theme persistence across reloads and navigation.
- Uncaught JavaScript exceptions and failed asset responses fail the test.

Tests use Playwright's waiting assertions and download events, without fixed
sleeps. Retries are disabled so flaky failures stay visible. Failure screenshots
and traces are retained alongside the HTML report in `playwright-report/` and
`test-results/`. Mobile emulation checks these interactions at a small viewport;
it does not replace testing on physical devices or a visual regression suite.

### CI strategy and audit (2026-11-20)

The initial suite had 232 passing Python tests and useful report/rendering and
local HTTP integration coverage, but no coverage gate or real browser tests.
The initial CI used one Python version and could commit regenerated assets back
to `dev`. That allowed CI to modify the code it was supposed to validate.
Asset updates must now be generated locally and included in the reviewed change;
CI checks them with read-only repository permissions.

The expanded suite adds failure-path assertions for Jira activity/worklogs and
Tempo lookups, exact classification thresholds, inclusive activity date bounds,
UTF-8 CLI exports to stdout/files, malformed API payloads and dates, sanitized
Phorge diagnostics, comment HTML escaping, and translation key/placeholder
parity. Regression tests exposed malformed board/team identifiers returning
500; these now return the existing 400 error page. A global filesystem mock in
a configuration test also recursed on Python 3.14; temporary-directory isolation
replaces that mock.

Coverage-pass measurements on Python 3.13, before the logging audit:

| Metric | Initial | First pass | Coverage pass |
| --- | ---: | ---: | ---: |
| Python test cases | 232 | 307 | 430 |
| Python statement coverage | 91.69% | 94.18% | 98.30% |
| Python branch coverage | 79.52% | 83.18% | 96.00% |
| Combined coverage | 89.24% | 91.97% | 97.84% |
| `report.py` combined coverage | 80.56% | 90.74% | 97.22% |
| Browser scenarios × projects | 0 | 11 × 3 | 11 × 3 |

The coverage-pass run also measures CLI subprocesses; the initial and first-pass runs
measured the parent process only. All Python 3.11, 3.13 and 3.14 runs pass the
97% floor with the same final coverage. The Jira, Tempo and Phorge clients each
reach **100% statement and branch coverage** through client-level contracts.
The additional tests found two real defects: a cached empty Jira identity hid a
successful username fallback on subsequent calls, and a malformed embedded Jira
comment envelope prevented loading an otherwise usable ticket. Both have
regression tests and fixes in separate commits.

### Why the global floor is not 100%

The remaining 59 uncovered lines are still included in the report. Of these,
32 belong to demo fixtures/bootstrap, and 10 belong to unused or bypassed helpers
(`group_worklogs_by_issue`, `Issue.url_key`, and the old Tempo search fallback;
current report generation already passes loaded period worklogs). The other 17
are parser/table and request-validation fallbacks. Some cannot be reached
through the current public flow: complete code macros are normalized before
line parsing, and table rows require a cell for every column before rendering.
Testing those branches by bypassing earlier steps would bind tests to internal
implementation rather than protect a user-visible contract.

No application code is excluded and no `no cover` pragmas were added. A future
cleanup can review and remove obsolete paths on their own merits. Further test
work should focus on real compatibility, accessibility and mutation resistance;
a 100% global score alone would not establish those properties. The 97% floor
retains a small margin below the measured 97.84% while blocking material losses.

CI runs independent jobs for Ruff/assets, Python **3.11, 3.13 and 3.14** (minimum
supported version, default runtime and newer interpreter), Playwright, and the
existing Docker build/smoke test. Every job has a timeout. Superseded runs on the
same ref are cancelled. Python jobs retain coverage XML/HTML and JUnit reports;
the browser job retains HTML reports and failure traces, all for 14 days.
Dependencies are installed from `uv.lock` and `package-lock.json`. See
[pytest-cov configuration](https://pytest-cov.readthedocs.io/en/latest/config.html)
for the coverage reporting and threshold options.

Next improvements, in priority order:

1. Extend Jira/Phorge adapter cases for malformed pagination, missing fields and
   API-version differences. Local fixtures verify application contracts, but
   cannot establish compatibility with every real Jira/Tempo/Phorge version.
2. Add focused JavaScript unit tests if table logic grows (filter option
   availability and duration calculations first). Keep browser assertions for
   actual interactions; do not duplicate every Python rendering assertion.
3. Add a small accessibility audit and keyboard-only tab navigation tests, then
   selected visual baselines on a pinned browser/OS. Chart initialization is
   covered; pixel accuracy and tooltip content are not yet checked.
4. Use mutation testing on classification and review-readiness rules to find
   assertions that execute code without detecting wrong decisions. Raise the
   coverage floor as meaningful gaps close, rather than targeting 100% with
   low-value assertions. Investigate any browser flake before adding retries.

The current module-global language setting is reset between tests, but this
does not prove isolation between concurrent apps configured with different
languages. If multi-language concurrent serving becomes a requirement, scope
that state per request/app and add concurrent integration tests.

## Logging

Set `[resprint] log_level = "info"` in `setting.toml` to follow report generation.
The default is now **warning** so a partially generated report is observable.
Existing configurations explicitly selecting `error` remain unchanged; update
that setting to see degradation warnings. Logs go to stderr, leaving CLI JSON,
Markdown and HTML output on stdout clean.

| Level | Meaning | Examples |
| --- | --- | --- |
| `error` | The requested operation failed | Unavailable Jira prevents a page/report, invalid startup configuration, failed report-file write |
| `warning` | Input rejected or usable results are incomplete | HTTP 400, failed optional enrichment, invalid external entries skipped, missing reviewer decisions, repeated pagination cursor |
| `info` | Normal operational progress and completion | Report phases, counts, review snapshot completion, CLI/WSGI/demo startup and shutdown |
| `debug` | Detailed implementation diagnostics | Pagination, parameter names, cache lookups, configuration loading, templates/tables/KPIs, assets and health probes |

The default console format includes timestamp, level, module and calling
function. CLI/report completion and web responses include elapsed milliseconds.
A failed operation does not emit a misleading successful completion. Existing
host logging handlers and formatters are preserved; configuring verbose ReSprint
logging does not enable verbose third-party HTTP logging.

### Instrumentation boundaries

The logging audit reviewed functions by responsibility, rather than adding an
entry/exit message to every getter or per-cell formatter:

| Responsibility | Instrumentation |
| --- | --- |
| CLI and configuration | Mode/start, validated configuration at debug, successful completion, one terminal diagnostic; missing optional Phorge configuration is a warning |
| Web and WSGI | Page/report start, endpoint/status/duration, invalid requests at warning without traceback, upstream failures at error, factory readiness/failure |
| Jira and Tempo | Client operations, page and result counts, identity/cache lookups at debug; the caller that chooses a fallback logs the failure |
| Phorge and review snapshot | Base query and snapshot counts, reviewer/name/repository stages at debug, unavailable metadata and stopped pagination at warning |
| Analysis, exports and rendering | Report/classification/export phases, template/table/KPI boundaries at debug; pure arithmetic, escaping, dataclass properties and small formatting helpers remain silent |
| Demo and local fixtures | Ready/closed/startup failure; fixture lifecycle at debug. Mock API routes remain quiet because actual clients already describe those operations. Signal handlers avoid logging directly; shutdown is logged after control returns to the demo boundary. |

HTTP diagnostics retain the exception type and available HTTP status, never the
raw exception text, URL credentials, query values, headers or response body.
Recovered external-data failures similarly omit raw exception messages and
tracebacks. Debug mode records only module/function/line locations from caught
exceptions, without source lines or local variable values. Unexpected uncaught failures remain the responsibility of the CLI
runtime or WSGI server. Server access logs have their own configuration and are
separate from these application logs. Host-provided handlers can also choose
different thresholds or formats.

Tests assert severity, absence of duplicate application error events, success
stage order, caller function context, elapsed-time fields, quiet health probes,
configuration isolation and redaction using sentinel credentials. They exercise
successful reports against the real local demo services, not just mocked logger
calls. This follows the [standard Python logging levels](https://docs.python.org/3.13/howto/logging.html#when-to-use-logging).

## Code Quality

```bash
uv run ruff format
uv run ruff check
```

## Git Hooks

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

The hooks check Ruff formatting, Ruff linting, pytest, and minified asset consistency when frontend files change. They also prevent committing a `.env` file.

## Architecture

The application code is organized by responsibility:

- `resprint.models` and `resprint.analysis`: domain models and sprint analysis.
- `resprint.helpers`: Jira and Tempo access helpers.
- `resprint.report`: report data construction.
- `resprint.exporters`: Markdown and JSON exports.
- `resprint.frontend`: local Flask UI, templates, assets, and HTML rendering.
- `resprint.cli`: command-line entry point.

Domain modules do not depend on Flask or HTML rendering. Jira and Tempo helpers isolate network calls. The frontend consumes already analyzed domain objects.

## API Sources

- Jira Software Agile API: sprint metadata and sprint issues.
  https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/
- Jira Cloud issue search and JQL.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- Jira Cloud issue worklogs.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-worklogs/
- Jira issue API: issue details and changelog through `expand=changelog`.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- Tempo Cloud API v4: worklogs filtered by `from`, `to`, and `issueId`.
  https://apidocs.tempo.io/
- Chart.js: KPI charts in the HTML report.
  https://www.chartjs.org/
- Material Design Icons: HTML interface icons.
  https://pictogrammers.com/library/mdi/

## License

ReSprint is distributed under the Apache License, Version 2.0. See `LICENSE` and `NOTICE`.

## Phorge review recap

ReSprint automatically includes a Differential review recap when `[phorge]`
contains `enabled = true`, `jira_fields` (a field name or a list of names),
`base_url`, and `PHORGE_API_TOKEN` is present in the environment or `.env`.
Configure non-secret values in `setting.toml`; see `setting.toml.example`.
An optional `ca_bundle` overrides the Jira certificate bundle.

References such as `D123` or a full review URL are extracted from strings or
lists of strings in the configured Jira fields. All issues in the sprint or
JQL scope contribute, after configured exclusions, including issues absent
from the time-based report categories. Out-of-sprint issues do not contribute.
A review referenced by multiple issues appears once with all linked issue keys.

The HTML recap offers search, sorting and an explicit state filter. It lists
reference, title, normalized state, Phorge status, repository, age in days of
open reviews and linked Jira issues. Ticket details also show review links and
states. Markdown includes a recap; JSON adds `code_reviews` with `checked_at`,
`warning`, `counts` and `items`. Web downloads reuse the displayed snapshot.
Warning values in JSON are stable translation keys, or null.

This is the **current** state of the references and reviews, timestamped when
the report is generated, even for a past sprint. It does not reconstruct the
state at sprint closure. Accepted reviews remain open until closed; abandoned
reviews have a separate count. Missing or inaccessible reviews are unknown.

The module defaults to disabled. Incomplete activation settings produce a
warning and leave it inactive. No references means no Phorge request. Phorge
failures preserve the Jira/Tempo report and referenced review rows with unknown
states. Repository lookup failures preserve any resolved review states.

Reviewer decisions are enriched through the read-only
`differential.revision.search` endpoint with the `reviewers` attachment.
Each review in the JSON snapshot also carries:

- `validation_count`: number of distinct reviewer entries in `accepted` state.
  An `accepted-older` decision does not count. A project reviewer counts as
  one entry, regardless of its number of members.
- `pending_required_approval_count`: number of blocking reviewer entries that
  have not accepted.
- `ready_to_close`: the calculated “À clôturer” indicator, true only for an
  open review meeting the configured validation and pending mandatory approval
  thresholds (defaults: at least two validations and zero pending approvals). Closed and abandoned reviews return false.

Missing, malformed or unsupported reviewer data leaves the counts null and
an open review's indicator null (indeterminate). Failure of this extra lookup
preserves the base review information and is logged without credentials.
Search requests are batched and paginated. These fields do not change the
Phorge state or close a revision, and are exposed as data in JSON. A “Ready to close” state badge appears in the
review table and ticket details for eligible reviews. The State filter selects
these candidates; their underlying Phorge state remains open.

The compact Reviews column shows a warning icon with an explanatory tooltip
when a completed issue has a known non-closed review, or when an unfinished
issue has all reviews closed or ready to close. Completion follows the report's
configured Jira categories. Empty reference lists and out-of-scope issues do
not trigger warnings. Unknown review states cannot establish readiness to
complete an issue. Abandoned reviews are excluded from all warning checks;
a ticket with only abandoned reviews behaves like a ticket without reviews.

Each review row expands to show its raw Phorge status and reviewer details:
validators (check icon), mandatory
approvals pending (clock icon), and reviewers requesting changes (cross icon).
Only current `accepted` decisions are shown as validations. Reviewer names,
including project reviewers, are resolved in read-only `phid.query` batches
shared across reviews. Inaccessible names are replaced with a translated
placeholder without losing decisions or counts. JSON retains the reviewer
PHID, status, blocking flag and optional display name in `reviewers` (null
when reviewer data is unavailable, an empty list when there are no reviewers).


The “Ready to close” thresholds can be changed in `setting.toml`:

```toml
[phorge]
ready_to_close_min_validations = 2
ready_to_close_max_pending_required_approvals = 0
```

Both values must be non-negative integers. A candidate must be open, have at
least the configured number of validations, and at most the configured number
of mandatory approvals pending. Missing reviewer data remains indeterminate,
even with zero thresholds. Restart ReSprint and regenerate the report after
changing configuration. The same calculated indicator drives badges and ticket
consistency warnings. JSON includes the applied thresholds in
`code_reviews.closure_criteria` to make the report's calculation explicit.

The review table includes an Author column. Author and reviewer names share
read-only `phid.query` batches. Unavailable authors display a dash; the original
`author_phid` and optional `author_name` are retained in the JSON snapshot.
Author names are also searchable in the review table.


Report durations are displayed in working days (`j` in French, `d` in English),
using `[resprint] hours_per_day` (default `7`). This includes ticket tables,
filtered column totals, per-user time, detail progress, KPI charts and Markdown
exports, including downloads from the HTML report. For example, with
`hours_per_day = 7.5`, 27,000 seconds is displayed as `1.00 j` in French.
Restart ReSprint and regenerate the report after changing this setting.
Underlying calculations and sort values remain in seconds. JSON retains its
explicit seconds/hours fields and the CLI `--min-hours` threshold stays in hours.
The age of a review remains measured in calendar days.
