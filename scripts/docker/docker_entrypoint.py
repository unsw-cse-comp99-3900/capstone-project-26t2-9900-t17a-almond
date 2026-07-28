#!/usr/bin/env python3
"""Entrypoint for the self-contained Almond project Docker image."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path


# This entrypoint is stored below scripts/docker; the application root is /repo.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_dashboard_server(host: str, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PROJECT_ROOT))
    return http.server.ThreadingHTTPServer((host, port), handler)


def serve(host: str, port: int) -> int:
    server = create_dashboard_server(host, port)
    print("Almond project dashboard is available at:", flush=True)
    print(f"  http://localhost:{port}/outputs/index.html", flush=True)
    print(f"  http://localhost:{port}/robustness_experiments/showcase/deepwukong_pdg_showcase.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Almond dashboard.", flush=True)
    finally:
        server.server_close()
    return 0


def run_project_command(command: str, extra_args: list[str], host: str, port: int) -> int:
    commands = {
        "console": ["deepwukong_demo_console_v4.py"],
        "tests": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        "code-perturbations": ["robustness_experiments/code/code_perturbations.py"],
        "graph-perturbations": ["robustness_experiments/graph/graph_perturbations.py"],
    }
    dashboard_server: http.server.ThreadingHTTPServer | None = None
    dashboard_thread: threading.Thread | None = None
    environment = os.environ.copy()
    if command == "console":
        dashboard_server = create_dashboard_server(host, port)
        dashboard_thread = threading.Thread(target=dashboard_server.serve_forever, daemon=True)
        dashboard_thread.start()
        environment["ALMOND_DASHBOARD_BASE_URL"] = f"http://localhost:{port}"
        print(f"Project dashboards are also available at http://localhost:{port}/", flush=True)
    try:
        return subprocess.run(
            [sys.executable, *commands[command], *extra_args],
            cwd=PROJECT_ROOT,
            env=environment,
        ).returncode
    finally:
        if dashboard_server is not None:
            dashboard_server.shutdown()
            dashboard_server.server_close()
        if dashboard_thread is not None:
            dashboard_thread.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Almond DeepWuKong project container.")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "console", "tests", "code-perturbations", "graph-perturbations"],
        help="Container mode. The default serves the static project dashboards.",
    )
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help="Arguments forwarded to the selected project script.")
    parser.add_argument("--host", default="0.0.0.0", help="Dashboard bind address in serve mode.")
    parser.add_argument("--port", default=8000, type=int, help="Dashboard port in serve mode.")
    args = parser.parse_args()

    if args.command == "serve":
        if args.arguments:
            parser.error("serve mode does not accept extra script arguments")
        return serve(args.host, args.port)
    return run_project_command(args.command, args.arguments, args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
