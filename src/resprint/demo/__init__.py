"""Self-contained local Jira, Tempo and Phorge demo using real HTTP clients."""

import signal
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

from werkzeug.serving import make_server

from resprint.config import Settings
from resprint.demo.data import REVIEW_FIELD, TOKEN
from resprint.demo.server import serve_fixture
from resprint.frontend.app import create_app
from resprint.logging import configure_logging

REPORT_PATH = "/report?sprint_id=456&tempo_team_id=42"
PARTICIPANTS_PATH = "/participants?sprint_id=456&tempo_team_id=42"


@contextmanager
def demo_services() -> Iterator[Settings]:
    """Start loopback fixtures with ephemeral ports and independent settings.

    This context is also reusable by integration tests. No local configuration,
    dotenv file, environment token or production server is read or modified.
    All fixture threads and sockets are stopped on exit.
    """
    from resprint.demo.mock_jira import create_mock_jira
    from resprint.demo.mock_phorge import create_mock_phorge

    with (
        serve_fixture(create_mock_jira()) as jira,
        serve_fixture(create_mock_phorge()) as phorge,
    ):
        yield Settings(
            jira_base_url=jira,
            jira_api_token=TOKEN,
            jira_rest_api_version="2",
            jira_project_key="ABC",
            jira_ca_bundle=None,
            done_status_categories=frozenset({"done"}),
            min_seconds=1,
            parent_field=None,
            log_level="warning",
            out_of_sprint_analysis=True,
            review_fields=(REVIEW_FIELD,),
            phorge_base_url=phorge,
            phorge_api_token=TOKEN,
            phorge_enabled_in_config=True,
        )


def _stop_on_signal(signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(128 + signum)


def run_demo(web_port: int) -> int:
    """Serve the local demo until interrupted, releasing every listener on exit."""
    if not 1 <= web_port <= 65535:
        print("ReSprint demo: choose a port between 1 and 65535.", file=sys.stderr)
        return 2
    previous_handlers = {
        sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        for sig in previous_handlers:
            signal.signal(sig, _stop_on_signal)
        with demo_services() as settings:
            configure_logging(settings.log_level)
            app = create_app(settings)
            server = make_server("127.0.0.1", web_port, app, threaded=True)
            try:
                print(
                    f"ReSprint demo ready at http://127.0.0.1:{web_port}/\n"
                    f"Report: http://127.0.0.1:{web_port}{REPORT_PATH}\n"
                    f"Participants: http://127.0.0.1:{web_port}{PARTICIPANTS_PATH}\n"
                    "Fictional project ABC, sprint 456, Tempo team 42.\n"
                    "Press Ctrl+C to stop.",
                    flush=True,
                )
                server.serve_forever()
            finally:
                server.server_close()
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"ReSprint demo: {exc}", file=sys.stderr)
        return 1
    except SystemExit as exc:
        # Werkzeug raises SystemExit(1) on an occupied HTTP port.
        return exc.code if isinstance(exc.code, int) else 1
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    return 0
