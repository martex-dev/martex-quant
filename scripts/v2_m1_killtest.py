"""V2-H1 KILL TEST: is dominance direction predictive at all?

    .venv/Scripts/python scripts/v2_m1_killtest.py

Pre-registered (docs/research/v2-dominance-rotation-phase0.md) BEFORE
results: for lookbacks Ld in {14, 30, 60} days, does the SIGN of the
trailing dominance change predict the NEXT 30 days of BTC-minus-alts
relative return in the SAME direction (relative momentum persistence)?

PASS bar: the (dominance-rising minus dominance-falling) difference in
forward relative return is positive with a 95% block-bootstrap CI
excluding zero for >= 2 of 3 lookbacks. FAIL -> V2 ends at M1.

Trial ledger: +3 (total across program: 41).
"""

from __future__ import annotations

import statistics
from pathlib import Path

import polars as pl

from martex_quant.data.indices import dominance_series, equal_weight_index
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.panel import forward_return, relative_forward_return_difference
from martex_quant.stats.bootstrap import flag_split_ci
from martex_quant.stats.significance import ci_above_zero

ALTS = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
LOOKBACKS = [14, 30, 60]
HORIZON = 30  # forward days of relative return
BLOCK = 60  # bootstrap block length (days) — covers signal+horizon autocorrelation
N_BOOT = 5_000
SEED = 11
TREND_LOOKBACK = 90  # descriptive quadrant split only (not part of the pass bar)


def block_bootstrap_ci(
    values: list[float], flags: list[bool], n_boot: int = N_BOOT, block: int = BLOCK
) -> tuple[float, float, float]:
    """95% CI for mean(values[flags]) - mean(values[~flags]) under a moving-
    block bootstrap (preserves serial correlation of overlapping windows).

    The only 60-day-block caller in the corpus, and the only estimator that
    re-partitions raw observations per draw instead of accumulating
    pre-aggregated sums.
    """
    ci = flag_split_ci(values, flags, block=block, seed=SEED, n_boot=n_boot)
    return ci.point, ci.low, ci.high


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    btc = store.read("BTCUSDT", Interval.D1)
    alt_frames = {s: store.read(s, Interval.D1) for s in ALTS}
    alt_idx = equal_weight_index(alt_frames)
    dom = dominance_series(btc, alt_idx)

    # Aligned working frame: dominance, BTC close, alt level, market level.
    market_idx = equal_weight_index({"BTCUSDT": btc, **alt_frames})
    df = (
        dom.join(btc.select("timestamp", pl.col("close").alias("btc")), on="timestamp")
        .join(alt_idx.rename({"level": "alt"}), on="timestamp")
        .join(market_idx.rename({"level": "market"}), on="timestamp")
        .sort("timestamp")
    )
    print(
        f"aligned days: {df.height}  span: {df['timestamp'][0]:%Y-%m-%d} .. "
        f"{df['timestamp'][-1]:%Y-%m-%d}\n"
    )

    # Forward 30d relative return (BTC minus alt basket), decision at t.
    # DIFFERENCE of the two forward returns, not their ratio — at a 30-day
    # crypto horizon the two are materially different quantities.
    fwd_rel = relative_forward_return_difference(
        HORIZON, minuend="btc", subtrahend="alt", name="fwd_rel"
    )
    df = df.with_columns(
        **{fwd_rel.name: fwd_rel.expr},
        trend_up=pl.col("market") > pl.col("market").shift(TREND_LOOKBACK),
    )

    passes = 0
    print(
        f"{'Ld':>4} {'n':>6} {'E[rel|rising]':>14} {'E[rel|falling]':>15} "
        f"{'diff':>8} {'95% CI':>20} verdict"
    )
    for lookback in LOOKBACKS:
        sub = df.with_columns(
            rising=pl.col("dominance") > pl.col("dominance").shift(lookback)
        ).drop_nulls(["fwd_rel", "rising"])
        values = sub["fwd_rel"].to_list()
        flags = sub["rising"].to_list()
        point, lo, hi = block_bootstrap_ci(values, flags)
        mean_r = statistics.fmean([v for v, f in zip(values, flags, strict=True) if f])
        mean_f = statistics.fmean([v for v, f in zip(values, flags, strict=True) if not f])
        ok = ci_above_zero(lo)
        passes += ok
        print(
            f"{lookback:>4} {len(values):>6} {mean_r:>13.2%} {mean_f:>14.2%} "
            f"{point:>7.2%} {'[' + f'{lo:+.2%}, {hi:+.2%}' + ']':>20} "
            f"{'PASS' if ok else 'fail'}"
        )

    # Descriptive quadrant table (Ld=30), NOT part of the pass bar.
    print("\ndescriptive quadrant means of forward 30d returns (Ld=30, trend=90d):")
    legs = (
        forward_return(HORIZON, price_column="btc", name="btc_fwd"),
        forward_return(HORIZON, price_column="alt", name="alt_fwd"),
    )
    sub = df.with_columns(
        rising=pl.col("dominance") > pl.col("dominance").shift(30),
        **{f.name: f.expr for f in legs},
    ).drop_nulls(["btc_fwd", "alt_fwd", "rising", "trend_up"])
    for trend_up in (True, False):
        for rising in (True, False):
            cell = sub.filter((pl.col("trend_up") == trend_up) & (pl.col("rising") == rising))
            n = cell.height
            btc_m = cell["btc_fwd"].mean() or 0.0
            alt_m = cell["alt_fwd"].mean() or 0.0
            print(
                f"  trend {'UP  ' if trend_up else 'DOWN'} dom {'RISING ' if rising else 'FALLING'}"
                f" (n={n:>4}): fwd30 BTC {btc_m:+.2%}  ALT {alt_m:+.2%}"
            )

    outcome = "V2-H1 PASSES — proceed to M2" if passes >= 2 else "V2-H1 FAILS — V2 ends at M1"
    print(f"\nVERDICT (pre-registered bar: >=2/3 lookbacks with CI > 0): {passes}/3 -> {outcome}")


if __name__ == "__main__":
    main()
