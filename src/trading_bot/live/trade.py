"""Live/dry-run trading against MT5.

    python -m trading_bot.live.trade --strategy vol-target             # DRY RUN
    python -m trading_bot.live.trade --strategy vol-target --live      # real orders

Same daily decision core as the paper trader (live/decision.py); MT5 is
execution only. Signals come from Binance data; fills happen at the firm.
DRY RUN is the default — --live is a deliberate, explicit flip.

Prerequisites for --live: MT5 terminal installed, logged into the firm
account, `pip install -e .[mt5]`, and the firm's actual symbol names
verified against DEFAULT_SYMBOL_MAP (override with --symbol-map file).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from trading_bot.live import decision
from trading_bot.live.mt5_broker import Mt5Broker

logger = logging.getLogger(__name__)

RISK_SCALE = 1.5  # phase5-realfirm.md: best pass rate at 1.5x for the 1-step account
DUST_FRACTION = 0.005  # skip rebalances under 0.5% of equity


def run_once(
    broker: Mt5Broker,
    collector: Any,
    strategy_name: str,
    root: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now if now is not None else decision.utcnow()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"
    state: dict[str, Any] = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"params": {}, "last_reselect": None}
    )

    frames = decision.fetch_frames(collector, now)
    if decision.needs_reselect(state["last_reselect"], state["params"], now):
        state["params"] = decision.reselect_params(frames, strategy_name)
        state["last_reselect"] = now.isoformat()
        logger.info("reselected params: %s", state["params"])

    equity = broker.equity()
    positions = broker.positions()
    outcomes = []
    exposures: dict[str, float] = {}
    for symbol in decision.SYMBOLS:
        df = frames[symbol]
        exposure = decision.current_exposure(strategy_name, state["params"][symbol], df)
        exposures[symbol] = exposure
        price = df["close"][-1]
        assert isinstance(price, float)
        target_units = exposure * RISK_SCALE * (equity / len(decision.SYMBOLS)) / price
        delta = target_units - positions.get(symbol, 0.0)
        if abs(delta) * price < equity * DUST_FRACTION:
            continue
        outcome = broker.place_market(symbol, delta)
        outcomes.append(outcome)
        with (root / "journal.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now.isoformat(), **asdict(outcome)}) + "\n")

    mark = {
        "ts": now.isoformat(),
        "equity": equity,
        "exposures": exposures,
        "params": dict(state["params"]),
        "orders": len(outcomes),
        "dry_run": broker.dry_run,
    }
    with (root / "equity.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(mark) + "\n")
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(state_path)
    logger.info(
        "%s run complete: equity %.2f, %d order(s)",
        "DRY-RUN" if broker.dry_run else "LIVE",
        equity,
        len(outcomes),
    )
    return mark


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m trading_bot.live.trade")
    parser.add_argument("--strategy", choices=list(decision.STRATEGIES), default="vol-target")
    parser.add_argument("--live", action="store_true", help="send REAL orders (default: dry run)")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--symbol-map", type=Path, default=None, help="JSON file overriding the symbol mapping"
    )
    args = parser.parse_args()

    from trading_bot.data.collectors.binance import BinanceCollector

    symbol_map = None
    if args.symbol_map is not None:
        symbol_map = json.loads(args.symbol_map.read_text(encoding="utf-8"))
    root = args.root if args.root is not None else Path("data/live") / args.strategy
    broker = Mt5Broker(symbol_map=symbol_map, dry_run=not args.live)
    broker.connect()
    try:
        mark = run_once(broker, BinanceCollector(), args.strategy, root)
        print(json.dumps(mark, indent=2))
    finally:
        broker.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
