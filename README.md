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
done_status_categories = ["done"]
min_seconds = 1
log_level = "error"
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
- `resprint.min_seconds` is optional. The default is `1`.
- `resprint.log_level` is optional. The default is `error`; supported values are `debug`, `info`, `warning`, `error`, and `critical`.
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

In period/JQL mode, the JQL query is displayed in the report header. If Tempo participants are selected, the out-of-sprint section represents issues booked by those participants during the period but absent from the JQL result. With `out_of_sprint_analysis = true`, these out-of-sprint issues are enriched with detailed activity and complete worklog totals.

From the HTML report page, the `Export` button downloads the current report as JSON or Markdown without rerunning the analysis. These exports include the out-of-sprint section when present.

ReSprint always uses Jira for sprint issues, estimates, remaining estimates, comments, activity, and global issue worklog totals. Sprint-period consumed time is loaded from Tempo worklogs for the selected Tempo participants; without Tempo participants, sprint-period time is left empty. The same Tempo worklog search powers the out-of-sprint section.

The HTML report uses Chart.js for KPI charts and Material Design Icons for icons. These assets are bundled locally and served by ReSprint through `/assets/...`; viewing a report does not require a CDN or internet access.

## CLI Usage

Analyze a Jira Software sprint from a board:

```bash
uv run resprint --sprint-id 456 --format markdown
```

Analyze issues through JQL while keeping a Jira sprint identifier:

```bash
uv run resprint --sprint-id 456 --jql 'project = ABC' --format json
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

In period/JQL mode, the JQL query defines the issues considered part of the analyzed period. If `--tempo-worker` is provided, the out-of-sprint section lists issues booked by those Tempo workers during the period but absent from the JQL result. `--tempo-worker` can be provided multiple times. `--tempo-team-id` remains available for CLI users who want to compute period time from a whole Tempo team. With `out_of_sprint_analysis = true`, these issues are enriched with detailed activity and complete worklog totals.

Useful options:

```bash
uv run resprint --sprint-id 456 --min-hours 2 --output review.md
uv run resprint --sprint-id 456 --format html --output review.html
uv run resprint --sprint-id 456 --tempo-worker alice --tempo-worker bob
```

If needed, provide sprint dates directly while using JQL:

```bash
uv run resprint \
  --sprint-id 456 \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --jql 'project = ABC'
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

```bash
uv run pytest
```

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
