"""Dashboard tests: data gathering on empty/populated state, HTTP endpoints."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from martex_quant.dashboard.data import gather_status, read_jsonl
from martex_quant.dashboard.server import _bound_handler


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_gather_status_on_empty_directory(tmp_path: Path) -> None:
    """Day zero: nothing exists yet — must render, not raise."""
    status = gather_status(tmp_path)
    assert status["paper"]["started"] is False
    assert status["live"]["started"] is False
    assert status["guard"]["killed"] is False
    assert status["runs_log"] == ""
    assert status["symbol_map_present"] is False
    json.dumps(status)  # everything must be JSON-serializable


def test_gather_status_with_paper_history(tmp_path: Path) -> None:
    root = tmp_path / "data" / "paper" / "vol-target"
    write_jsonl(
        root / "equity.jsonl",
        [
            {"ts": "2026-07-11T00:10:00+00:00", "equity": 5000.0, "exposures": {"BTCUSDT": 0.0}},
            {"ts": "2026-07-13T00:10:00+00:00", "equity": 5012.5, "exposures": {"BTCUSDT": 0.9}},
        ],
    )
    write_jsonl(
        root / "journal.jsonl",
        [
            {
                "ts": "2026-07-12T00:10:00+00:00",
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": 0.01,
                "price": 64000.0,
                "fee": 0.64,
            }
        ],
    )
    status = gather_status(tmp_path)
    paper = status["paper"]
    assert paper["started"] and paper["n_marks"] == 2
    assert paper["days_running"] == 2.0
    assert paper["last_mark"]["equity"] == 5012.5
    assert paper["equity_series"] == [
        ["2026-07-11T00:10:00+00:00", 5000.0],
        ["2026-07-13T00:10:00+00:00", 5012.5],
    ]
    assert paper["recent_fills"][0]["symbol"] == "BTCUSDT"


def test_read_jsonl_survives_torn_write(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\n{"broken...\n{"b": 2}\n', encoding="utf-8")
    assert read_jsonl(p) == [{"a": 1}, {"b": 2}]


def test_killed_latch_visible(tmp_path: Path) -> None:
    guard = tmp_path / "data" / "live" / "guard"
    guard.mkdir(parents=True)
    (guard / "KILLED").write_text("2026-08-01 equity 4700 <= floor 4750\n", encoding="utf-8")
    status = gather_status(tmp_path)
    assert status["guard"]["killed"] is True
    assert "4700" in status["guard"]["kill_note"]


def _serve(tmp_path: Path) -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), lambda *a, **kw: _bound_handler(tmp_path, *a, **kw)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def test_http_endpoints(tmp_path: Path) -> None:
    server, port = _serve(tmp_path)
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "Trading Bot" in page

        status = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status").read())
        assert status["paper"]["started"] is False

        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/action/nonsense", method="POST")
        try:
            urllib.request.urlopen(req)
            raise AssertionError("unknown action must 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()


def test_run_action_inherits_full_environment(tmp_path: Path, monkeypatch) -> None:
    """Regression: a stripped env broke polars CPU detection in subprocesses.
    Actions must inherit the parent environment."""
    import os

    from martex_quant.dashboard import server

    monkeypatch.setenv("DASHBOARD_ENV_CANARY", "present")
    monkeypatch.setitem(
        server.ACTIONS,
        "env-canary",
        ["{py}", "-c", "import os; print(os.environ.get('DASHBOARD_ENV_CANARY', 'MISSING'))"],
    )
    result = server.run_action("env-canary", tmp_path)
    assert result["exit_code"] == 0
    assert "present" in result["output"]
    assert os.environ.get("DASHBOARD_ENV_CANARY") == "present"


def test_strategies_discovered_and_sectioned(tmp_path: Path) -> None:
    for name in ("vol-target", "rotation"):
        write_jsonl(
            tmp_path / "data" / "paper" / name / "equity.jsonl",
            [{"ts": "2026-07-11T00:10:00+00:00", "equity": 5000.0, "exposures": {}}],
        )
    (tmp_path / "data" / "live" / "guard").mkdir(parents=True)  # excluded
    status = gather_status(tmp_path)
    assert sorted(status["strategies"]) == ["rotation", "vol-target"]
    assert status["strategies"]["rotation"]["paper"]["started"] is True
    assert status["strategies"]["rotation"]["live"]["started"] is False
