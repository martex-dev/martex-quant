"""Time-series & structure kill-test batch: hypotheses 33-40.

    .venv/Scripts/python scripts/h33_40_killtests.py

Pre-registered in docs/hypotheses/33-40-timeseries-batch.md.
"""

from __future__ import annotations

import json
import statistics
from itertools import combinations
from pathlib import Path

import polars as pl

from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.panel import (
    align_day_to_cache_precision,
    forward_return,
    momentum,
    relative_forward_return_ratio,
    rolling_max_close,
    rolling_mean_of,
    true_range,
)
from martex_quant.features.panel import daily_panel as canonical_daily_panel
from martex_quant.stats.bootstrap import event_mean_ci as _event_mean_ci
from martex_quant.stats.bootstrap import two_group_diff_ci
from martex_quant.stats.significance import ci_excludes_zero

LEGACY8 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
PERP_DIR = Path("data/perp")
BLOCK_DAYS = 30
N_BOOT = 5_000
MIN_COINS = 10


# --- shared bootstrap machinery (H15-21) ------------------------------------------


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
    sig = ci_excludes_zero(lo, hi)
    print(
        f"  {name:<56} n={n_a:>6}  diff {point:+.2%}  CI [{lo:+.2%}, {hi:+.2%}]  "
        f"{'SIGNAL' if sig else 'noise'}"
    )
    return sig


