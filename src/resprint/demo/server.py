"""Shared lifecycle utilities for local HTTP fixtures."""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Thread

from flask import Flask
from werkzeug.serving import WSGIRequestHandler, make_server


class QuietHandler(WSGIRequestHandler):
    """Suppress fixture access noise while keeping the application logs visible."""

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        pass


@contextmanager
def serve_fixture(app: Flask) -> Iterator[str]:
    """Serve a fixture on a free loopback port and release it on every exit."""
    server = make_server(
        "127.0.0.1", 0, app, threaded=True, request_handler=QuietHandler
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def run_fixture(app: Flask) -> None:
    """Run a standalone fixture, including in the isolated Docker smoke network."""
    parser = argparse.ArgumentParser(description=app.name)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
