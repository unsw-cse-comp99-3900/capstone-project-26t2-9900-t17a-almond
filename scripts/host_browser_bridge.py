#!/usr/bin/env python3
"""Open validated Almond dashboard URLs in the host's default browser."""

from __future__ import annotations

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def is_allowed_dashboard_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1"}
        and parsed.port == 8000
        and parsed.path.startswith(("/outputs/", "/robustness_experiments/showcase/"))
    )


def make_handler(dry_run: bool) -> type[BaseHTTPRequestHandler]:
    class BrowserBridgeHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._respond(HTTPStatus.OK, {"status": "ready"})
                return
            if parsed.path != "/open":
                self._respond(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
                return
            url = parse_qs(parsed.query).get("url", [""])[0]
            if not is_allowed_dashboard_url(url):
                self._respond(HTTPStatus.BAD_REQUEST, {"error": "dashboard URL is not allowed"})
                return
            if not dry_run:
                webbrowser.open(url, new=2)
            self._respond(HTTPStatus.OK, {"opened": url, "dry_run": dry_run})

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _respond(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return BrowserBridgeHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Almond Docker dashboard selections to the host browser.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true", help="Validate requests without opening a browser.")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(args.dry_run))
    print(f"Almond browser bridge listening on port {args.port}.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
