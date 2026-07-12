"""H52 true maker-fill fade + H55/H56/H57 kill tests (existing 15m data).

    .venv/Scripts/python scripts/h52_55_57_studies.py

Pre-registered in docs/hypotheses/52-57-intraday-frontier.md.
"""

from __future__ import annotations

import math
import random
from datetime import date
from pathlib import Path

import polars as pl

from trading_bot.backtesting.metrics import compute_metrics
from trading_bot.data.models import Interval

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
DATA = Path("data/intraday")
CACHE_DIR = Path("data/tmp/h4x_streams")
BLOCK_DAYS = 30
N_BOOT = 5_000
MAKER_FEE = 0.0002
TAKER_EXIT = 0.00065  # fee 5.5bp + half-spread 0.5 + impact 0.5
VOL_TARGET = 0.30


def _prefix(xs: list[float]) -> list[float]:
    out = [0.0]
    for x in xs:
        out.append(out[-1] + float(x))
    return out


def event_mean_ci(panel: pl.DataFrame, seed: int) -> tuple[float, float, float, int]:
    by_day = panel.group_by("day").agg(v_sum=pl.col("v").sum(), v_n=pl.col("v").count()).sort("day")
    ps, pn = _prefix(by_day["v_sum"].to_list()), _prefix(by_day["v_n"].to_list())
    n = by_day.height
    point = ps[n] / max(pn[n], 1.0)
    rng = random.Random(seed)
    n_blocks = n // BLOCK_DAYS + 1
    means = []
    for _ in range(N_BOOT):
        total = cnt = 0.0
        for _ in range(n_blocks):
            s = rng.randint(0, max(n - BLOCK_DAYS, 0))
            e = s + BLOCK_DAYS
            total += ps[e] - ps[s]
            cnt += pn[e] - pn[s]
        if cnt > 0:
            means.append(total / cnt)
    means.sort()
    return point, means[int(0.025 * len(means))], means[int(0.975 * len(means))], int(pn[n])


def show(name: str, point: float, lo: float, hi: float, n: int, claim: str) -> None:
    sig = lo > 0 or hi < 0
    print(
        f"  {name:<52} n={n:>6}  {point:+.4%}  CI [{lo:+.4%}, {hi:+.4%}]  "
        f"{'SIGNAL' if sig else 'noise'}  ({claim})"
    )


def load(symbol: str) -> pl.DataFrame:
    return (
        pl.read_parquet(DATA / f"{symbol}_15m.parquet")
        .sort("ts")
        .with_columns(
            day=pl.col("ts").dt.date(),
            hh=pl.col("ts").dt.hour(),
            mm=pl.col("ts").dt.minute(),
        )
    )


# --- H52: true maker-fill first-hour fade ------------------------------------------


def h52(rot_daily: pl.DataFrame) -> None:
    print("=== H52 first-hour fade, TRUE maker fill (one-bar window) ===")
    daily: dict[date, list[float]] = {}
    signals = fills = 0
    for symbol in SYMBOLS:
        df = load(symbol)
        for (day,), grp in df.group_by("day", maintain_order=True):
            assert isinstance(day, date)
            if grp.height < 90:
                continue
            hhs = grp["hh"].to_list()
            h0 = [i for i in range(grp.height) if hhs[i] == 0]
            h1 = [i for i in range(grp.height) if hhs[i] == 1]
            if len(h0) != 4 or not h1:
                continue
            opens = grp["open"].to_list()
            closes = grp["close"].to_list()
            highs = grp["high"].to_list()
            lows = grp["low"].to_list()
            r0 = closes[h0[-1]] / opens[h0[0]] - 1.0
            if r0 == 0:
                continue
            signals += 1
            direction = -1.0 if r0 > 0 else 1.0  # fade
            limit = closes[h0[-1]]
            nb = h1[0]
            filled = lows[nb] <= limit if direction > 0 else highs[nb] >= limit
            day_rets = daily.setdefault(day, [])
            if not filled:
                day_rets.append(0.0)
                continue
            fills += 1
            gross = direction * (closes[-1] / limit - 1.0)
            day_rets.append(gross - MAKER_FEE - TAKER_EXIT)
    rows = sorted((d, sum(v) / len(v)) for d, v in daily.items())
    ew = pl.DataFrame({"day": [r[0] for r in rows], "ret": [r[1] for r in rows]})
    ew = ew.with_columns(
        scale=(VOL_TARGET / (pl.col("ret").rolling_std(30).shift(1) * math.sqrt(365))).clip(
            0.0, 1.0
        )
    ).drop_nulls("scale")
    ew = ew.with_columns(sret=pl.col("ret") * pl.col("scale"))
    curve = pl.DataFrame(
        {
            "timestamp": ew["day"],
            "equity": (1.0 + ew["sret"]).cum_prod() * 10_000.0,
            "exposure": pl.Series([1.0] * ew.height),
        }
    )
    m = compute_metrics(curve, [], Interval.D1)
    joined = ew.join(rot_daily, on="day", how="inner")
    corr = joined.select(pl.corr("sret", "rot_ret")).item()
    assert isinstance(corr, float)
    fill_rate = fills / max(signals, 1)
    bar = m.sharpe > 0.7 and abs(corr) < 0.30
    fragile = fill_rate < 0.30
    print(
        f"  {ew.height}d  Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
        f"MDD {m.max_drawdown_pct:.1f}%  corr(rot-stop) {corr:+.3f}  fill rate {fill_rate:.0%}"
    )
    print(
        f"  H52 VERDICT: {'CANDIDATE (diversifier)' if bar else 'KILLED'}"
        f"{' [FRAGILE: fill<30%]' if fragile else ''}\n"
    )


