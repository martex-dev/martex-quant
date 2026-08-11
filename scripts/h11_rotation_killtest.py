"""Hypothesis 11 kill test: cross-sectional relative-strength spread.

.venv/Scripts/python scripts/h11_rotation_killtest.py
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.stats.bootstrap import daily_mean_ci
from trading_bot.stats.significance import ci_above_zero

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
LOOKBACKS = [30, 90]
HORIZON = 7
TOP_K = 2
MIN_LISTED = 6
BLOCK_DAYS = 30
N_BOOT = 5_000


SEED = 11


def bootstrap_mean(values: list[float]) -> tuple[float, float, float]:
    """Unweighted daily mean: one spread value per day, so each draw
    contributes exactly BLOCK_DAYS to the denominator."""
    ci = daily_mean_ci(
        values,
        block=BLOCK_DAYS,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    wide: pl.DataFrame | None = None
    for symbol in SYMBOLS:
        part = store.read(symbol, Interval.D1).select("timestamp", pl.col("close").alias(symbol))
        wide = part if wide is None else wide.join(part, on="timestamp", how="full", coalesce=True)
    assert wide is not None
    wide = wide.sort("timestamp")

    closes = {s: wide[s].to_list() for s in SYMBOLS}
    n = wide.height
    passes = 0
    points = []
    print(f"{'L':>4} {'days':>6} {'mean top2-bot2 fwd7d':>21} {'95% CI':>22} verdict")
    for lookback in LOOKBACKS:
        spreads = []
        for i in range(lookback, n - HORIZON):
            scored = []
            for s in SYMBOLS:
                past, now, fwd = closes[s][i - lookback], closes[s][i], closes[s][i + HORIZON]
                if past is None or now is None or fwd is None:
                    continue
                scored.append((now / past - 1.0, fwd / now - 1.0))
            if len(scored) < MIN_LISTED:
                continue
            scored.sort(key=lambda x: x[0])
            bottom = [f for _, f in scored[:TOP_K]]
            top = [f for _, f in scored[-TOP_K:]]
            spreads.append(sum(top) / TOP_K - sum(bottom) / TOP_K)
        point, lo, hi = bootstrap_mean(spreads)
        ok = ci_above_zero(lo)
        passes += ok
        points.append(point)
        print(
            f"{lookback:>4} {len(spreads):>6} {point:>20.3%} "
            f"{'[' + f'{lo:+.3%}, {hi:+.3%}' + ']':>22} {'PASS' if ok else 'fail'}"
        )

    both_positive = all(p > 0 for p in points)
    verdict = passes >= 1 and both_positive
    outcome = "H11 PASSES — graduates to strategy-grade" if verdict else "H11 FAILS"
    print(f"\nVERDICT (>=1 CI>0 AND all point estimates >0): {outcome}")


if __name__ == "__main__":
    main()
