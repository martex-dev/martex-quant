"""Dashboard HTTP server.

    python -m trading_bot.dashboard

Stdlib only, bound to 127.0.0.1 — never reachable from the network.
Actions run the same commands available on the CLI, as subprocesses, and
stream their output back to the page. Going live is intentionally absent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from trading_bot.dashboard.data import gather_status

PORT = 8765

# Action name -> argv (sys.executable substituted at runtime). Deliberately
# a fixed allowlist: the page can never compose arbitrary commands.
ACTIONS: dict[str, list[str]] = {
    "paper-run": ["{py}", "-m", "trading_bot.live.paper", "--strategy", "vol-target"],
    "mt5-dryrun": ["{py}", "-m", "trading_bot.live.trade", "--strategy", "vol-target"],
    "guard-check": ["{py}", "-m", "trading_bot.live.guard"],
    "data-report": ["{py}", "-m", "trading_bot.data.report"],
    "tests": ["{py}", "-m", "pytest", "-q", "--no-header"],
}
ACTION_TIMEOUT_S = 900


def run_action(name: str, base: Path) -> dict[str, Any]:
    argv = [a.replace("{py}", sys.executable) for a in ACTIONS[name]]
    try:
        proc = subprocess.run(
            argv,
            cwd=base,
            capture_output=True,
            text=True,
            timeout=ACTION_TIMEOUT_S,
            # Full environment: native-extension packages (polars) probe CPU
            # features at import and misbehave in a stripped env.
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return {"action": name, "exit_code": proc.returncode, "output": output[-8000:]}
    except subprocess.TimeoutExpired:
        return {"action": name, "exit_code": -1, "output": "timed out"}


class DashboardHandler(BaseHTTPRequestHandler):
    base: Path  # set via partial in serve()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # keep the console quiet; the page polls every 30s

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path in ("/", "/index.html"):
            page = (Path(__file__).parent / "page.html").read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._send_json(gather_status(self.base))
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        prefix = "/api/action/"
        if not self.path.startswith(prefix):
            self._send_json({"error": "not found"}, 404)
            return
        name = self.path[len(prefix) :]
        if name not in ACTIONS:
            self._send_json({"error": f"unknown action {name!r}"}, 400)
            return
        self._send_json(run_action(name, self.base))


def serve(base: Path, port: int = PORT) -> None:
    handler = partial(_bound_handler, base)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"dashboard: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    server.serve_forever()


def _bound_handler(base: Path, *args: Any, **kwargs: Any) -> DashboardHandler:
    handler_cls = type("BoundHandler", (DashboardHandler,), {"base": base})
    return handler_cls(*args, **kwargs)  # type: ignore[no-any-return]


if __name__ == "__main__":
    serve(Path.cwd())