# --- H55/H56/H57 kill tests ---------------------------------------------------------


def main() -> None:
    rot_stop = pl.read_parquet(CACHE_DIR / "rot_stop_stream.parquet")
    rot_daily = rot_stop.with_columns(day=pl.col("timestamp").dt.date()).select(
        "day", pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret")
    )
    h52(rot_daily)

    frames = {s: load(s) for s in SYMBOLS}

    print("=== H55 BTC -> alt intraday lead-lag (|z|>2) ===")
    btc = frames["BTCUSDT"].with_columns(ret=pl.col("close") / pl.col("close").shift(1) - 1.0)
    btc = btc.with_columns(sigma=pl.col("ret").rolling_std(96).shift(1)).select(
        "ts", "day", pl.col("ret").alias("btc_ret"), "sigma"
    )
    events = btc.filter(pl.col("btc_ret").abs() > 2.0 * pl.col("sigma")).select(
        "ts", "day", "btc_ret"
    )
    parts_15, parts_1h = [], []
    for symbol in SYMBOLS:
        if symbol == "BTCUSDT":
            continue
        alt = frames[symbol].with_columns(
            fwd15=pl.col("close").shift(-1) / pl.col("close") - 1.0,
            fwd1h=pl.col("close").shift(-4) / pl.col("close") - 1.0,
        )
        joined = events.join(alt.select("ts", "fwd15", "fwd1h"), on="ts", how="inner")
        signed = joined.with_columns(
            v15=pl.when(pl.col("btc_ret") > 0).then(pl.col("fwd15")).otherwise(-pl.col("fwd15")),
            v1h=pl.when(pl.col("btc_ret") > 0).then(pl.col("fwd1h")).otherwise(-pl.col("fwd1h")),
        ).drop_nulls(["v15", "v1h"])
        parts_15.append(signed.select("day", v=pl.col("v15")))
        parts_1h.append(signed.select("day", v=pl.col("v1h")))
    show("alt next-15m signed follow", *event_mean_ci(pl.concat(parts_15), 5510), "two-sided")
    show("alt next-1h signed follow", *event_mean_ci(pl.concat(parts_1h), 5511), "two-sided")

    print("=== H56 intraday ETH/BTC ratio reversion (|z|>2) ===")
    pair = (
        frames["ETHUSDT"]
        .select("ts", "day", pl.col("close").alias("eth"))
        .join(frames["BTCUSDT"].select("ts", pl.col("close").alias("btc")), on="ts", how="inner")
        .sort("ts")
        .with_columns(lr=(pl.col("eth") / pl.col("btc")).log())
    )
    pair = pair.with_columns(
        z=(pl.col("lr") - pl.col("lr").rolling_mean(96).shift(1))
        / pl.col("lr").rolling_std(96).shift(1),
        fwd2h=(pl.col("eth").shift(-8) / pl.col("eth")) / (pl.col("btc").shift(-8) / pl.col("btc"))
        - 1.0,
    ).drop_nulls(["z", "fwd2h"])
    ev = pair.filter(pl.col("z").abs() > 2.0).with_columns(
        v=pl.when(pl.col("z") > 0).then(-pl.col("fwd2h")).otherwise(pl.col("fwd2h"))
    )
    show("ratio 2h reversion (signed)", *event_mean_ci(ev.select("day", "v"), 5610), "two-sided")

    print("=== H57 prior-day POC first touch ===")
    poc_events = []
    for symbol in SYMBOLS:
        df = frames[symbol]
        prev_poc: float | None = None
        for (day,), grp in df.group_by("day", maintain_order=True):
            assert isinstance(day, date)
            closes = grp["close"].to_list()
            highs = grp["high"].to_list()
            lows = grp["low"].to_list()
            vols = grp["volume"].to_list()
            opens = grp["open"].to_list()
            if grp.height >= 90 and prev_poc is not None:
                approach = 1.0 if prev_poc > opens[0] else -1.0
                if abs(prev_poc / opens[0] - 1.0) > 0.002:
                    for i in range(grp.height - 4):
                        if lows[i] <= prev_poc <= highs[i]:
                            fwd = closes[i + 4] / closes[i] - 1.0
                            poc_events.append((day, -approach * fwd))
                            break
            # compute today's POC for tomorrow
            if grp.height >= 90:
                lo, hi = min(lows), max(highs)
                if hi > lo:
                    buckets = [0.0] * 20
                    for c, v in zip(closes, vols, strict=True):
                        b = min(int((c - lo) / (hi - lo) * 20), 19)
                        buckets[b] += v
                    best = max(range(20), key=lambda b: buckets[b])
                    prev_poc = lo + (best + 0.5) * (hi - lo) / 20
                else:
                    prev_poc = None
            else:
                prev_poc = None
    p57 = pl.DataFrame({"day": [d for d, _ in poc_events], "v": [v for _, v in poc_events]})
    show("1h after first POC touch (bounce>0/magnet<0)", *event_mean_ci(p57, 5710), "two-sided")


if __name__ == "__main__":
    main()
