# Configuration and troubleshooting

[Back to README](../README.md)

## Configuration files

ReSprint reads `settings.toml` and `.env` from the current working directory.
Start with [settings.toml.example](../settings.toml.example) and
[.env.example](../.env.example). Restart the service and regenerate reports after
changing configuration.

If `settings.toml` is absent, the legacy filename `setting.toml` is accepted.
If both exist, only `settings.toml` is read.

`.env` is loaded with python-dotenv. Quoted values, `export KEY=value`, inline
comments and variable expansion are supported. Existing environment variables
take precedence. Docker's `--env-file` uses different syntax; see
[Docker deployment](deployment.md).

## Credentials and service access

`JIRA_API_TOKEN` is required outside demo mode. Jira and Tempo requests use
`Authorization: Bearer <token>` against `jira.base_url`. Use a token accepted by
your instance; a password or email/API-token Basic authentication pair is not
implemented.

The configured account needs access to the issues and worklogs being analyzed,
Jira Software boards/sprints for sprint selection, and Tempo teams, members and
worklog search for participant selection. Visibility follows the service's
permissions; ReSprint does not grant additional access.

Tempo calls use `/rest/tempo-teams/2` and `/rest/tempo-timesheets/4` on the Jira
instance, with the Jira token and certificate configuration. There is no
separate Tempo Cloud URL or token setting.

`PHORGE_API_TOKEN` is required only for the optional
[Phorge integration](phorge.md).

## Jira settings

| Key under `[jira]` | Default | Purpose |
| --- | --- | --- |
| `base_url` | Required | Jira instance URL, for example `https://jira.example.com`. |
| `project_key` | Unset | Project used to list boards in the web UI; optional for CLI reports. |
| `rest_api_version` | `"2"` | Issue REST API version: `"2"` or `"3"`. Use `"2"` for Data Center. |
| `ca_bundle` | System trust | Path to a custom CA bundle for Jira and Tempo HTTPS requests. |

Sprint metadata comes from `/rest/agile/1.0/sprint/{id}`. Sprint issues are
loaded through issue search. Switching the issue REST API version does not
change the Tempo API or authentication method.

## Report settings

| Key under `[resprint]` | Default | Purpose |
| --- | --- | --- |
| `hours_per_day` | `7` | Working hours per displayed day; positive fractional values such as `7.5` are supported. |
| `done_status_categories` | `["done"]` | Jira status category keys treated as completed. |
| `min_seconds` | `1` | Minimum total period time for an unfinished issue to appear; CLI `--min-hours` overrides this threshold. |
| `language` | `"fr"` | Display language: `"fr"` or `"en"`. |
| `log_level` | `"warning"` | `debug`, `info`, `warning`, `error` or `critical`. |
| `out_of_sprint_analysis` | `false` | Load detailed activity and complete Jira worklogs for out-of-scope issues. The section itself is available without this enrichment. |
| `request_concurrency` | `4` | Maximum concurrent per-issue Jira requests; must be at least one. |
| `jira_issue_request_timeout` | `10` | Positive timeout in seconds for each per-issue comments, changelog or complete-worklog request. |
| `ignored_changelog_fields` | `["worklogid", "timeestimate", "timespent"]` | Fields omitted from displayed activity. |
| `excluded_issue_keys` | Empty | Issue keys excluded from both scope and out-of-sprint sections. |
| `parent_field` | Unset | Optional Jira custom field containing a parent or epic relationship. |

Durations in HTML and Markdown use working days (`j` in French, `d` in English).
With `hours_per_day = 7.5`, 27,000 seconds is displayed as `1.00 j` in French.
Calculations and sorting remain in seconds. JSON keeps explicit seconds/hours
fields. Review age uses calendar days.

Comments and activity are filtered to the analyzed dates, including both bounds.
Detailed out-of-sprint totals require `out_of_sprint_analysis = true`; without
it, their available totals are based on the selected period worklogs.

## Logging

Logs go to stderr, leaving CLI report output on stdout. Set `log_level = "info"`
to follow report generation or `"debug"` for detailed diagnostics.

| Level | Meaning |
| --- | --- |
| `error` | The requested operation failed. |
| `warning` | A request was rejected or usable results have incomplete data. |
| `info` | Normal progress, completion and service lifecycle. |
| `debug` | Pagination, configuration, caches and rendering diagnostics. |

HTTP error diagnostics omit raw response bodies, headers, credentials and raw
exception messages. Server access logs are configured separately by the host or
Gunicorn. Review logs before sharing them: issue identifiers and operational
details can still be private.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing configuration or token | Run from the directory containing `settings.toml` and `.env`; check for environment variables overriding `.env`. |
| HTTP 401 or 403 | Token validity, Bearer authentication support, and the account's Jira/Tempo permissions. |
| Tempo endpoints return 404 | The instance exposes the Jira-hosted Tempo APIs listed above; the separate Tempo Cloud API is not implemented. |
| No boards listed | `jira.project_key`, Jira Software access and board visibility. |
| Missing issues | JQL/sprint scope, exclusions, selected participants, status category and period-time threshold. |
| Partial activity or totals | Warning logs, per-issue timeouts and upstream permissions. |
| Certificate verification error | A readable CA bundle configured through `jira.ca_bundle` or `phorge.ca_bundle`; container paths must exist inside the container. |
| Port 5000 occupied | Use `--port 5001` with `--serve` or `--demo`. |
| HTML file lacks styling or interactions | CLI HTML references `/assets/...`; use the web UI or serve those assets at the expected path. |
