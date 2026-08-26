"""Intraday guard: the firm's rules, enforced BEFORE the firm enforces them.

    python -m martex_quant.live.guard [--live]

Designed to run every ~5 minutes via Task Scheduler. Stateless per
invocation; state lives in data/live/guard/. Two tripwires:

- DAILY: equity down >= 2.5% from the UTC day's starting equity
  (firm busts at 3%) -> flatten everything; stay flat until next UTC day.
- STATIC: equity <= $4,750 (firm busts at $4,700) -> flatten everything
  and write a KILLED file. The KILLED latch is never cleared by code;
  removing it is a deliberate human act after understanding what died.

The daily decision runner also refuses to trade while KILLED exists or
the daily trip is active for the current day.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from martex_quant.live.mt5_broker import Mt5Broker

logger = logging.getLogger(__name__)

DAILY_TRIP = 0.025  # flatten at -2.5% day loss; firm busts at -3%
STATIC_FLOOR = 4_750.0  # flatten + latch; firm busts at 4,700
KILL_FILE = "KILLED"


def check_once(
    broker: Mt5Broker,
    root: Path,
    now: datetime | None = None,
    daily_trip: float = DAILY_TRIP,
    static_floor: float = STATIC_FLOOR,
) -> dict[str, Any]:
    now = now if now is not None else datetime.now(tz=UTC)
    root.mkdir(parents=True, exist_ok=True)
    kill_path = root / KILL_FILE
    state_path = root / "guard_state.json"
    state: dict[str, Any] = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"day": None, "day_start_equity": None, "tripped": False}
    )

    equity = broker.equity()
    day = now.date().isoformat()
    if state["day"] != day:
        state.update({"day": day, "day_start_equity": equity, "tripped": False})

    action = "none"
    if kill_path.exists():
        # Latched: keep enforcing flat in case anything re-opened.
        if broker.positions():
            broker.flatten_all()
            action = "re-flatten (killed)"
        else:
            action = "killed (flat)"
    elif equity <= static_floor:
        broker.flatten_all()
        kill_path.write_text(
            f"{now.isoformat()} equity {equity:.2f} <= floor {static_floor:.2f}\n",
            encoding="utf-8",
        )
        state["tripped"] = True
        action = "STATIC FLOOR HIT — flattened and latched"
        logger.critical(action)
    else:
        day_start = float(state["day_start_equity"])
        day_loss = 1.0 - equity / day_start if day_start > 0 else 0.0
        if state["tripped"]:
            if broker.positions():
                broker.flatten_all()
                action = "re-flatten (daily trip active)"
            else:
                action = "daily trip active (flat)"
        elif day_loss >= daily_trip:
            broker.flatten_all()
            state["tripped"] = True
            action = f"DAILY TRIP at {day_loss:.2%} — flattened for the rest of the day"
            logger.warning(action)

    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(state_path)
    record = {"ts": now.isoformat(), "equity": equity, "action": action}
    if action != "none":
        with (root / "guard_log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    return record


def is_halted(root: Path, now: datetime | None = None) -> bool:
    """True when trading must not happen: latched kill, or the current UTC
    day's trip is active. The daily runner calls this before trading."""
    if (root / KILL_FILE).exists():
        return True
    state_path = root / "guard_state.json"
    if not state_path.exists():
        return False
    state = json.loads(state_path.read_text(encoding="utf-8"))
    now = now if now is not None else datetime.now(tz=UTC)
    is_today = state.get("day") == now.date().isoformat()
    return bool(state.get("tripped")) and is_today


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m martex_quant.live.guard")
    parser.add_argument("--live", action="store_true", help="really flatten (default: dry run)")
    parser.add_argument("--root", type=Path, default=Path("data/live/guard"))
    args = parser.parse_args()
    broker = Mt5Broker(dry_run=not args.live)
    broker.connect()
    try:
        record = check_once(broker, args.root)
        print(json.dumps(record))
    finally:
        broker.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
