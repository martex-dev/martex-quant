"""H22 (crash-bounce, engine-grade) + H23 (incremental features).

.venv/Scripts/python scripts/h22_h23_studies.py
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import polars as pl

from trading_bot.backtesting.metrics import compute_metrics
from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.panel import (
    align_day_to_cache_precision,
    daily_panel,
    forward_return,
    momentum,
    trailing_percentile_rank,
    vol_excl_current,
)
from trading_bot.stats.bootstrap import daily_mean_ci, two_group_diff_ci
from trading_bot.strategies.event import CrashBounce

LEGACY8 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
N_BOOT = 5_000


def block_mean_ci(values: list[float], block: int, seed: int) -> tuple[float, float, float]:
    """Unweighted daily mean over held-day returns.

    This is the only caller with a 10-day block (H22 events are short) and
    the only one that returns NaN bounds on a series shorter than two
    blocks. Slice-summed rather than prefix-delta — preserved for its
    floating-point ordering.
    """
    ci = daily_mean_ci(
        values,
        block=block,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="slice_sum",
        short_series="error",
        nan_below=block * 2,
    )
    return ci.point, ci.low, ci.high


def day_diff_ci(panel: pl.DataFrame, seed: int, block: int = 30) -> tuple[float, float, float]:
    by_day = (
        panel.group_by("day")
        .agg(
            a_sum=pl.col("a").sum(),
            a_n=pl.col("a").is_not_null().sum(),
            b_sum=pl.col("b").sum(),
            b_n=pl.col("b").is_not_null().sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )
    a_sum, a_n, b_sum, b_n = (by_day[c].to_list() for c in ("a_sum", "a_n", "b_sum", "b_n"))
    ci = two_group_diff_ci(
        a_sum,
        a_n,
        b_sum,
        b_n,
        block=block,
        seed=seed,
        n_boot=N_BOOT,
        empty_denominator="guard",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def h22(store: ParquetStore) -> None:
    print("=== H22 crash-day alt bounce (engine-grade, full costs) ===")
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    frames = {}
    for symbol in universe:
        with contextlib.suppress(FileNotFoundError):
            frames[symbol] = store.read(symbol, Interval.D1)
    result = run_multi_backtest(
        frames, CrashBounce(), config=MultiBacktestConfig(initial_cash=10_000.0), warmup_bars=2
    )
    curve = result.equity_curve
    m = compute_metrics(curve, [], Interval.D1)
    day_ret = curve["equity"].pct_change().fill_null(0.0)
    # Active on BOTH the entry day (exposure>0 at its close) and the exit
    # morning (previous close exposure>0) — full event capture.
    active = (curve["exposure"] > 0.01) | (curve["exposure"].shift(1).fill_null(0.0) > 0.01)
    event_returns = [r for r, a in zip(day_ret.to_list(), active.to_list(), strict=True) if a]
    point, lo, hi = block_mean_ci(event_returns, block=10, seed=22)
    years = curve.height / 365.0
    ann = (result.final_equity / 10_000.0) ** (1 / years) - 1.0
    print(f"  {curve.height} days, {len(event_returns)} held days, {len(result.fills)} fills")
    print(f"  mean net held-day return {point:+.3%}  CI [{lo:+.3%}, {hi:+.3%}]")
    print(f"  annualized net {ann:+.2%}/yr  Sharpe {m.sharpe:.2f}  MDD {m.max_drawdown_pct:.1f}%")
    bar1 = lo > 0
    bar2 = ann >= 0.03
    print(
        f"  bar1 (CI>0) {'PASS' if bar1 else 'fail'}; bar2 (ann>=3%) "
        f"{'PASS' if bar2 else 'fail'} -> "
        f"{'ELIGIBLE (overlay/paper candidate)' if bar1 and bar2 else 'NOT eligible'}\n"
    )


def h23(store: ParquetStore) -> None:
    print("=== H23 incremental feature tests ===")
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    wide = daily_panel(
        store,
        universe,
        base_columns=("close", "ret"),
        feature_stages=[
            [momentum(90), vol_excl_current(30, name="vol30"), forward_return(7)],
        ],
        on_missing_symbol="skip",
        drop_nulls=("r90", "vol30", "fwd7"),
    )

    # 23a: shocks within momentum-flat subset
    flat = wide.filter(pl.col("r90") <= 0).with_columns(z=pl.col("ret") / pl.col("vol30"))
    p = flat.with_columns(
        a=pl.when(pl.col("z") >= 2).then(pl.col("fwd7")),
        b=pl.when(pl.col("z") < 2).then(pl.col("fwd7")),
    )
    n_a = p["a"].drop_nulls().len()
    point, lo, hi = day_diff_ci(p, seed=231)
    print(
        f"  23a shocks|momentum-flat: n={n_a}  diff {point:+.2%}  "
        f"CI [{lo:+.2%}, {hi:+.2%}]  {'PASS' if lo > 0 else 'fail'}"
    )

    # 23b: funding confirmation within momentum-long subset (legacy 8)
    fparts = []
    for symbol in LEGACY8:
        fdf = (
            pl.read_parquet(f"data/funding/{symbol}.parquet")
            .with_columns(pl.col("timestamp").dt.truncate("1d").alias("day"))
            .group_by("day", maintain_order=True)
            .agg(pl.col("rate").sum().alias("funding"))
            .sort("day")
        )
        ranks = trailing_percentile_rank(fdf["funding"].to_list(), window=90, skip_nulls=False)
        fdf = fdf.with_columns(pl.Series("fpct", ranks, dtype=pl.Float64)).with_columns(
            pl.col("day").cast(pl.Datetime("us", "UTC")), pl.lit(symbol).alias("symbol")
        )
        fparts.append(fdf.select("day", "symbol", "fpct"))
    funding = pl.concat(fparts)
    long_days = (
        align_day_to_cache_precision(
            wide.filter((pl.col("r90") > 0) & pl.col("symbol").is_in(LEGACY8))
        )
        .join(funding, on=["day", "symbol"], how="inner")
        .drop_nulls(["fpct"])
    )
    p = long_days.with_columns(
        a=pl.when(pl.col("fpct") >= 0.9).then(pl.col("fwd7")),
        b=pl.when((pl.col("fpct") > 0.1) & (pl.col("fpct") < 0.9)).then(pl.col("fwd7")),
    )
    n_a = p["a"].drop_nulls().len()
    point, lo, hi = day_diff_ci(p, seed=232)
    print(
        f"  23b high-funding|momentum-long: n={n_a}  diff {point:+.2%}  "
        f"CI [{lo:+.2%}, {hi:+.2%}]  {'PASS' if lo > 0 else 'fail'}"
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    h22(store)
    h23(store)


if __name__ == "__main__":
    main()
