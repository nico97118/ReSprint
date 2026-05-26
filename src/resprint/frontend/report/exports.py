from __future__ import annotations

import re
from urllib.parse import quote

from resprint.exporters.json import render_json
from resprint.exporters.markdown import render_markdown
from resprint.frontend.utils.html import html_attr
from resprint.models import Sprint, SprintReview


def render_export_actions(sprint: Sprint) -> str:
    basename = html_attr(f"resprint-{_filename_slug(sprint.name)}")
    return f"""<details
  class="report-export"
  data-report-export
  data-export-basename="{basename}"
>
  <summary class="report-export-trigger">
    <span class="button-content">
      <span class="mdi mdi-download" aria-hidden="true"></span>
      <span>Exporter</span>
      <span class="mdi mdi-chevron-down" aria-hidden="true"></span>
    </span>
  </summary>
  <div class="report-export-menu">
    <button type="button" data-export-option="json">JSON</button>
    <button type="button" data-export-option="markdown">Markdown</button>
  </div>
</details>"""


def report_export_json(review: SprintReview, sprint: Sprint, jql: str | None) -> str:
    return _script_text(render_json(review, sprint, jql))


def report_export_markdown(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    return _script_text(render_markdown(review, sprint, jira_base_url))


def jira_jql_url(jira_base_url: str, jql: str | None) -> str | None:
    if not jql:
        return None
    return f"{jira_base_url}/issues/?jql={quote(jql)}"


def _filename_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "rapport"


def _script_text(value: str) -> str:
    return (
        value.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
