"""Paper trader: the candidate system running forward, one day at a time.

    python -m trading_bot.live.paper --strategy vol-target
    python -m trading_bot.live.paper --strategy donchian

Run once per day, ideally shortly after 00:00 UTC. Each run:
1. fetches recent daily bars for the 8-symbol universe,
2. re-selects each symbol's parameter every 90 days on the trailing year
   (the same selection code path the walk-forward validation used),
3. replays the strategy over history to reconstruct its state, reads the
   current target exposure, and simulates fills at the newest close using
   the backtest cost model,
4. appends fills to journal.jsonl and an equity mark to equity.jsonl.

State lives in data/paper/<strategy>/. Honest deviation from the backtest
engine: the engine fills at the NEXT bar's open; the paper trader fills at
the newest closed bar's close — adjacent prices when run right after
midnight UTC. Measuring that gap (live-vs-backtest drift) is the point of
Phase 5.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from trading_bot.backtesting.history import History
from trading_bot.backtesting.research import select_param
from trading_bot.core.events import bars_from_frame
from trading_bot.data.collectors.binance import BinanceCollector
from trading_bot.data.models import Interval
from trading_bot.execution.simulated import ExecutionConfig
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import DonchianBreakout
from trading_bot.strategies.vol_target import VolTargetMomentum

logger = logging.getLogger(__name__)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
_BPS = 1e-4

STRATEGIES: dict[str, tuple[list[float], Callable[[float], Strategy], Callable[[float], int]]] = {
    "vol-target": (
        [7, 14, 30, 60, 90, 180],
        lambda p: VolTargetMomentum(int(p)),
        lambda p: max(int(p), 30) + 1,
    ),
    "donchian": (
        [10, 20, 40, 55, 80, 120],
        lambda p: DonchianBreakout(int(p)),
        lambda p: int(p) + 1,
    ),
}

RESELECT_DAYS = 90
TRAIN_DAYS = 365
FETCH_DAYS = 560  # train + max warmup + slack


class PaperTrader:
    def __init__(
        self,
        strategy_name: str,
        root: Path,
        collector: Any | None = None,
        initial_cash: float = 5_000.0,
        execution: ExecutionConfig | None = None,
    ) -> None:
        if strategy_name not in STRATEGIES:
            raise ValueError(f"unknown strategy {strategy_name!r}")
        self.strategy_name = strategy_name
        self.grid, self.factory, self.warmup_of = STRATEGIES[strategy_name]
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.collector = collector if collector is not None else BinanceCollector()
        self.execution = execution if execution is not None else ExecutionConfig()
        self.state = self._load_state(initial_cash)

    # -- state ---------------------------------------------------------------

    def _state_path(self) -> Path:
        return self.root / "state.json"

    def _load_state(self, initial_cash: float) -> dict[str, Any]:
        path = self._state_path()
        if path.exists():
            state: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return state
        return {
            "cash": initial_cash,
            "positions": {},  # symbol -> units
            "params": {},  # symbol -> chosen grid param
            "last_reselect": None,  # ISO date
        }

    def _save_state(self) -> None:
        tmp = self._state_path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        tmp.replace(self._state_path())

    def _append(self, filename: str, record: dict[str, Any]) -> None:
        with (self.root / filename).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # -- one daily cycle -------------------------------------------------------

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = now if now is not None else datetime.now(tz=UTC)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=FETCH_DAYS)

        frames: dict[str, pl.DataFrame] = {}
        for symbol in SYMBOLS:
            frames[symbol] = self.collector.fetch_ohlcv(symbol, Interval.D1, start, end)

        if self._needs_reselect(now):
            self._reselect(frames, now)

        prices: dict[str, float] = {}
        exposures: dict[str, float] = {}
        for symbol, df in frames.items():
            exposures[symbol] = self._current_exposure(symbol, df)
            close = df["close"][-1]
            assert isinstance(close, float)
            prices[symbol] = close

        equity = self._equity(prices)
        fills = []
        for symbol in SYMBOLS:
            target_units = exposures[symbol] * (equity / len(SYMBOLS)) / prices[symbol]
            delta = target_units - self.state["positions"].get(symbol, 0.0)
            notional = abs(delta) * prices[symbol]
            if notional < equity * 0.001:  # skip dust rebalances (<0.1% equity)
                continue
            fills.append(self._fill(symbol, delta, prices[symbol], frames[symbol], now))

        equity = self._equity(prices)
        mark = {
            "ts": now.isoformat(),
            "equity": equity,
            "cash": self.state["cash"],
            "exposures": exposures,
            "params": dict(self.state["params"]),
            "n_fills": len(fills),
        }
        self._append("equity.jsonl", mark)
        self._save_state()
        logger.info("paper run complete: equity %.2f, %d fill(s)", equity, len(fills))
        return mark

    # -- internals -------------------------------------------------------------

    def _needs_reselect(self, now: datetime) -> bool:
        last = self.state.get("last_reselect")
        if last is None or not self.state["params"]:
            return True
        return (now - datetime.fromisoformat(last)).days >= RESELECT_DAYS

    def _reselect(self, frames: dict[str, pl.DataFrame], now: datetime) -> None:
        for symbol, df in frames.items():
            train = df.tail(TRAIN_DAYS)
            param, sharpe = select_param(
                train, symbol, Interval.D1, self.grid, self.factory, self.warmup_of
            )
            self.state["params"][symbol] = param
            logger.info("reselected %s: param=%s (train sharpe %.2f)", symbol, param, sharpe)
        self.state["last_reselect"] = now.isoformat()

    def _current_exposure(self, symbol: str, df: pl.DataFrame) -> float:
        """Replay the strategy over history so stateful strategies (Donchian
        hysteresis) reconstruct their position correctly."""
        strategy = self.factory(self.state["params"][symbol])
        bars = bars_from_frame(df)
        history = History(bars)
        exposure = 0.0
        for _ in bars:
            history.advance()
            exposure = strategy.on_bar(history)
        return exposure

    def _fill(
        self, symbol: str, delta: float, price: float, df: pl.DataFrame, now: datetime
    ) -> dict[str, Any]:
        volume = df["volume"][-1]
        assert isinstance(volume, float)
        participation = min(abs(delta) / volume, 1.0) if volume > 0 else 1.0
        adverse = self.execution.half_spread_bps + self.execution.impact_bps * participation
        direction = 1.0 if delta > 0 else -1.0
        fill_price = price * (1.0 + direction * adverse * _BPS)
        fee = abs(delta) * fill_price * self.execution.fee_bps * _BPS

        self.state["cash"] -= delta * fill_price + fee
        self.state["positions"][symbol] = self.state["positions"].get(symbol, 0.0) + delta
        record = {
            "ts": now.isoformat(),
            "symbol": symbol,
            "side": "buy" if delta > 0 else "sell",
            "quantity": abs(delta),
            "price": fill_price,
            "fee": fee,
        }
        self._append("journal.jsonl", record)
        return record

    def _equity(self, prices: dict[str, float]) -> float:
        total = float(self.state["cash"])
        for sym, units in self.state["positions"].items():
            if sym in prices:
                total += float(units) * prices[sym]
        return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m trading_bot.live.paper")
    parser.add_argument("--strategy", choices=list(STRATEGIES), default="vol-target")
    parser.add_argument(
        "--root", type=Path, default=None, help="state dir (default data/paper/<strategy>)"
    )
    parser.add_argument("--cash", type=float, default=5_000.0)
    args = parser.parse_args()
    root = args.root if args.root is not None else Path("data/paper") / args.strategy
    trader = PaperTrader(args.strategy, root, initial_cash=args.cash)
    mark = trader.run_once()
    print(json.dumps(mark, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
