# Phorge review recap

[Back to README](../README.md)

## Enable the integration

Set `PHORGE_API_TOKEN` in your environment or `.env`, then configure
`settings.toml`:

```toml
[phorge]
enabled = true
base_url = "https://phorge.example.com"
jira_fields = ["customfield_12345"]
ready_to_close_min_validations = 2
ready_to_close_max_pending_required_approvals = 0
```

Replace the URL and field identifier with your instance values. `jira_fields`
accepts a field name or a list of names. An optional `ca_bundle` overrides the
Jira certificate bundle. See [settings.toml.example](../settings.toml.example).

The integration is disabled by default. Incomplete activation settings produce
a warning and leave it inactive.

## Scope and report contents

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

No references means no Phorge request. Phorge failures preserve the Jira/Tempo report and referenced review rows with unknown
states. Repository lookup failures preserve any resolved review states.

## Reviewer decisions and readiness

Reviewer decisions are enriched through the read-only
`differential.revision.search` endpoint with the `reviewers` attachment.
Each review in the JSON snapshot contains:

- `validation_count`: number of distinct reviewer entries in `accepted` state.
  An `accepted-older` decision does not count. A project reviewer counts as
  one entry, regardless of its number of members.
- `pending_required_approval_count`: number of blocking reviewer entries that
  have not accepted.
- `ready_to_close`: the calculated “À clôturer” indicator, true only for an
  open review meeting the configured validation and pending mandatory approval
  thresholds (defaults: at least two validations and zero pending approvals).
  Closed and abandoned reviews return false.

Missing, malformed or unsupported reviewer data leaves the counts null and
an open review's indicator null (indeterminate). Failure of this extra lookup
preserves the base review information and is logged without credentials.
Search requests are batched and paginated. These fields do not change the
Phorge state or close a revision. A “Ready to close” state badge appears in the
review table and ticket details for eligible reviews. The State filter selects
these candidates; their underlying Phorge state remains open.

## Ticket consistency warnings

The compact Reviews column shows a warning icon with an explanatory tooltip
when a completed issue has a known non-closed review, or when an unfinished
issue has all reviews closed or ready to close. Completion follows the report's
configured Jira categories. Empty reference lists and out-of-scope issues do
not trigger warnings. Unknown review states cannot establish readiness to
complete an issue. Abandoned reviews are excluded from all warning checks;
a ticket with only abandoned reviews behaves like a ticket without reviews.

## Reviewer details and authors

Each review row expands to show its raw Phorge status and reviewer details:
validators (check icon), mandatory
approvals pending (clock icon), and reviewers requesting changes (cross icon).
Only current `accepted` decisions are shown as validations. Reviewer names,
including project reviewers, are resolved in read-only `phid.query` batches
shared across reviews. Inaccessible names are replaced with a translated
placeholder without losing decisions or counts. JSON retains the reviewer
PHID, status, blocking flag and optional display name in `reviewers` (null
when reviewer data is unavailable, an empty list when there are no reviewers).


## Readiness thresholds

Both values must be non-negative integers. A candidate must be open, have at
least the configured number of validations, and at most the configured number
of mandatory approvals pending. Missing reviewer data remains indeterminate,
even with zero thresholds. Restart ReSprint and regenerate the report after
changing configuration. The same calculated indicator drives badges and ticket
consistency warnings. JSON includes the applied thresholds in
`code_reviews.closure_criteria` to make the report's calculation explicit.

## Author identity

The review table includes an Author column. Author and reviewer names share
read-only `phid.query` batches. Unavailable authors display a dash; the original
`author_phid` and optional `author_name` are retained in the JSON snapshot.
Author names are also searchable in the review table.
