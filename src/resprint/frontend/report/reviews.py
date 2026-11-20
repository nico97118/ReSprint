"""Review table using the report's existing sorting and filtering controls."""

from resprint.frontend.i18n import t
from resprint.frontend.utils.html import html_attr, html_text
from resprint.frontend.utils.table import (
    TableCell,
    TableColumn,
    TableFilter,
    TableRow,
    badge_cell,
    html_cell,
    link_cell,
    render_table_section,
    text_cell,
)
from resprint.frontend.utils.templates import render_template
from resprint.reviews import issue_review_inconsistency


def render_reviews(snapshot: dict | None, jira_base_url: str) -> str:
    """Render an optional review snapshot without performing network requests."""
    if snapshot is None:
        return ""
    rows = []
    for row in snapshot["items"]:
        rows.append(
            TableRow(
                cells={
                    "ref": link_cell(row["label"], row["url"], sort_value=row["id"]),
                    "title_column": text_cell(row["title"] or "—"),
                    "author": text_cell(row.get("author_name") or "—"),
                    "state": review_state_badge(
                        row["state"], row.get("ready_to_close")
                    ),
                    "repository": text_cell(row["repository"] or "—"),
                    "age": text_cell(
                        row["age_days"] if row["age_days"] is not None else "—",
                        sort_value=row["age_days"]
                        if row["age_days"] is not None
                        else -1,
                    ),
                    "issues": html_cell(
                        ", ".join(
                            link_cell(key, f"{jira_base_url}/browse/{key}").html
                            for key in row["issue_keys"]
                        )
                    ),
                },
                search_text=" ".join(str(v) for v in row.values()),
                details_html=render_template(
                    "components/report/review_detail.html",
                    status=row["status_name"] or "—",
                    decisions=review_decision_details(row).html,
                ),
            )
        )
    summary = " · ".join(
        f"{t('reviews.' + state)} {count}"
        for state, count in snapshot["counts"].items()
        if count > 0
    )
    notice = (
        f"<p role='alert'>{html_text(t(snapshot['warning']))}</p>"
        if snapshot["warning"]
        else ""
    )
    if snapshot.get("warning_detail"):
        notice += f"<p>{html_text(snapshot['warning_detail'])}</p>"
    table = render_table_section(
        section_id="code-reviews",
        title=t("reviews.title"),
        columns=[
            TableColumn(
                c,
                t("reviews." + c),
                sort_type="number" if c in ("ref", "age") else "text",
            )
            for c in (
                "ref",
                "title_column",
                "author",
                "state",
                "repository",
                "age",
                "issues",
            )
        ],
        rows=rows,
        filters=[
            TableFilter("state", t("reviews.state")),
            TableFilter("repository", t("reviews.repository")),
        ],
        empty_message=t("reviews.empty"),
    )
    return render_template(
        "components/report/reviews.html",
        summary=summary,
        notice=notice,
        table=table,
    )


def review_state_badge(state: str, ready_to_close: bool | None = None) -> TableCell:
    """Use one badge for the displayed state in the recap and ticket details."""
    if state == "open" and ready_to_close is True:
        return badge_cell(t("reviews.ready_to_close"), "review-ready")
    variant = {
        "open": "status-indeterminate",
        "closed": "status-done",
        "abandoned": "status-unknown",
        "unknown": "status-unknown",
    }.get(state, "status-unknown")
    return badge_cell(t("reviews." + state), variant)


def issue_review_count(
    snapshot: dict | None, key: str, is_done: bool | None = None
) -> TableCell:
    """Count closed reviews over all references, including unknowns."""
    refs = [
        row for row in (snapshot or {}).get("items", []) if key in row["issue_keys"]
    ]
    closed = sum(row["state"] == "closed" for row in refs)
    value = f"{closed}/{len(refs)}" if refs else "—"
    reason = issue_review_inconsistency(refs, is_done) if is_done is not None else None
    if reason:
        label = html_attr(t(reason))
        return html_cell(
            f'{html_text(value)} <span class="mdi mdi-alert-outline '
            f'issue-review-warning" role="img" aria-label="{label}" '
            f'title="{label}"></span>',
            sort_value=closed,
            class_name="issue-review-count",
        )
    return text_cell(value, sort_value=closed, class_name="issue-review-count")


def render_issue_reviews(snapshot: dict | None, key: str) -> str:
    """Render a named ticket detail section with review links and state badges."""
    if snapshot is None:
        return ""
    refs = [row for row in snapshot["items"] if key in row["issue_keys"]]
    if not refs:
        return ""
    content = (
        '<div class="stack">'
        + "".join(
            '<div class="issue-review-link">'
            + link_cell(row["label"], row["url"]).html
            + " "
            + review_state_badge(row["state"], row.get("ready_to_close")).html
            + "</div>"
            for row in refs
        )
        + "</div>"
    )
    return render_template(
        "components/report/issue_detail_expandable.html",
        classes="issue-detail-item issue-detail-item-wide issue-detail-item-expandable",
        label=t("reviews.title"),
        content=content,
        count=len(refs),
        expanded=True,
    )


def review_decision_details(row: dict) -> TableCell:
    """Show validators, pending mandatory reviewers and change requests."""
    entries = []
    for ref in row.get("reviewers") or []:
        state = ref["status"]
        if state == "accepted":
            kind, icon = "approved", "check-circle-outline"
        elif state == "rejected":
            kind, icon = "changes_requested", "close-circle-outline"
        elif ref["is_blocking"] or state == "blocking":
            kind, icon = "required_pending", "clock-alert-outline"
        else:
            continue
        entries.append(
            dict(
                kind=kind,
                icon=icon,
                label=t("reviews." + kind),
                name=ref.get("name") or t("reviews.reviewer_unavailable"),
            )
        )
    if not entries:
        return text_cell("—")
    return html_cell(
        render_template("components/report/review_decisions.html", entries=entries)
    )
