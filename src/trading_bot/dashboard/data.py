"""Gathers everything the dashboard shows from the on-disk state.

Pure reads, defensive everywhere: any missing file is a "not started yet"
state, never an error — the dashboard must render usefully on day zero.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_JOURNAL_ROWS = 30
MAX_LOG_LINES = 40

# Windows: a windowless (pythonw) parent spawning a console subprocess pops
# a black console window without this flag. No-op elsewhere.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_GIT_REV_CACHE: dict[str, str] = {}


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn write must not break the dashboard
    return rows[-limit:] if limit is not None else rows


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except json.JSONDecodeError:
        return None


def _tail_text(path: Path, n_lines: int = MAX_LOG_LINES) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-n_lines:])


def _account_section(root: Path) -> dict[str, Any]:
    marks = read_jsonl(root / "equity.jsonl")
    fills = read_jsonl(root / "journal.jsonl", limit=MAX_JOURNAL_ROWS)
    state = read_json(root / "state.json")
    days_running = 0.0
    if len(marks) >= 2:
        first = datetime.fromisoformat(marks[0]["ts"])
        last = datetime.fromisoformat(marks[-1]["ts"])
        days_running = round((last - first).total_seconds() / 86_400, 1)
    return {
        "started": bool(marks),
        "n_marks": len(marks),
        "days_running": days_running,
        "last_mark": marks[-1] if marks else None,
        "equity_series": [[m["ts"], m.get("equity")] for m in marks if "equity" in m],
        "recent_fills": list(reversed(fills)),
        "state": state,
    }


def _guard_section(root: Path) -> dict[str, Any]:
    return {
        "killed": (root / "KILLED").exists(),
        "kill_note": _tail_text(root / "KILLED", 3),
        "state": read_json(root / "guard_state.json"),
        "log": read_jsonl(root / "guard_log.jsonl", limit=10),
    }


def _git_rev(base: Path) -> str:
    """Revision of the running code; cached — one lookup per server start."""
    key = str(base)
    if key not in _GIT_REV_CACHE:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=base,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=NO_WINDOW,
            )
            _GIT_REV_CACHE[key] = out.stdout.strip() or "unknown"
        except Exception:
            _GIT_REV_CACHE[key] = "unknown"
    return _GIT_REV_CACHE[key]


def _discover_strategies(base: Path) -> list[str]:
    names = set()
    for kind in ("paper", "live"):
        root = base / "data" / kind
        if root.exists():
            for child in root.iterdir():
                if child.is_dir() and child.name != "guard":
                    names.add(child.name)
    return sorted(names) if names else ["vol-target"]


def gather_status(base: Path) -> dict[str, Any]:
    """Everything the dashboard page needs, in one JSON-safe dict."""
    symbol_map = read_json(base / "config" / "symbol_map.json")
    strategies = {
        name: {
            "paper": _account_section(base / "data" / "paper" / name),
            "live": _account_section(base / "data" / "live" / name),
        }
        for name in _discover_strategies(base)
    }
    return {
        "strategies": strategies,
        "generated_at": datetime.now().astimezone().isoformat(),
        "git_rev": _git_rev(base),
        "strategy": "vol-target momentum (30% target vol), EW 8 symbols, 1.5x eval sizing",
        "plan": "CFD 1-step 5k @ $51.80 — gate: clean 2-week shakedown (target ~Jul 25)",
        "paper": _account_section(base / "data" / "paper" / "vol-target"),
        "live": _account_section(base / "data" / "live" / "vol-target"),
        "guard": _guard_section(base / "data" / "live" / "guard"),
        "runs_log": _tail_text(base / "data" / "paper" / "runs.log"),
        "symbol_map_present": symbol_map is not None,
        "checklist": [
            {"item": "Paper shakedown >= 2 weeks, no missed nightly runs", "auto": "days"},
            {"item": "Intraday guard built and tested", "done": True},
            {"item": "Buy eval, log firm credentials into MT5 terminal (human)", "done": False},
            {"item": "Dry run against firm server; write config/symbol_map.json", "auto": "map"},
            {"item": "Verify contract sizes / volume minimums per symbol", "done": False},
            {"item": "Flip scheduled task to --live (deliberate CLI step)", "done": False},
        ],
    }
