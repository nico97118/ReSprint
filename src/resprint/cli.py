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
from resprint.frontend.i18n import configure_language
from resprint.frontend.report.page import render_html
from resprint.logging import configure_logging, get_logger
from resprint.report import build_report

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)

    try:
        settings = Settings.from_sources()
        configure_language(settings.language)
        configure_logging(settings.log_level)
        logger.debug("CLI arguments parsed: %s", args)
        logger.info("Starting ReSprint with output format %s", args.format)

        if args.serve:
            logger.info("Starting web server on %s:%s", args.host, args.port)
            app = create_app(settings)
            app.run(
                host=args.host,
                port=args.port,
                debug=False,
                use_reloader=False,
            )
            return 0

        logger.info("Building report from CLI")
        context = build_report(
            settings,
            sprint_id=args.sprint_id,
            jql=args.jql,
            min_hours=args.min_hours,
            sprint_start=args.sprint_start,
            sprint_end=args.sprint_end,
            sprint_name=args.sprint_name,
            tempo_worker_keys=tuple(args.tempo_worker),
            tempo_team_id=args.tempo_team_id,
        )

        if args.format == "json":
            logger.debug("Rendering JSON output")
            output = render_json(context.review, context.sprint, context.jql)
        elif args.format == "html":
            logger.debug("Rendering HTML output")
            output = render_html(
                context.review,
                context.sprint,
                context.jira_base_url,
                context.jql,
            )
        else:
            logger.debug("Rendering Markdown output")
            output = render_markdown(
                context.review,
                context.sprint,
                context.jira_base_url,
            )

        if args.output:
            logger.info("Writing report output to %s", args.output)
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            logger.debug("Writing report output to stdout")
            sys.stdout.write(output)
        logger.info("Report generation completed")
        return 0
    except (ValueError, requests.RequestException) as exc:
        logger.error("ReSprint failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a Jira sprint review by listing unfinished issues with "
            "Tempo time spent during the sprint."
        )
    )
    parser.add_argument(
        "--sprint-id",
        type=int,
        help="Jira sprint ID.",
    )
    parser.add_argument(
        "--sprint-start",
        type=date.fromisoformat,
        help=(
            "Sprint start date in YYYY-MM-DD format. "
            "Avoids the /rest/agile/1.0/sprint call."
        ),
    )
    parser.add_argument(
        "--sprint-end",
        type=date.fromisoformat,
        help=(
            "Sprint end date in YYYY-MM-DD format. "
            "Avoids the /rest/agile/1.0/sprint call."
        ),
    )
    parser.add_argument(
        "--sprint-name",
        help=(
            "Sprint name to display when --sprint-start and --sprint-end are provided."
        ),
    )
    parser.add_argument(
        "--jql",
        help=(
            "JQL filter. With --sprint-id, the sprint is added automatically. "
            "Without --sprint-id, the query defines the period issues."
        ),
    )
    parser.add_argument(
        "--tempo-team-id",
        type=int,
        help="Tempo team ID to compute out-of-sprint/period time.",
    )
    parser.add_argument(
        "--tempo-worker",
        action="append",
        default=[],
        help=(
            "Tempo worker key to compute out-of-sprint/period time. "
            "Can be provided multiple times."
        ),
    )
    parser.add_argument(
        "--min-hours",
        type=float,
        help="Minimum Tempo hours threshold to include an issue.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "html"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the local sprint selection web interface.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Local web server bind address.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Local web server port.",
    )
    parser.add_argument("--output", help="Output file path.")
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
            "--sprint-id is required unless --jql, --sprint-start and "
            "--sprint-end are provided"
        )
