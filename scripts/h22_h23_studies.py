"""H22 (crash-bounce, engine-grade) + H23 (incremental features).

.venv/Scripts/python scripts/h22_h23_studies.py
"""

from __future__ import annotations

import contextlib
import json
import random
from pathlib import Path

import polars as pl

from trading_bot.backtesting.metrics import compute_metrics
from trading_bot.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.strategies.event import CrashBounce

LEGACY8 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
N_BOOT = 5_000


def block_mean_ci(values: list[float], block: int, seed: int) -> tuple[float, float, float]:
    n = len(values)
    point = sum(values) / n
    if n <= block * 2:
        return point, float("nan"), float("nan")
    rng = random.Random(seed)
    n_blocks = n // block + 1
    means = []
    for _ in range(N_BOOT):
        total = 0.0
        cnt = 0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            total += sum(values[s : s + block])
            cnt += block
        means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))]


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
    arrays = [by_day[c].to_list() for c in ("a_sum", "a_n", "b_sum", "b_n")]
    n = by_day.height

    def prefix(xs: list[float]) -> list[float]:
        out = [0.0]
        for x in xs:
            out.append(out[-1] + float(x))
        return out

    pa, pan, pb, pbn = (prefix(x) for x in arrays)
    point = pa[n] / max(pan[n], 1.0) - pb[n] / max(pbn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // block + 1
    diffs = []
    for _ in range(N_BOOT):
        sa = na = sb = nb = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, n - block)
            e = s + block
            sa += pa[e] - pa[s]
            na += pan[e] - pan[s]
            sb += pb[e] - pb[s]
            nb += pbn[e] - pbn[s]
        if na > 0 and nb > 0:
            diffs.append(sa / na - sb / nb)
    diffs.sort()
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


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
    parts = []
    for symbol in universe:
        try:
            df = store.read(symbol, Interval.D1).sort("timestamp")
        except FileNotFoundError:
            continue
        df = df.select(
            pl.col("timestamp").alias("day"),
            "close",
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
        ).with_columns(
            r90=pl.col("close") / pl.col("close").shift(90) - 1.0,
            vol30=pl.col("ret").shift(1).rolling_std(30),
            fwd7=pl.col("close").shift(-7) / pl.col("close") - 1.0,
        )
        parts.append(df.with_columns(pl.lit(symbol).alias("symbol")))
    wide = pl.concat(parts).drop_nulls(["r90", "vol30", "fwd7"])

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
        values = fdf["funding"].to_list()
        pct: list[float | None] = []
        for i, v in enumerate(values):
            if i < 90:
                pct.append(None)
                continue
            window = values[i - 90 : i + 1]
            pct.append(sum(1 for w in window if w <= v) / len(window))
        fdf = fdf.with_columns(pl.Series("fpct", pct, dtype=pl.Float64)).with_columns(
            pl.col("day").cast(pl.Datetime("us", "UTC")), pl.lit(symbol).alias("symbol")
        )
        fparts.append(fdf.select("day", "symbol", "fpct"))
    funding = pl.concat(fparts)
    long_days = (
        wide.filter((pl.col("r90") > 0) & pl.col("symbol").is_in(LEGACY8))
        .with_columns(pl.col("day").cast(pl.Datetime("us", "UTC")))
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
