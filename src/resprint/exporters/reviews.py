"""Markdown representation of the shared review snapshot."""

from resprint.exporters.common import escape_markdown_table
from resprint.frontend.i18n import t


def review_markdown(snapshot: dict, jira_base_url: str) -> list[str]:
    """Render the same review rows as the HTML report."""
    lines = [
        f"## {t('reviews.title')}",
        "",
    ]
    if snapshot.get("warning_detail"):
        lines.extend([snapshot["warning_detail"], ""])
    if snapshot["warning"]:
        lines.extend([t(snapshot["warning"]), ""])
    lines.extend(
        [
            " · ".join(
                f"{t('reviews.' + state)}: {count}"
                for state, count in snapshot["counts"].items()
            ),
            "",
        ]
    )
    columns = ("ref", "title_column", "state", "repository", "age", "issues")
    lines.extend(
        [
            "| " + " | ".join(t("reviews." + c) for c in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
    )
    for row in snapshot["items"]:
        values = [
            f"[{row['label']}]({row['url']})",
            row["title"] or "—",
            t("reviews." + row["state"])
            + (f" ({row['status_name']})" if row["status_name"] else ""),
            row["repository"] or "—",
            str(row["age_days"]) if row["age_days"] is not None else "—",
            ", ".join(
                f"[{key}]({jira_base_url}/browse/{key})" for key in row["issue_keys"]
            ),
        ]
        lines.append("| " + " | ".join(escape_markdown_table(v) for v in values) + " |")
    if not snapshot["items"]:
        lines.append(t("reviews.empty"))
    return lines + [""]
