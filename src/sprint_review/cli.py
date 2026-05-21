from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from pathlib import Path

import requests

from sprint_review.analyzer import build_sprint_review
from sprint_review.config import Settings
from sprint_review.jira_client import JiraClient
from sprint_review.models import IssueReviewItem, Sprint, SprintReview
from sprint_review.report import render_json, render_markdown
from sprint_review.tempo_client import TempoClient


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        min_seconds = (
            int(args.min_hours * 3600)
            if args.min_hours is not None
            else settings.min_seconds
        )

        jira = JiraClient(
            settings.jira_base_url,
            settings.jira_username,
            settings.jira_api_token,
            settings.epic_field,
            settings.jira_auth_method,
            settings.jira_rest_api_version,
        )
        worklog_source = args.worklog_source or settings.worklog_source
        if worklog_source == "tempo" and not settings.tempo_api_token:
            raise ValueError("TEMPO_API_TOKEN est requis avec --worklog-source tempo")
        tempo = (
            TempoClient(settings.tempo_api_token)
            if worklog_source == "tempo" and settings.tempo_api_token
            else None
        )

        sprint = _resolve_sprint(args, jira)
        if args.jql:
            jql = f"({args.jql}) AND sprint = {args.sprint_id}"
            issues = jira.search_issues(jql)
        else:
            issues = jira.get_sprint_issues(args.sprint_id, args.board_id)

        total_worklogs_by_issue_id = None
        if tempo:
            worklogs_by_issue_id = {
                issue.id: tempo.get_issue_worklogs(
                    issue.id,
                    sprint.start_date,
                    sprint.end_date,
                )
                for issue in issues
            }
        else:
            total_worklogs_by_issue_id = {
                issue.id: jira.get_all_issue_worklogs(issue.key) for issue in issues
            }
            worklogs_by_issue_id = {
                issue.id: [
                    worklog
                    for worklog in total_worklogs_by_issue_id[issue.id]
                    if sprint.start_date <= worklog.start_date <= sprint.end_date
                ]
                for issue in issues
            }
        review = build_sprint_review(
            issues,
            worklogs_by_issue_id,
            settings.done_status_categories,
            min_seconds,
            total_worklogs_by_issue_id,
        )
        review = _with_comments(
            review,
            (
                replace(
                    item,
                    comments=tuple(
                        jira.get_issue_comments(
                            item.issue.key,
                            sprint.start_date,
                            sprint.end_date,
                        )
                    ),
                )
                for item in _iter_review_items(review)
            ),
        )

        if args.format == "json":
            output = render_json(review, sprint)
        else:
            output = render_markdown(review, sprint, settings.jira_base_url)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0
    except (ValueError, requests.RequestException) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare une sprint review Jira en listant les issues non terminees "
            "avec du temps Tempo consomme pendant le sprint."
        )
    )
    parser.add_argument(
        "--sprint-id",
        type=int,
        required=True,
        help="ID du sprint Jira.",
    )
    parser.add_argument(
        "--sprint-start",
        type=date.fromisoformat,
        help=(
            "Date de debut du sprint au format YYYY-MM-DD. "
            "Evite l'appel /rest/agile/1.0/sprint."
        ),
    )
    parser.add_argument(
        "--sprint-end",
        type=date.fromisoformat,
        help=(
            "Date de fin du sprint au format YYYY-MM-DD. "
            "Evite l'appel /rest/agile/1.0/sprint."
        ),
    )
    parser.add_argument(
        "--sprint-name",
        help=(
            "Nom du sprint a afficher quand --sprint-start et --sprint-end "
            "sont fournis."
        ),
    )
    parser.add_argument(
        "--board-id",
        type=int,
        help=(
            "ID du board Jira Software. Si absent, le script utilise JQL sprint = <id>."
        ),
    )
    parser.add_argument(
        "--jql",
        help=(
            "Filtre JQL additionnel, par exemple 'project = ABC'. "
            "Le sprint est ajoute automatiquement."
        ),
    )
    parser.add_argument(
        "--min-hours",
        type=float,
        help="Seuil minimal d'heures Tempo pour remonter une issue.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format de sortie.",
    )
    parser.add_argument(
        "--worklog-source",
        choices=("jira", "tempo"),
        help="Source des temps consommes. Par defaut: SPRINT_REVIEW_WORKLOG_SOURCE.",
    )
    parser.add_argument("--output", help="Chemin du fichier de sortie.")
    return parser


def _resolve_sprint(args: argparse.Namespace, jira: JiraClient) -> Sprint:
    if args.sprint_start or args.sprint_end:
        if not args.sprint_start or not args.sprint_end:
            raise ValueError(
                "--sprint-start et --sprint-end doivent etre fournis ensemble"
            )
        return Sprint(
            id=args.sprint_id,
            name=args.sprint_name or f"Sprint {args.sprint_id}",
            start_date=args.sprint_start,
            end_date=args.sprint_end,
        )
    return jira.get_sprint(args.sprint_id)


def _iter_review_items(review: SprintReview) -> Iterable[IssueReviewItem]:
    yield from review.completed
    yield from review.unfinished_with_time
    yield from review.not_started


def _with_comments(
    review: SprintReview,
    enriched_items: Iterable[IssueReviewItem],
) -> SprintReview:
    by_key = {item.issue.key: item for item in enriched_items}
    return SprintReview(
        completed=tuple(by_key[item.issue.key] for item in review.completed),
        unfinished_with_time=tuple(
            by_key[item.issue.key] for item in review.unfinished_with_time
        ),
        not_started=tuple(by_key[item.issue.key] for item in review.not_started),
    )
