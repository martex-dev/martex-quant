"""H59: is the live paper drawdown consistent with the backtest's own distribution?

    .venv/Scripts/python scripts/h59_drawdown_consistency.py

Pre-registered in docs/hypotheses/59-live-drawdown-consistency.md, committed
before the guarded window was analysed.

The null is the strategy's OWN backtested daily returns. The statistic is the
compounded return over K calendar days, K being the live record's calendar
span. The reported p is one-sided: the share of backtest windows at or below
the live result.

Two reference distributions are always printed together:

* every overlapping K-day window in the backtest — descriptive, and its
  windows are heavily dependent;
* a moving-block bootstrap — the inferential version.

If they disagree materially, the registration says that disagreement IS the
finding and no p-value is quoted.

Ledger: +0. This is a model-adequacy diagnostic on deployed specs, not an
edge search. It cannot produce an edge. The boundary, from the registration:
if any result here is used to justify a spec CHANGE, that change is a new
strategy with its own registration and ledger cost.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/tmp/h4x_streams"
PAPER = ROOT / "data/paper"

N_BOOT = 10_000
BLOCK = 5  # trading-week blocks, the corpus's day-block convention
SEEDS = {"rotation-stop": 5901, "rotation": 5902, "vol-target": 5903}

# Pre-registered bars. Read against cell 1; cell 3 is the control.
CONSISTENT, WATCH = 0.05, 0.01

# Declared cells: paper account -> the cached backtest stream it came from.
CELLS = {
    "rotation-stop": "rot_stop_stream",
    "rotation": "rot_champion_stream",
    "vol-target": "v1_stream",
}


@dataclass(frozen=True)
class LiveRecord:
    name: str
    start: datetime
    end: datetime
    first_equity: float
    last_equity: float
    marks: int

    @property
    def calendar_days(self) -> int:
        """Calendar span, NOT mark count.

        The paper record has a known gap (2026-07-22..07-27, recorded as a
        permanently FAILED gate). Counting marks would silently shorten the
        comparison window and flatter the result.
        """
        return (self.end - self.start).days

    @property
    def total_return(self) -> float:
        return self.last_equity / self.first_equity - 1.0


def read_live(name: str) -> LiveRecord:
    rows = [
        json.loads(line)
        for line in (PAPER / name / "equity.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    stamps = [datetime.fromisoformat(r["ts"]) for r in rows]
    return LiveRecord(
        name=name,
        start=stamps[0],
        end=stamps[-1],
        first_equity=float(rows[0]["equity"]),
        last_equity=float(rows[-1]["equity"]),
        marks=len(rows),
    )


def backtest_returns(stream: str) -> list[float]:
    """Cached streams come in both shapes the series store distinguishes:
    some hold an equity level, some hold returns directly. Differencing a
    return series, or reading a level as a return, would be silent and
    wrong — so the shape is dispatched on explicitly rather than assumed."""
    frame = pl.read_parquet(CACHE / f"{stream}.parquet")
    if "equity" in frame.columns:
        return frame["equity"].pct_change().drop_nulls().to_list()
    if "ret" in frame.columns:
        return frame["ret"].drop_nulls().to_list()
    raise KeyError(f"{stream}: expected an 'equity' or 'ret' column, got {frame.columns}")


def overlapping_window_returns(returns: list[float], k: int) -> list[float]:
    """Compounded return of every overlapping k-length window."""
    if k > len(returns):
        return []
    out: list[float] = []
    for start in range(len(returns) - k + 1):
        level = 1.0
        for r in returns[start : start + k]:
            level *= 1.0 + r
        out.append(level - 1.0)
    return out


def bootstrap_window_returns(returns: list[float], k: int, *, seed: int) -> list[float]:
    """Moving-block bootstrap: build k-day paths from resampled blocks.

    Blocks rather than single days because daily returns are not independent
    — volatility clusters, and independent resampling would understate how
    often a bad month happens.
    """
    rng = random.Random(seed)
    n = len(returns)
    if n < BLOCK:
        return []
    n_blocks = -(-k // BLOCK)  # ceil
    out: list[float] = []
    for _ in range(N_BOOT):
        level = 1.0
        taken = 0
        for _ in range(n_blocks):
            start = rng.randint(0, n - BLOCK)
            for r in returns[start : start + BLOCK]:
                if taken >= k:
                    break
                level *= 1.0 + r
                taken += 1
        out.append(level - 1.0)
    return out


def share_at_or_below(distribution: list[float], value: float) -> float:
    if not distribution:
        return float("nan")
    return sum(1 for x in distribution if x <= value) / len(distribution)


def verdict_for(p: float) -> str:
    if p >= CONSISTENT:
        return "CONSISTENT"
    return "WATCH" if p >= WATCH else "INCONSISTENT"


def context_lake() -> tuple[ParquetStore, str]:
    """The CURRENT lake for context, the frozen one only as a fallback.

    data/lake is deliberately frozen at 2026-07-09 so it can witness the
    published figures; it therefore cannot see the live window at all. The
    market-context question needs current data, so it reads data/lake-current
    and SAYS which lake it used — silently falling back would produce an
    answer about the wrong period.
    """
    current = ROOT / "data/lake-current"
    if current.is_dir():
        return ParquetStore(current), "data/lake-current"
    return ParquetStore(ROOT / "data/lake"), "data/lake (FROZEN — may not cover the window)"


def market_context(lake: ParquetStore, start: datetime, end: datetime) -> None:
    """Descriptive only, and not a cell. A long-only momentum book falling in
    a falling market is the least surprising outcome in finance; reporting the
    drawdown without saying what the market did would be misleading."""
    universe = json.loads((ROOT / "config/universe.json").read_text("utf-8"))["symbols"]
    moves: list[tuple[str, float]] = []
    for symbol in universe:
        try:
            frame = lake.read(symbol, Interval.D1)
        except FileNotFoundError:
            continue
        # The lake stores tz-aware ms timestamps; the paper marks parse as
        # µs. Cast the bounds to the column's own dtype rather than stripping
        # the zone, which would shift the window by the UTC offset.
        stamp = frame.schema["timestamp"]
        window = frame.filter(
            (pl.col("timestamp") >= pl.lit(start).cast(stamp))
            & (pl.col("timestamp") <= pl.lit(end).cast(stamp))
        )
        if window.height >= 2:
            moves.append((symbol, window["close"][-1] / window["close"][0] - 1.0))
    if not moves:
        print("  (no lake coverage for this window — context unavailable)")
        return
    btc = dict(moves).get("BTCUSDT")
    ranked = sorted(moves, key=lambda pair: pair[1], reverse=True)
    equal_weight = sum(m for _, m in moves) / len(moves)
    losers = sum(1 for _, m in moves if m < 0)
    print(f"  BTC over the same window       : {btc:+.2%}" if btc is not None else "  BTC: n/a")
    print(f"  equal-weight universe ({len(moves):>2} coins): {equal_weight:+.2%}")
    print(f"  coins down over the window     : {losers}/{len(moves)}")
    # The momentum books hold the TOP-ranked coins, so the universe average is
    # not the relevant benchmark on its own: what the leaders did is closer to
    # what the book could have earned.
    top = ranked[:5]
    print("  best 5 in the universe         : " + ", ".join(f"{s[:-4]} {m:+.1%}" for s, m in top))
    print(
        "  worst 5                        : "
        + ", ".join(f"{s[:-4]} {m:+.1%}" for s, m in ranked[-5:])
    )


def main() -> None:
    print("H59 — live paper record vs each strategy's OWN backtest distribution")
    print("Ledger +0 (diagnostic, not an edge search).\n")

    results: dict[str, str] = {}
    for name, stream in CELLS.items():
        live = read_live(name)
        returns = backtest_returns(stream)
        k = live.calendar_days

        overlapping = overlapping_window_returns(returns, k)
        booted = bootstrap_window_returns(returns, k, seed=SEEDS[name])
        p_overlap = share_at_or_below(overlapping, live.total_return)
        p_boot = share_at_or_below(booted, live.total_return)

        role = {
            "rotation-stop": "CELL 1 — DEPLOYED SPEC",
            "rotation": "CELL 2 — unstopped comparator",
            "vol-target": "CELL 3 — CONTROL (should be consistent)",
        }[name]
        print(f"=== {name}  [{role}] ===")
        print(
            f"  live: {live.total_return:+.2%} over {k} calendar days "
            f"({live.marks} marks, {live.start:%Y-%m-%d} -> {live.end:%Y-%m-%d})"
        )
        print(f"  backtest stream: {len(returns)} daily returns, {len(overlapping)} k-windows")
        print(f"  p (overlapping windows): {p_overlap:.4f}   -> {verdict_for(p_overlap)}")
        print(f"  p (block bootstrap)    : {p_boot:.4f}   -> {verdict_for(p_boot)}")

        if overlapping:
            worst = min(overlapping)
            print(f"  worst k-day window in the backtest: {worst:+.2%}")
        agree = verdict_for(p_overlap) == verdict_for(p_boot)
        if not agree:
            print("  ** the two references DISAGREE — per the registration, that")
            print("     disagreement is the finding and no p-value is quoted **")
        results[name] = verdict_for(p_boot) if agree else "DISAGREEMENT"
        print()

    print("=== descriptive context (NOT a cell, NOT a trial) ===")
    live = read_live("rotation-stop")
    lake, which = context_lake()
    print(f"  source: {which}")
    market_context(lake, live.start, live.end)

    print("\n=== VERDICT (pre-registered bars) ===")
    control = results.get("vol-target")
    if control == "INCONSISTENT":
        print("  CONTROL FAILED: vol-target is flagged inconsistent while roughly")
        print("  flat. The method is measuring itself. Run is VOID; no verdict is")
        print("  read from cells 1 or 2.")
        return
    print(f"  control (vol-target)     : {control} -> method not self-flagging")
    for name in ("rotation-stop", "rotation"):
        print(f"  {name:<24} : {results[name]}")

    deployed = results["rotation-stop"]
    print()
    if deployed == "CONSISTENT":
        print("  DEPLOYED SPEC: CONSISTENT -> no action; keep collecting marks.")
        print("  This is FAILURE TO REJECT on n=1 window, NOT evidence the")
        print("  strategy works. The registration commits to saying so.")
    elif deployed == "WATCH":
        print("  DEPLOYED SPEC: WATCH -> no spec change; re-run at 60 and 90 days.")
    else:
        print("  DEPLOYED SPEC: INCONSISTENT -> open the divergence hunt (costs,")
        print("  fills, universe composition, regime coverage of the backtest).")
        print("  Any resulting spec change is a NEW strategy with its own")
        print("  registration and ledger cost.")


if __name__ == "__main__":
    main()
