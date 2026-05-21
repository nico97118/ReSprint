from __future__ import annotations

import html
import json
from dataclasses import asdict

from sprint_review.models import IssueReviewItem, Sprint, SprintReview


def render_markdown(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    lines = [
        f"# Sprint review - {sprint.name}",
        "",
        f"Periode: {sprint.start_date.isoformat()} -> {sprint.end_date.isoformat()}",
        "",
    ]

    if not _has_items(review):
        lines.append("Aucune issue a signaler pour cette sprint review.")
        return "\n".join(lines) + "\n"

    lines.extend(
        _render_section(
            "Tickets termines",
            list(review.completed),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
            jira_base_url,
        )
    )
    lines.extend(
        _render_section(
            "Tickets non commences",
            list(review.not_started),
            jira_base_url,
        )
    )

    return "\n".join(lines) + "\n"


def _render_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend(["Aucun ticket.", ""])
        return lines

    lines.extend(
        [
            "| Issue key | Epopee | Priorite | FixVersion | Temps original estime | "
            "Temps restant estime | Temps total consomme | "
            "Temps consomme durant le sprint | "
            "Temps original depasse | "
            "Temps consomme par utilisateur | "
            "Commentaires durant le sprint |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for item in items:
        issue = item.issue
        issue_url = f"{jira_base_url}/browse/{issue.key}"
        lines.append(
            "| "
            f"[{issue.key}]({issue_url}) | "
            f"{_escape_table(issue.epic or '-')} | "
            f"{_escape_table(issue.priority or '-')} | "
            f"{_escape_table(_format_fix_versions(issue.fix_versions))} | "
            f"{_format_duration(issue.original_estimate_seconds)} | "
            f"{_format_duration(issue.remaining_estimate_seconds)} | "
            f"{_format_duration(item.total_seconds)} | "
            f"{_format_duration(item.tempo_seconds)} | "
            f"{_format_bool(item.is_over_original_estimate)} | "
            f"{_format_time_spent_by_user(item)} | "
            f"{_format_comments(item)} |"
        )

    lines.append("")
    return lines


def render_json(review: SprintReview, sprint: Sprint) -> str:
    payload = {
        "sprint": asdict(sprint),
        "completed": [_item_to_json(item) for item in review.completed],
        "unfinished_with_time": [
            _item_to_json(item) for item in review.unfinished_with_time
        ],
        "not_started": [_item_to_json(item) for item in review.not_started],
    }
    return json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n"


def render_html(
    review: SprintReview,
    sprint: Sprint,
    jira_base_url: str,
) -> str:
    title = f"Sprint review - {sprint.name}"
    sections = [
        ("Tickets termines", list(review.completed)),
        (
            "Tickets non termines avec du temps consomme",
            list(review.unfinished_with_time),
        ),
        ("Tickets non commences", list(review.not_started)),
    ]
    sections_html = "\n".join(
        _render_html_section(title, items, jira_base_url) for title, items in sections
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --border: #d7dde5;
      --header: #eef2f7;
      --text: #17202a;
      --muted: #5f6b7a;
      --accent: #0969da;
      --danger: #b42318;
      --ok: #1f7a4d;
      --background: #f7f8fa;
      --surface: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--background);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1 {{ margin: 0 0 4px; font-size: 28px; }}
    h2 {{ margin: 28px 0 12px; font-size: 20px; }}
    .period {{ margin: 0 0 24px; color: var(--muted); }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{
      background: var(--header);
      text-align: left;
      font-weight: 650;
      white-space: nowrap;
    }}
    td.numeric, th.numeric {{ text-align: right; white-space: nowrap; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 650; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); }}
    .badge {{
      display: inline-block;
      border: 1px solid var(--border);
      padding: 2px 8px;
      border-radius: 999px;
      white-space: nowrap;
      background: #fff;
    }}
    .badge-danger {{
      color: var(--danger);
      border-color: #f0b8b2;
      background: #fff4f2;
    }}
    .badge-ok {{ color: var(--ok); border-color: #addcc5; background: #effaf4; }}
    .stack {{ display: grid; gap: 4px; }}
    .comments {{ max-width: 380px; }}
    .empty {{ color: var(--muted); margin: 0 0 20px; }}
  </style>
</head>
<body>
  <main>
    <h1>{_html(title)}</h1>
    <p class="period">
      Periode: {_html(sprint.start_date.isoformat())}
      -> {_html(sprint.end_date.isoformat())}
    </p>
    {sections_html}
  </main>
</body>
</html>
"""


def _render_html_section(
    title: str,
    items: list[IssueReviewItem],
    jira_base_url: str,
) -> str:
    if not items:
        return (
            f"<section><h2>{_html(title)}</h2>"
            '<p class="empty">Aucun ticket.</p></section>'
        )

    rows = "\n".join(_render_html_row(item, jira_base_url) for item in items)
    return f"""<section>
  <h2>{_html(title)} <span class="muted">({len(items)})</span></h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Issue key</th>
          <th>Epopee</th>
          <th>Priorite</th>
          <th>FixVersion</th>
          <th class="numeric">Temps original estime</th>
          <th class="numeric">Temps restant estime</th>
          <th class="numeric">Temps total consomme</th>
          <th class="numeric">Temps sprint</th>
          <th>Depassement</th>
          <th>Temps sprint par utilisateur</th>
          <th>Commentaires sprint</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</section>"""


def _render_html_row(item: IssueReviewItem, jira_base_url: str) -> str:
    issue = item.issue
    issue_url = f"{jira_base_url}/browse/{issue.key}"
    overrun_class = "badge-danger" if item.is_over_original_estimate else "badge-ok"
    overrun = _html(_format_bool(item.is_over_original_estimate))
    return f"""<tr>
  <td><a href="{_html_attr(issue_url)}">{_html(issue.key)}</a></td>
  <td>{_html(issue.epic or "-")}</td>
  <td>{_html(issue.priority or "-")}</td>
  <td>{_html(_format_fix_versions(issue.fix_versions))}</td>
  <td class="numeric">{_html(_format_duration(issue.original_estimate_seconds))}</td>
  <td class="numeric">{_html(_format_duration(issue.remaining_estimate_seconds))}</td>
  <td class="numeric">{_html(_format_duration(item.total_seconds))}</td>
  <td class="numeric">{_html(_format_duration(item.tempo_seconds))}</td>
  <td><span class="badge {overrun_class}">{overrun}</span></td>
  <td>{_format_html_time_spent_by_user(item)}</td>
  <td class="comments">{_format_html_comments(item)}</td>
</tr>"""


def _item_to_json(item: IssueReviewItem) -> dict[str, object]:
    return {
        "key": item.issue.key,
        "summary": item.issue.summary,
        "epic": item.issue.epic,
        "priority": item.issue.priority,
        "fix_versions": list(item.issue.fix_versions),
        "status": item.issue.status,
        "status_category": item.issue.status_category,
        "assignee": item.issue.assignee,
        "original_estimate_seconds": item.issue.original_estimate_seconds,
        "remaining_estimate_seconds": item.issue.remaining_estimate_seconds,
        "is_over_original_estimate": item.is_over_original_estimate,
        "total_seconds": item.total_seconds,
        "total_hours": round(item.total_hours, 2),
        "tempo_seconds": item.tempo_seconds,
        "tempo_hours": round(item.tempo_hours, 2),
        "total_time_spent_by_user": [
            {
                "user": user_time.user,
                "seconds": user_time.seconds,
                "hours": round(user_time.hours, 2),
            }
            for user_time in item.total_time_spent_by_user
        ],
        "time_spent_by_user": [
            {
                "user": user_time.user,
                "seconds": user_time.seconds,
                "hours": round(user_time.hours, 2),
            }
            for user_time in item.time_spent_by_user
        ],
        "worklog_count": item.worklog_count,
        "authors": list(item.authors),
        "comments": [
            {
                "id": comment.id,
                "author": comment.author,
                "created_at": comment.created_at.isoformat(),
                "body": comment.body,
            }
            for comment in item.comments
        ],
    }


def _has_items(review: SprintReview) -> bool:
    return any(
        (
            review.completed,
            review.unfinished_with_time,
            review.not_started,
        )
    )


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours = seconds / 3600
    return f"{hours:.2f} h"


def _format_fix_versions(fix_versions: tuple[str, ...]) -> str:
    if not fix_versions:
        return "-"
    return ", ".join(fix_versions)


def _format_bool(value: bool) -> str:
    return "Oui" if value else "Non"


def _format_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return "-"

    return "<br>".join(
        _escape_table(f"{user_time.user}: {_format_duration(user_time.seconds)}")
        for user_time in item.time_spent_by_user
    )


def _format_html_time_spent_by_user(item: IssueReviewItem) -> str:
    if not item.time_spent_by_user:
        return '<span class="muted">-</span>'

    lines = (
        f"{_html(user_time.user)}: {_html(_format_duration(user_time.seconds))}"
        for user_time in item.time_spent_by_user
    )
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _format_html_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return '<span class="muted">-</span>'

    lines = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        lines.append(f"{_html(created)} - {_html(author)}: {_html(body)}")
    return f'<div class="stack">{"".join(f"<div>{line}</div>" for line in lines)}</div>'


def _format_comments(item: IssueReviewItem) -> str:
    if not item.comments:
        return "-"

    rendered_comments = []
    for comment in item.comments:
        author = comment.author or "Auteur inconnu"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M")
        body = comment.body or "(commentaire vide)"
        rendered_comments.append(_escape_table(f"{created} - {author}: {body}"))

    return "<br>".join(rendered_comments)
