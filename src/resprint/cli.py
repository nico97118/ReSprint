from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import requests

from resprint.config import Settings
from resprint.exporters.json import render_json
from resprint.exporters.markdown import render_markdown
from resprint.frontend.app import create_app
from resprint.frontend.report_page import render_html
from resprint.report import build_report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)

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
            tempo_team_id=args.tempo_team_id,
        )

        if args.format == "json":
            output = render_json(context.review, context.sprint, context.jql)
        elif args.format == "html":
            output = render_html(
                context.review,
                context.sprint,
                context.jira_base_url,
                context.jql,
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
            "Filtre JQL. Avec --sprint-id, le sprint est ajoute automatiquement. "
            "Sans --sprint-id, la requete definit les fiches de la periode."
        ),
    )
    parser.add_argument(
        "--tempo-team-id",
        type=int,
        help=("ID de l'equipe Tempo pour calculer les temps hors sprint/periode."),
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
        help="Source des temps consommes. Par defaut: RESPRINT_WORKLOG_SOURCE.",
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


def _validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    if args.serve:
        return
    has_period = args.sprint_start is not None and args.sprint_end is not None
    if args.sprint_id is None and not (args.jql and has_period):
        parser.error(
            "--sprint-id est requis, sauf avec --jql, --sprint-start et --sprint-end"
        )
    if args.sprint_id is None and args.board_id is not None:
        parser.error("--board-id ne peut etre utilise qu'avec --sprint-id")
