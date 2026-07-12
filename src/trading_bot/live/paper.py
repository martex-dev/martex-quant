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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from trading_bot.data.collectors.binance import BinanceCollector
from trading_bot.execution.simulated import ExecutionConfig
from trading_bot.live.decision import (
    COMBINED,
    CROSS_SECTIONAL,
    STRATEGIES,
    SYMBOLS,
    crash_bounce_weights,
    current_exposure,
    fetch_frames,
    needs_reselect,
    reselect_params,
    rotation_stop_weights,
    rotation_weights,
    select_rotation_param,
)
from trading_bot.live.narrate import _trades_sentence as _ts
from trading_bot.live.narrate import narrate_rotation, narrate_vol_target

logger = logging.getLogger(__name__)

_BPS = 1e-4


class PaperTrader:
    def __init__(
        self,
        strategy_name: str,
        root: Path,
        collector: Any | None = None,
        initial_cash: float = 5_000.0,
        execution: ExecutionConfig | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        known = set(STRATEGIES) | CROSS_SECTIONAL | {COMBINED}
        if strategy_name not in known:
            raise ValueError(f"unknown strategy {strategy_name!r}")
        self.strategy_name = strategy_name
        self.is_cross_sectional = strategy_name in CROSS_SECTIONAL
        self.is_combined = strategy_name == COMBINED
        if symbols is not None:
            self.symbols = symbols
        elif self.is_cross_sectional:
            from trading_bot.live.decision import universe_symbols

            self.symbols = universe_symbols()  # rotation papers on the WIDE universe
        else:
            self.symbols = list(SYMBOLS)
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
        frames = fetch_frames(self.collector, now, symbols=self.symbols)

        if needs_reselect(self.state.get("last_reselect"), self.state["params"], now):
            if self.is_combined:
                self.state["params"] = {
                    "per_symbol": reselect_params(frames, "vol-target"),
                    "lookback": select_rotation_param(frames),
                }
            elif self.strategy_name == "crash-bounce":
                self.state["params"] = {"threshold": -0.03}  # fixed, never tuned
            elif self.is_cross_sectional:
                self.state["params"] = {
                    "lookback": select_rotation_param(
                        frames, stop=self.strategy_name == "rotation-stop"
                    )
                }
            else:
                self.state["params"] = reselect_params(frames, self.strategy_name)
            self.state["last_reselect"] = now.isoformat()
            logger.info("reselected params: %s", self.state["params"])

        prices: dict[str, float] = {}
        for symbol, df in frames.items():
            close = df["close"][-1]
            assert isinstance(close, float)
            prices[symbol] = close

        # ``fractions``: fraction of TOTAL equity per symbol, all paths.
        if self.is_combined:
            per_symbol = self.state["params"]["per_symbol"]
            vt_exposures = {
                s: current_exposure("vol-target", per_symbol[s], frames[s]) for s in SYMBOLS
            }
            rot = rotation_weights(frames, int(self.state["params"]["lookback"]))
            fractions = {
                s: 0.5 * (vt_exposures[s] / len(SYMBOLS)) + 0.5 * rot.get(s, 0.0) for s in SYMBOLS
            }
            exposures = dict(fractions)
        elif self.strategy_name == "crash-bounce":
            weights = crash_bounce_weights(frames)
            fractions = {s: weights.get(s, 0.0) for s in self.symbols}
            exposures = {s: f for s, f in fractions.items() if f > 0}
        elif self.strategy_name == "rotation-stop":
            weights, stopped = rotation_stop_weights(frames, int(self.state["params"]["lookback"]))
            fractions = {s: weights.get(s, 0.0) for s in self.symbols}
            exposures = {s: f for s, f in fractions.items() if f > 0}
        elif self.is_cross_sectional:
            weights = rotation_weights(frames, int(self.state["params"]["lookback"]))
            fractions = {s: weights.get(s, 0.0) for s in self.symbols}
            exposures = {s: f for s, f in fractions.items() if f > 0}
        else:
            exposures = {
                s: current_exposure(self.strategy_name, self.state["params"][s], frames[s])
                for s in SYMBOLS
            }
            fractions = {s: exposures[s] / len(SYMBOLS) for s in SYMBOLS}

        equity = self._equity(prices)
        fills = []
        for symbol in self.symbols:
            target_units = fractions[symbol] * equity / prices[symbol]
            delta = target_units - self.state["positions"].get(symbol, 0.0)
            notional = abs(delta) * prices[symbol]
            if notional < equity * 0.001:  # skip dust rebalances (<0.1% equity)
                continue
            fills.append(self._fill(symbol, delta, prices[symbol], frames[symbol], now))

        equity = self._equity(prices)
        if self.strategy_name == "crash-bounce":
            btc = frames.get("BTCUSDT")
            btc_ret = 0.0
            if btc is not None and btc.height >= 2:
                a, b = btc["close"][-2], btc["close"][-1]
                assert isinstance(a, float) and isinstance(b, float)
                btc_ret = b / a - 1.0
            if exposures:
                story = (
                    f"BTC fell {btc_ret:+.1%} yesterday — a crash day. History says "
                    f"altcoins bounce the day after, so it holds ALL "
                    f"{len(exposures)} alts equally for exactly one day. " + _ts(fills)
                )
            else:
                story = (
                    f"BTC moved {btc_ret:+.1%} yesterday — no crash (trigger is -3%). "
                    "This strategy only acts the day after BTC crashes; it waits in "
                    "cash. " + _ts(fills)
                )
        elif self.is_combined:
            from trading_bot.live.narrate import _trades_sentence

            trend_part = narrate_vol_target(
                frames, self.state["params"]["per_symbol"], vt_exposures, []
            ).removesuffix(" No trades were needed today.")
            rot_part = narrate_rotation(
                frames, int(self.state["params"]["lookback"]), rot, []
            ).removesuffix(" No trades were needed today.")
            story = (
                "This account runs BOTH strategies, half the money each. "
                f"TREND HALF: {trend_part} ROTATION HALF: {rot_part} " + _trades_sentence(fills)
            )
        elif self.strategy_name == "rotation-stop":
            story = narrate_rotation(
                frames, int(self.state["params"]["lookback"]), fractions, fills
            )
            if stopped:
                names = ", ".join(stopped[:3]) + (", …" if len(stopped) > 3 else "")
                story += (
                    f" Safety stop active on {len(stopped)} coin(s) ({names}): each fell more "
                    "than 2x its normal range from its recent high, so it is skipped until it "
                    "makes a fresh 30-day high."
                )
        elif self.is_cross_sectional:
            story = narrate_rotation(
                frames, int(self.state["params"]["lookback"]), fractions, fills
            )
        else:
            story = narrate_vol_target(frames, self.state["params"], exposures, fills)
        mark = {
            "ts": now.isoformat(),
            "equity": equity,
            "cash": self.state["cash"],
            "exposures": exposures,
            "params": dict(self.state["params"]),
            "n_fills": len(fills),
            "story": story,
        }
        self._append("equity.jsonl", mark)
        self._save_state()
        logger.info("paper run complete: equity %.2f, %d fill(s)", equity, len(fills))
        return mark

    # -- internals -------------------------------------------------------------

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
    parser.add_argument(
        "--strategy",
        choices=[*STRATEGIES, *sorted(CROSS_SECTIONAL), COMBINED],
        default="vol-target",
    )
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
