"""Overnight kill-test batch: hypotheses 15-21.

    .venv/Scripts/python scripts/h15_21_killtests.py

Pre-registered in docs/hypotheses/15-21-overnight-batch.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.cross_section import ranking_spread_series
from trading_bot.features.panel import daily_panel as canonical_daily_panel
from trading_bot.features.panel import (
    forward_return,
    momentum,
    rolling_max_close,
    rolling_mean_close,
    rolling_mean_volume,
    trailing_percentile_rank,
    vol_excl_current,
)
from trading_bot.stats.bootstrap import daily_mean_ci, two_group_diff_ci

LEGACY8 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
BLOCK_DAYS = 30
N_BOOT = 5_000


# --- shared bootstrap machinery -------------------------------------------------


def diff_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float]:
    """Mean(a) - mean(b) with block bootstrap; a/b are value-or-null columns."""
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
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        empty_denominator="guard",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


def report(name: str, panel: pl.DataFrame, seed: int) -> bool:
    n_a = panel["a"].drop_nulls().len()
    point, lo, hi = diff_ci(panel, seed)
    sig = lo > 0 or hi < 0
    print(
        f"  {name:<52} n={n_a:>6}  diff {point:+.2%}  CI [{lo:+.2%}, {hi:+.2%}]  "
        f"{'SIGNAL' if sig else 'noise'}"
    )
    return sig


def mean_ci(values: list[float], seed: int) -> tuple[float, float, float]:
    """Unweighted: ``values`` is one spread per day, so every draw
    contributes exactly BLOCK_DAYS to the denominator."""
    ci = daily_mean_ci(
        values,
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


# --- panels ---------------------------------------------------------------------


def daily_panel(store: ParquetStore, symbols: list[str]) -> pl.DataFrame:
    return canonical_daily_panel(
        store,
        symbols,
        base_columns=("close", "volume", "ret"),
        feature_stages=[
            [
                momentum(7),
                momentum(30),
                momentum(14),
                vol_excl_current(10, name="vol10"),
                rolling_mean_close(90, name="ma90"),
                rolling_max_close(365, name="peak365"),
                rolling_mean_volume(7, name="v7"),
                rolling_mean_volume(30, name="v30"),
                forward_return(7),
                forward_return(30),
                forward_return(1),
            ],
        ],
        on_missing_symbol="skip",
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    wide = daily_panel(store, universe)
    print(f"wide daily panel: {wide.height} symbol-days\n")

    # --- H15 weekly crash bounce ---
    print("=== H15 weekly crash bounce ===")
    p15 = wide.drop_nulls(["r7", "fwd7"])
    crash = pl.col("r7") <= -0.15
    p = p15.with_columns(
        a=pl.when(crash).then(pl.col("fwd7")),
        b=pl.when(~crash).then(pl.col("fwd7")),
    )
    report("crash days (r7<=-15%) vs rest, fwd7", p, 151)
    p15v = p15.drop_nulls(["vol10"]).with_columns(vol10_ago=pl.col("vol10").shift(7).over("symbol"))
    p15v = p15v.drop_nulls(["vol10_ago"]).filter(crash)
    p = p15v.with_columns(
        a=pl.when(pl.col("vol10") < pl.col("vol10_ago")).then(pl.col("fwd7")),
        b=pl.when(pl.col("vol10") >= pl.col("vol10_ago")).then(pl.col("fwd7")),
    )
    report("crash + vol falling vs crash + vol rising, fwd7", p, 152)

    # --- H16 acceleration ranking spreads ---
    print("=== H16 cross-sectional short-momentum / acceleration ===")
    p16 = wide.drop_nulls(["r7", "r30", "fwd7"]).with_columns(
        accel=pl.col("r7") - (pl.col("r30") - pl.col("r7"))
    )
    rankings = [
        ("rank by 7d return", "r7", 161),
        ("rank by acceleration", "accel", 162),
        ("rank by 30d return (reference)", "r30", 163),
    ]
    for name, col, seed in rankings:
        # drop_nulls_on=None: p16 was already null-dropped at the call site
        # above, so this script must NOT drop again inside.
        spreads = ranking_spread_series(
            p16,
            col,
            outcome_column="fwd7",
            k=2,
            min_symbols=10,
            drop_nulls_on=None,
        )
        point, lo, hi = mean_ci(spreads, seed)
        sig = lo > 0
        print(
            f"  {name:<52} n={len(spreads):>6}  spread {point:+.3%}  "
            f"CI [{lo:+.3%}, {hi:+.3%}]  {'SIGNAL' if sig else 'noise'}"
        )

    # --- H17 fallen angel ---
    print("=== H17 fallen-angel recovery ===")
    p17 = wide.drop_nulls(["peak365", "r14", "fwd30"])
    angel = (pl.col("close") / pl.col("peak365") - 1.0 <= -0.50) & (pl.col("r14") >= 0.20)
    p = p17.with_columns(
        a=pl.when(angel).then(pl.col("fwd30")),
        b=pl.when(~angel).then(pl.col("fwd30")),
    )
    report("fallen angels (<=-50% off peak, +20%/14d) fwd30", p, 171)

    # --- H18 overextension ---
    print("=== H18 trend overextension ===")
    p18 = wide.drop_nulls(["ma90", "fwd7", "fwd30"]).with_columns(
        stretch=pl.col("close") / pl.col("ma90") - 1.0
    )
    # trailing 365d percentile of stretch, per symbol
    parts = []
    for _, grp in p18.group_by("symbol", maintain_order=True):
        ranks = trailing_percentile_rank(grp["stretch"].to_list(), window=365, skip_nulls=False)
        parts.append(grp.with_columns(pl.Series("spct", ranks, dtype=pl.Float64)))
    p18 = pl.concat(parts).drop_nulls(["spct"])
    hot = pl.col("spct") >= 0.95
    for horizon, seed in [("fwd7", 181), ("fwd30", 182)]:
        p = p18.with_columns(
            a=pl.when(hot).then(pl.col(horizon)),
            b=pl.when(~hot).then(pl.col(horizon)),
        )
        report(f"stretched (>=95th pct above 90d MA) {horizon}", p, seed)

    # --- H19 BTC -> alt lead-lag ---
    print("=== H19 BTC -> alt next-day lead-lag ===")
    btc = wide.filter(pl.col("symbol") == "BTCUSDT").select("day", pl.col("ret").alias("btc_ret"))
    alts = wide.filter(pl.col("symbol") != "BTCUSDT").join(btc, on="day").drop_nulls(["fwd1"])
    quiet = pl.col("btc_ret").abs() < 0.01
    for name, cond, seed in [
        ("BTC>+3% today -> alts next day (vs BTC quiet)", pl.col("btc_ret") > 0.03, 191),
        ("BTC<-3% today -> alts next day (vs BTC quiet)", pl.col("btc_ret") < -0.03, 192),
    ]:
        p = alts.with_columns(
            a=pl.when(cond).then(pl.col("fwd1")),
            b=pl.when(quiet).then(pl.col("fwd1")),
        )
        report(name, p, seed)

    # --- H20 sessions (hourly, legacy 8) ---
    print("=== H20 UTC session effects (hourly, legacy 8) ===")
    parts = []
    for symbol in LEGACY8:
        h = store.read(symbol, Interval.H1).sort("timestamp")
        parts.append(
            h.select(
                pl.col("timestamp"),
                pl.col("timestamp").dt.truncate("1d").alias("day"),
                (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret"),
            ).drop_nulls()
        )
    hourly = pl.concat(parts).with_columns(session=pl.col("timestamp").dt.hour() // 8)
    for sess, name, seed in [(0, "Asia 00-08", 201), (1, "EU 08-16", 202), (2, "US 16-24", 203)]:
        p = hourly.with_columns(
            a=pl.when(pl.col("session") == sess).then(pl.col("ret")),
            b=pl.when(pl.col("session") != sess).then(pl.col("ret")),
        )
        report(f"session {name} vs others (hourly mean)", p, seed)

    # --- H21 volume conviction among rotation picks ---
    print("=== H21 volume-conviction among top-2 momentum picks ===")
    p21 = wide.drop_nulls(["r30", "fwd7", "v7", "v30"])
    tops = []
    for _, grp in p21.group_by("day", maintain_order=True):
        if grp.height < 10:
            continue
        tops.append(grp.sort("r30").tail(2))
    picks = pl.concat(tops)
    p = picks.with_columns(
        a=pl.when(pl.col("v7") > pl.col("v30")).then(pl.col("fwd7")),
        b=pl.when(pl.col("v7") <= pl.col("v30")).then(pl.col("fwd7")),
    )
    report("top-2 picks: volume expanding vs contracting, fwd7", p, 211)


if __name__ == "__main__":
    main()