def event_mean_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float]:
    """Count-weighted mean of an event-day value column.

    Unlike h44_50's copy this one does NOT clamp the block start, and it
    counts non-nulls explicitly rather than via ``count()``. Both are kept
    as this call site's history.
    """
    by_day = (
        panel.group_by("day")
        .agg(v_sum=pl.col("v").sum(), v_n=pl.col("v").is_not_null().sum())
        .sort("day")
        .fill_null(0.0)
    )
    ci = _event_mean_ci(
        by_day["v_sum"].to_list(),
        by_day["v_n"].to_list(),
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    return ci.point, ci.low, ci.high


# --- panel -------------------------------------------------------------------------


def daily_panel(store: ParquetStore, symbols: list[str]) -> pl.DataFrame:
    """Two stages: atr14 reads the tr column the first stage produces."""
    return canonical_daily_panel(
        store,
        symbols,
        base_columns=("close", "high", "low", "ret"),
        feature_stages=[
            [
                momentum(30),
                momentum(90),
                momentum(180),
                rolling_max_close(30, name="hi30"),
                true_range(),
                forward_return(7),
                forward_return(30),
            ],
            [rolling_mean_of("tr", 14, name="atr14")],
        ],
        on_missing_symbol="skip",
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    wide = daily_panel(store, universe)
    print(f"wide daily panel: {wide.height} symbol-days\n")

    # --- H33 multi-horizon blend ---
    print("=== H33 multi-horizon momentum blend ===")
    p33 = wide.drop_nulls(["r30", "r90", "r180", "fwd7"]).with_columns(
        score=(pl.col("r30") > 0).cast(pl.Int32)
        + (pl.col("r90") > 0).cast(pl.Int32)
        + (pl.col("r180") > 0).cast(pl.Int32)
    )
    for s in range(4):
        sub = p33.filter(pl.col("score") == s)
        print(f"  E[fwd7 | score={s}] = {sub['fwd7'].mean():+.3%}  (n={sub.height})")
    p = p33.filter(pl.col("score") >= 1).with_columns(
        a=pl.when(pl.col("score") == 3).then(pl.col("fwd7")),
        b=pl.when(pl.col("score") < 3).then(pl.col("fwd7")),
    )
    report("score=3 vs score 1-2, fwd7", p, 3310)

    # --- H34 basis momentum, incremental to momentum ---
    print("=== H34 basis momentum | r90>0 (legacy 8, perp cache) ===")
    parts = []
    for symbol in LEGACY8:
        cache = PERP_DIR / f"{symbol}.parquet"
        if not cache.exists():
            continue
        perp = align_day_to_cache_precision(pl.read_parquet(cache))
        spot = align_day_to_cache_precision(wide.filter(pl.col("symbol") == symbol))
        df = (
            perp.join(spot, on="day", how="inner")
            .sort("day")
            .with_columns(basis=pl.col("perp_close") / pl.col("close") - 1.0)
            .with_columns(d_basis7=pl.col("basis") - pl.col("basis").shift(7))
        )
        parts.append(df)
    p34 = pl.concat(parts).drop_nulls(["d_basis7", "r90", "fwd7"]).filter(pl.col("r90") > 0)
    p = p34.with_columns(
        a=pl.when(pl.col("d_basis7") > 0).then(pl.col("fwd7")),
        b=pl.when(pl.col("d_basis7") <= 0).then(pl.col("fwd7")),
    )
    report("rising basis vs falling basis | momentum long, fwd7", p, 3410)

    # --- H35 pairs ratio stat-arb ---
    print("=== H35 pairs / ratio stat-arb (legacy 8, 28 pairs, |z|>=1.5) ===")
    closes = {s: wide.filter(pl.col("symbol") == s).select("day", "close") for s in LEGACY8}
    event_parts = []
    for a_sym, b_sym in combinations(LEGACY8, 2):
        df = (
            closes[a_sym]
            .join(closes[b_sym], on="day", suffix="_b")
            .sort("day")
            .with_columns(lr=(pl.col("close") / pl.col("close_b")).log())
        )
        # RATIO of forward returns — what the pairs trade earns. Distinct from
        # the difference form used by v2_m1; the two are not interchangeable.
        fwd_ratio = relative_forward_return_ratio(
            7, numerator="close", denominator="close_b", name="fwd_ratio"
        )
        df = df.with_columns(
            z=(pl.col("lr") - pl.col("lr").rolling_mean(90)) / pl.col("lr").rolling_std(90),
            **{fwd_ratio.name: fwd_ratio.expr},
        ).drop_nulls(["z", "fwd_ratio"])
        events = df.filter(pl.col("z").abs() >= 1.5).with_columns(
            v=pl.when(pl.col("z") > 0).then(-pl.col("fwd_ratio")).otherwise(pl.col("fwd_ratio"))
        )
        event_parts.append(events.select("day", "v"))
    p35 = pl.concat(event_parts)
    pt, lo, hi = event_mean_ci(p35, 3510)
    sig = ci_excludes_zero(lo, hi)
    print(
        f"  signed fwd7 ratio return on |z|>=1.5 (reversion claim >0)      "
        f"n={p35.height:>6}  mean {pt:+.2%}  CI [{lo:+.2%}, {hi:+.2%}]  "
        f"{'SIGNAL' if sig else 'noise'}"
    )

    # --- H36 short-leg viability ---
    print("=== H36 short-leg viability (bottom-2 by r90) ===")
    p36 = wide.drop_nulls(["r90", "fwd7"])
    bots = []
    for _, grp in p36.group_by("day", maintain_order=True):
        if grp.height < MIN_COINS:
            continue
        bots.append(grp.sort("r90").head(2).select("day", "symbol"))
    bot_keys = pl.concat(bots).with_columns(pl.lit(1).alias("is_bot"))
    p36 = p36.join(bot_keys, on=["day", "symbol"], how="left")
    p = p36.with_columns(
        a=pl.when(pl.col("is_bot") == 1).then(pl.col("fwd7")),
        b=pl.when(pl.col("is_bot").is_null()).then(pl.col("fwd7")),
    )
    report("bottom-2 vs rest, fwd7 (short claim: CI<0)", p, 3610)

    # --- per-day cross-sectional stats for H37/H38/H39 ---
    daily_rows = []
    ret_pivot = (
        wide.select("day", "symbol", "ret")
        .pivot(values="ret", index="day", on="symbol")
        .sort("day")
    )
    pivot_days = ret_pivot["day"].to_list()
    day_index = {d: i for i, d in enumerate(pivot_days)}
    ret_cols = {s: ret_pivot[s].to_list() for s in ret_pivot.columns if s != "day"}

    def pair_corr(sym_a: str, sym_b: str, end_idx: int) -> float | None:
        if end_idx < 90:
            return None
        xs, ys = [], []
        for i in range(end_idx - 89, end_idx + 1):
            x, y = ret_cols[sym_a][i], ret_cols[sym_b][i]
            if x is not None and y is not None:
                xs.append(x)
                ys.append(y)
        if len(xs) < 60:
            return None
        try:
            return statistics.correlation(xs, ys)
        except statistics.StatisticsError:
            return None

    for day, grp in wide.drop_nulls(["r90", "fwd7"]).group_by("day", maintain_order=True):
        if grp.height < MIN_COINS:
            continue
        g = grp.sort("r90")
        top2 = g.tail(2)
        g30 = grp.drop_nulls("r30")
        breadth = (grp["r90"] > 0).sum() / grp.height
        dispersion = g30["r30"].std() if g30.height >= MIN_COINS else None
        spread = None
        if g30.height >= MIN_COINS:
            gs = g30.sort("r30")
            spread_top = gs.tail(2)["fwd7"].mean()
            spread_bot = gs.head(2)["fwd7"].mean()
            if spread_top is not None and spread_bot is not None:
                spread = spread_top - spread_bot
        syms = top2["symbol"].to_list()
        idx = day_index.get(day[0] if isinstance(day, tuple) else day)
        corr = pair_corr(syms[0], syms[1], idx) if idx is not None else None
        daily_rows.append(
            {
                "day": day[0] if isinstance(day, tuple) else day,
                "top2_fwd7": top2["fwd7"].mean(),
                "breadth": breadth,
                "dispersion": dispersion,
                "spread": spread,
                "pick_corr": corr,
            }
        )
    daily = pl.DataFrame(daily_rows)

    print("=== H37 breadth dial (top2 fwd7 by breadth tercile) ===")
    d37 = daily.drop_nulls(["breadth", "top2_fwd7"])
    q1, q2 = d37["breadth"].quantile(1 / 3), d37["breadth"].quantile(2 / 3)
    for name, cond in [
        ("low", pl.col("breadth") <= q1),
        ("mid", (pl.col("breadth") > q1) & (pl.col("breadth") <= q2)),
        ("high", pl.col("breadth") > q2),
    ]:
        sub = d37.filter(cond)
        print(f"  tercile {name:<4} E[top2 fwd7] = {sub['top2_fwd7'].mean():+.3%} (n={sub.height})")
    p = d37.with_columns(
        a=pl.when(pl.col("breadth") > q2).then(pl.col("top2_fwd7")),
        b=pl.when(pl.col("breadth") <= q1).then(pl.col("top2_fwd7")),
    )
    report("top breadth tercile vs bottom, top2 fwd7", p, 3710)

    print("=== H38 dispersion dial (spread by dispersion tercile) ===")
    d38 = daily.drop_nulls(["dispersion", "spread"])
    q1, q2 = d38["dispersion"].quantile(1 / 3), d38["dispersion"].quantile(2 / 3)
    for name, cond in [
        ("low", pl.col("dispersion") <= q1),
        ("mid", (pl.col("dispersion") > q1) & (pl.col("dispersion") <= q2)),
        ("high", pl.col("dispersion") > q2),
    ]:
        sub = d38.filter(cond)
        print(f"  tercile {name:<4} E[spread] = {sub['spread'].mean():+.3%} (n={sub.height})")
    p = d38.with_columns(
        a=pl.when(pl.col("dispersion") > q2).then(pl.col("spread")),
        b=pl.when(pl.col("dispersion") <= q1).then(pl.col("spread")),
    )
    report("high dispersion tercile vs low, r30 spread", p, 3810)

    print("=== H39 pick-correlation diversification ===")
    d39 = daily.drop_nulls(["pick_corr", "top2_fwd7"])
    med = d39["pick_corr"].median()
    print(f"  median top-2 pick correlation: {med:.2f}")
    p = d39.with_columns(
        a=pl.when(pl.col("pick_corr") <= med).then(pl.col("top2_fwd7")),
        b=pl.when(pl.col("pick_corr") > med).then(pl.col("top2_fwd7")),
    )
    report("low-corr picks vs high-corr picks, top2 fwd7", p, 3910)

    print("=== H40 trailing stop (2xATR14 from 30d high | r90>0) ===")
    p40 = wide.drop_nulls(["r90", "atr14", "hi30", "fwd30"]).filter(pl.col("r90") > 0)
    fired = (pl.col("hi30") - pl.col("close")) >= 2.0 * pl.col("atr14")
    p = p40.with_columns(
        a=pl.when(fired).then(pl.col("fwd30")),
        b=pl.when(~fired).then(pl.col("fwd30")),
    )
    report("stop-fired vs not | uptrend, fwd30 (stops help: CI<0)", p, 4010)


if __name__ == "__main__":
    main()
