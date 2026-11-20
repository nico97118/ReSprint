# ReSprint

Prepare Jira sprint reviews with a clear view of completed work, unfinished
issues with time logged, and work outside the sprint.

ReSprint combines Jira issues with Tempo worklogs for the participants you select.
Use the local web interface to explore a report, or generate Markdown and JSON
from the command line. An optional Phorge integration adds the current state of
linked Differential reviews.

- Analyze a Jira sprint or a custom period defined by a JQL query.
- Compare estimates, remaining work, total time and time spent during the period.
- Inspect comments, activity and time spent by participant.
- Search, filter and sort reports in French or English.
- Export the displayed report as Markdown or JSON without rerunning it.

[Try the demo](#try-the-demo) · [Installation](#installation) ·
[Usage](#usage) · [Documentation](#documentation) ·
[Contributing](#help-and-contributing)

## Try the demo

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
The project supports Python 3.11 or later and defaults to Python 3.13 through
[`.python-version`](.python-version); uv can install the required interpreter.

```bash
git clone https://github.com/nico97118/ReSprint.git
cd ReSprint
uv sync --locked --no-dev
uv run --locked --no-dev resprint --demo
```

Open [localhost:5000](http://127.0.0.1:5000/), select the demo sprint, choose the
Tempo team and generate a report. The demo runs local Jira, Tempo and Phorge
fixtures with fictional data. It requires no account or configuration and ignores
production tokens, `.env` and `settings.toml`. Press Ctrl+C to stop it.

If port 5000 is occupied, add `--port 5001`.
See [demo fixtures](docs/demo.md) for the dataset and supported demo queries.

## Requirements and compatibility

For your own data, ReSprint requires:

- Jira Software with access to the relevant issues, boards, sprints and worklogs.
- Tempo installed on the Jira instance, exposing the Data Center endpoints
  `/rest/tempo-teams/2` and `/rest/tempo-timesheets/4`.
- A Jira token accepted as a Bearer token, with access to the required Jira and
  Tempo data. The same token is used for both services.

The Tempo integration targets Jira-hosted Data Center APIs. ReSprint does not
implement the separate Tempo Cloud API. Choosing Jira REST API v3 does not enable
Tempo Cloud support. Check your instance's API availability and permissions
before connecting it.

Node.js and npm are needed only for frontend development and tests. Frontend
assets are bundled with the application.

## Installation

From the cloned repository, install dependencies and create your configuration:

```bash
uv sync --locked --no-dev
cp .env.example .env
cp settings.toml.example settings.toml
```

Set your token in `.env`:

```dotenv
JIRA_API_TOKEN=your-jira-personal-access-token
```

Edit the Jira section of `settings.toml` for your instance:

```toml
[jira]
base_url = "https://jira.example.com"
project_key = "ABC"
rest_api_version = "2"
```

Run commands from the repository root: configuration is read from the current
working directory. Keep credentials in `.env` or environment variables; both
`.env` and `settings.toml` are excluded from Git.

See [configuration](docs/configuration.md) for all settings, custom certificate
authorities and optional Phorge credentials. For a container deployment, follow
the [Docker guide](docs/deployment.md).

## Usage

### Web interface

```bash
uv run --locked --no-dev resprint --serve
```

Open [localhost:5000](http://127.0.0.1:5000/). Select a board and sprint, or enter a
date range and JQL query. Then choose a Tempo team and the members whose time
should contribute to the report. `jira.project_key` is needed to list boards.

The report provides charts, expandable issue details, search and filters. The
**Export** button downloads the displayed data as JSON or Markdown.

### Command line

Generate a sprint review as Markdown:

```bash
uv run --locked --no-dev resprint --sprint-id 456 --tempo-worker alice --output review.md
```

Replace `456` with your Jira sprint ID and `alice` with a Tempo worker key from
your instance. Repeat `--tempo-worker` for multiple participants, or use
`--tempo-team-id 42` for a whole team. A participant or team selection is required
for every report.

Analyze a custom period:

```bash
uv run --locked --no-dev resprint \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --sprint-name "May iteration" \
  --jql 'project = ABC AND fixVersion = "2026.05"' \
  --tempo-worker alice --tempo-worker bob \
  --format json --output review.json
```

With `--sprint-id`, an additional `--jql` narrows the sprint scope. Without a
sprint ID, JQL and both dates are required. Use `--min-hours 2` to include
unfinished issues with at least two hours logged during the period.

Markdown is the default format. Omit `--output` to write to stdout, or use
`--format json` for structured data. `--format html` is also available, but its
output references `/assets/...` and requires the application's assets to be
served at that path; it is not a self-contained HTML file.

Run `uv run --locked --no-dev resprint --help` for all options.

## Understanding the report

The main issue sections are:

- **Completed:** issues in the configured done status categories.
- **Unfinished with time:** other issues with period time at or above the
  configured threshold (one second by default, overridden by `--min-hours`).
- **Not started:** issues in Jira's `new` status category below that threshold.
- **Out of sprint:** issues with time logged by the selected participants during
  the period, outside the sprint or JQL scope.

An issue in progress below the threshold does not appear in the first three
sections. The report highlights issues for discussion using these selection rules.

Jira supplies issue details and total worklogs; Tempo supplies period time for
the selected participants. Displayed durations use working days, with seven
hours per day by default. JSON retains explicit seconds/hours fields, and
`--min-hours` is always expressed in hours.

Reports reflect data available when generated. In particular, the optional
Phorge recap shows current review states even for a past sprint. Optional data
loads can fail while leaving a usable report; consult the logs for warnings.

## Documentation

- [Configuration and troubleshooting](docs/configuration.md)
- [Phorge review recap and readiness rules](docs/phorge.md)
- [Docker deployment and CLI exports](docs/deployment.md)
- [Demo dataset and local API fixtures](docs/demo.md)
- [Development and frontend assets](CONTRIBUTING.md)
- [Testing infrastructure and commands](TESTING.md)

## Help and contributing

For questions and bug reports, use the
[issue tracker](https://github.com/nico97118/ReSprint/issues). Include the command
or workflow, expected and actual behavior, and relevant service versions. Remove
tokens and private Jira or review data from logs and examples.

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup and checks, and [AUTHORS.md](AUTHORS.md) for project authorship.

## License

ReSprint is distributed under the [Apache License 2.0](LICENSE).
See [NOTICE](NOTICE) for attribution notices.
