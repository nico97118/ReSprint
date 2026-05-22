from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import requests

from sprint_review.application.report_service import build_report
from sprint_review.config import Settings
from sprint_review.presentation.report import render_html, render_json, render_markdown
from sprint_review.webapp.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.serve and args.sprint_id is None:
        parser.error("--sprint-id est requis hors mode --serve")

    try:
        settings = Settings.from_env()

        if args.serve:
            app = create_app(settings)
            app.run(
                host=args.host,
                port=args.port,
                debug=False,
                use_reloader=False,
            )
            return 0

        context = build_report(
            settings,
            sprint_id=args.sprint_id,
            board_id=args.board_id,
            jql=args.jql,
            min_hours=args.min_hours,
            worklog_source=args.worklog_source,
            sprint_start=args.sprint_start,
            sprint_end=args.sprint_end,
            sprint_name=args.sprint_name,
        )

        if args.format == "json":
            output = render_json(context.review, context.sprint)
        elif args.format == "html":
            output = render_html(
                context.review,
                context.sprint,
                context.jira_base_url,
            )
        else:
            output = render_markdown(
                context.review,
                context.sprint,
                context.jira_base_url,
            )

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
        choices=("markdown", "json", "html"),
        default="markdown",
        help="Format de sortie.",
    )
    parser.add_argument(
        "--worklog-source",
        choices=("jira", "tempo"),
        help="Source des temps consommes. Par defaut: SPRINT_REVIEW_WORKLOG_SOURCE.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Lance l'interface web locale de selection de sprint.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Adresse d'ecoute du serveur web local.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port d'ecoute du serveur web local.",
    )
    parser.add_argument("--output", help="Chemin du fichier de sortie.")
    return parser
