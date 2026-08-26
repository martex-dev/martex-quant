"""Retail intraday kill-test batch: hypotheses 44-50 (maker-fee regime).

    .venv/Scripts/python scripts/h44_50_killtests.py

Pre-registered in docs/hypotheses/44-50-retail-intraday-batch.md.
Data: data/intraday/<sym>_15m.parquet (Bybit USDT perps, 2021+).
Info tests are GROSS; the maker round trip (~0.04%) is the toll every
per-trade effect must plausibly clear.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from martex_quant.features.intraday import load_15m_bars
from martex_quant.features.panel import forward_return, trailing_percentile_rank
from martex_quant.stats.bootstrap import event_mean_ci as _event_mean_ci
from martex_quant.stats.bootstrap import two_group_diff_ci
from martex_quant.stats.significance import ci_excludes_zero

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LTCUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "TRXUSDT",
    "PEPEUSDT",
]
FUNDING_SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
DATA = Path("data/intraday")
BLOCK_DAYS = 30
N_BOOT = 5_000
MIN_BARS_DAY = 90
MAKER_RT = 0.0004

# 8 bars of 15m = 2 hours. Named by bar count here; h52/h53 name the same
# horizon by duration instead (fwd2h / fwd1h).
FWD8 = forward_return(8, name="fwd8")


# --- bootstrap machinery (day blocks; H15-21 lineage) ------------------------------


def event_mean_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float, int]:
    """Count-weighted mean of event values pooled by day.

    Intraday events cluster heavily within a day, which is exactly why this
    is count-weighted rather than an unweighted daily mean.
    """
    by_day = panel.group_by("day").agg(v_sum=pl.col("v").sum(), v_n=pl.col("v").count()).sort("day")
    ci = _event_mean_ci(
        by_day["v_sum"].to_list(),
        by_day["v_n"].to_list(),
        block=BLOCK_DAYS,
        seed=seed,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="clamp",
    )
    return ci.point, ci.low, ci.high, ci.n


def diff_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float, int]:
    """Mean(a)-mean(b), day-block bootstrap; a/b value-or-null columns."""
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
        short_series="clamp",
    )
    return ci.point, ci.low, ci.high, ci.n


def show(name: str, point: float, lo: float, hi: float, n: int, claim: str) -> None:
    sig = ci_excludes_zero(lo, hi)
    print(
        f"  {name:<52} n={n:>6}  {point:+.4%}  CI [{lo:+.4%}, {hi:+.4%}]  "
        f"{'SIGNAL' if sig else 'noise'}  ({claim})"
    )


# --- per-day event extraction -------------------------------------------------------


def day_events(symbol: str, df: pl.DataFrame) -> dict[str, list[tuple[date, float]]]:
    """H44 ORB, H45 first-hour, H46 US-open, H48 prev-day levels."""
    out: dict[str, list[tuple[date, float]]] = {"h44": [], "h45": [], "h46": [], "h48": []}
    prev_high: float | None = None
    prev_low: float | None = None
    for (day,), grp in df.group_by("day", maintain_order=True):
        assert isinstance(day, date)
        if grp.height < MIN_BARS_DAY:
            prev_high, prev_low = None, None
            continue
        highs = grp["high"].to_list()
        lows = grp["low"].to_list()
        closes = grp["close"].to_list()
        opens = grp["open"].to_list()
        hhs = grp["hh"].to_list()
        mms = grp["mm"].to_list()
        day_close = closes[-1]
        by_time = {(hhs[i], mms[i]): i for i in range(grp.height)}

        # H44 ORB: first-hour range, breakout close in hours 1-5.
        h0 = [i for i in range(grp.height) if hhs[i] == 0]
        if len(h0) == 4:
            rh = max(highs[i] for i in h0)
            rl = min(lows[i] for i in h0)
            for i in range(grp.height):
                if not 1 <= hhs[i] <= 5:
                    continue
                if closes[i] > rh:
                    out["h44"].append((day, day_close / closes[i] - 1.0))
                    break
                if closes[i] < rl:
                    out["h44"].append((day, -(day_close / closes[i] - 1.0)))
                    break

        # H45 first-hour momentum.
        if len(h0) == 4:
            r0 = closes[h0[-1]] / opens[h0[0]] - 1.0
            rem = day_close / closes[h0[-1]] - 1.0
            if r0 != 0:
                out["h45"].append((day, (1.0 if r0 > 0 else -1.0) * rem))

        # H46 US-open session momentum (13:30-16:00 -> 16:00-24:00).
        i_ref, i_end = by_time.get((13, 15)), by_time.get((15, 45))
        if i_ref is not None and i_end is not None:
            sess = closes[i_end] / closes[i_ref] - 1.0
            outcome = day_close / closes[i_end] - 1.0
            if sess != 0:
                out["h46"].append((day, (1.0 if sess > 0 else -1.0) * outcome))

        # H48 previous-day high/low break before 12:00.
        if prev_high is not None and prev_low is not None:
            for i in range(grp.height):
                if hhs[i] >= 12:
                    break
                if closes[i] > prev_high:
                    out["h48"].append((day, day_close / closes[i] - 1.0))
                    break
                if closes[i] < prev_low:
                    out["h48"].append((day, -(day_close / closes[i] - 1.0)))
                    break

        prev_high, prev_low = max(highs), min(lows)
    return out


def main() -> None:
    print(f"maker toll context: ~{MAKER_RT:.2%} per round trip\n")
    pooled: dict[str, list[tuple[date, float]]] = {"h44": [], "h45": [], "h46": [], "h48": []}
    h49_parts, h50_parts = [], []
    for symbol in SYMBOLS:
        df = load_15m_bars(DATA, symbol)
        ev = day_events(symbol, df)
        for k in pooled:
            pooled[k].extend(ev[k])

        # H49 vol-burst continuation (vectorized).
        d = df.with_columns(ret=pl.col("close") / pl.col("close").shift(1) - 1.0)
        d = d.with_columns(sigma=pl.col("ret").rolling_std(96).shift(1))
        d = d.with_columns(**{FWD8.name: FWD8.expr}).drop_nulls(["ret", "sigma", "fwd8"])
        bursts = d.filter(pl.col("ret").abs() > 4.0 * pl.col("sigma"))
        h49_parts.append(
            bursts.select(
                "day",
                v=pl.when(pl.col("ret") > 0).then(pl.col("fwd8")).otherwise(-pl.col("fwd8")),
            )
        )

        # H50 VWAP stretch (vectorized; reversion-signed).
        d2 = df.with_columns(
            tp=(pl.col("high") + pl.col("low") + pl.col("close")) / 3.0,
        ).with_columns(
            cpv=(pl.col("tp") * pl.col("volume")).cum_sum().over("day"),
            cv=pl.col("volume").cum_sum().over("day"),
        )
        d2 = d2.with_columns(stretch=pl.col("close") / (pl.col("cpv") / pl.col("cv")) - 1.0)
        d2 = d2.with_columns(
            sstd=pl.col("stretch").rolling_std(96).shift(1),
            **{FWD8.name: FWD8.expr},
        ).drop_nulls(["stretch", "sstd", "fwd8"])
        events = d2.filter(pl.col("stretch").abs() > 2.0 * pl.col("sstd"))
        h50_parts.append(
            events.select(
                "day",
                v=pl.when(pl.col("stretch") > 0).then(-pl.col("fwd8")).otherwise(pl.col("fwd8")),
            )
        )

    print("=== H44 opening-range breakout (signed to day close) ===")
    p = pl.DataFrame({"day": [d for d, _ in pooled["h44"]], "v": [v for _, v in pooled["h44"]]})
    show("ORB break in h1-5 -> day close", *event_mean_ci(p, 4410), "PASS if CI>0")

    print("=== H45 first-hour momentum ===")
    p = pl.DataFrame({"day": [d for d, _ in pooled["h45"]], "v": [v for _, v in pooled["h45"]]})
    show("sign(00-01h) x rest-of-day", *event_mean_ci(p, 4510), "PASS if CI>0")

    print("=== H46 US-open session momentum ===")
    p = pl.DataFrame({"day": [d for d, _ in pooled["h46"]], "v": [v for _, v in pooled["h46"]]})
    show("sign(13:30-16:00) x 16:00-24:00", *event_mean_ci(p, 4610), "PASS if CI>0")

    print("=== H47 funding-window drift (7 majors, two-sided) ===")
    parts = []
    for symbol in FUNDING_SYMS:
        f = pl.read_parquet(Path("data/funding") / f"{symbol}.parquet").sort("timestamp")
        ranks = trailing_percentile_rank(f["rate"].to_list(), window=270, skip_nulls=False)
        f = f.with_columns(pl.Series("pct", ranks, dtype=pl.Float64)).drop_nulls("pct")
        px = load_15m_bars(DATA, symbol).select("ts", "close", "day")
        f = (
            f.join(px, left_on="timestamp", right_on="ts", how="inner")
            .join(
                px.with_columns(pl.col("ts") - pl.duration(minutes=30)).rename(
                    {"close": "close30"}
                ),
                left_on="timestamp",
                right_on="ts",
                how="inner",
            )
            .with_columns(fwd30m=pl.col("close30") / pl.col("close") - 1.0)
        )
        parts.append(f.select("day", "pct", "fwd30m"))
    p47 = pl.concat(parts).with_columns(
        a=pl.when(pl.col("pct") >= 0.9).then(pl.col("fwd30m")),
        b=pl.when(pl.col("pct") < 0.9).then(pl.col("fwd30m")),
    )
    show("30m after stamp: funding>=90th pct vs rest", *diff_ci(p47, 4710), "two-sided")

    print("=== H48 previous-day high/low break before 12:00 ===")
    p = pl.DataFrame({"day": [d for d, _ in pooled["h48"]], "v": [v for _, v in pooled["h48"]]})
    show("signed break -> day close", *event_mean_ci(p, 4810), "PASS if CI>0")

    print("=== H49 vol-burst continuation (two-sided) ===")
    p = pl.concat(h49_parts)
    show("|ret|>4 sigma -> next 2h signed", *event_mean_ci(p, 4910), "cont>0 / reversion<0")

    print("=== H50 VWAP stretch (reversion-signed, two-sided) ===")
    p = pl.concat(h50_parts)
    show("|stretch|>2 sigma -> next 2h reversion", *event_mean_ci(p, 5010), "reversion>0 / cont<0")


if __name__ == "__main__":
    main()
