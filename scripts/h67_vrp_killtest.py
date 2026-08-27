"""H67: variance risk premium kill test, against its seven pre-registered bars.

    .venv/Scripts/python scripts/h67_vrp_killtest.py

Pre-registered in docs/hypotheses/67-variance-risk-premium.md, committed
2026-08-27 BEFORE this script was written (commit afa6c3e). The proxy
instrument, the 3.0 vol-point haircut and all seven bars are fixed by
that document and are read from it, not chosen here.

Trials 148-152 (five declared cells).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    Metrics,
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import CI, daily_mean_ci

ROOT = Path(".")
N_TRIALS = 152
SEED = 20260827
N_BOOT = 2_000

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/67-variance-risk-premium.md §4-§5).
# Do not edit any constant below to chase a result.
TENOR = 30
BLOCK = 60  # §5.1: double the tenor
VEGA = 2.0 * (1.0 / math.sqrt(2.0 * math.pi)) * math.sqrt(TENOR / 365.0)  # 0.228734
HAIRCUT_BASE = 0.03  # §4.3: 3.0 vol points, derived
HAIRCUT_STRESS = 0.06  # §4.4 cell 5: 2x
SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

BAR_MIN_CAGR = 2.0
BAR_MIN_SHARPE = 1.0
BAR_MAX_CORR = 0.30
BAR_DSR = 0.95
TAIL_CONDITION_MDD = -40.0
# --------------------------------------------------------------------------


def load_inputs() -> dict[str, pl.DataFrame]:
    """DVOL close (implied) joined to frozen-lake spot log returns (realized)."""
    store = ParquetStore(ROOT / "data/lake")
    frames: dict[str, pl.DataFrame] = {}
    for currency, symbol in SYMBOLS.items():
        dvol = (
            pl.read_parquet(ROOT / f"data/dvol/{currency}.parquet")
            .select(
                pl.col("timestamp")
                .dt.truncate("1d")
                .cast(pl.Datetime("us", "UTC"))
                .alias("timestamp"),
                (pl.col("close") / 100.0).alias("k"),
            )
            .sort("timestamp")
        )
        spot = (
            store.read(symbol, Interval.D1)
            .sort("timestamp")
            .select(
                pl.col("timestamp")
                .dt.truncate("1d")
                .cast(pl.Datetime("us", "UTC"))
                .alias("timestamp"),
                (pl.col("close").log() - pl.col("close").log().shift(1)).alias("r"),
            )
            .drop_nulls()
        )
        frames[currency] = dvol.join(spot, on="timestamp", how="inner").sort("timestamp")
    return frames


def tranche_stream(frame: pl.DataFrame, haircut: float, *, overlap: bool) -> pl.Series:
    """Daily return of the short-variance ladder, per §4.2.

    Overlapping book (30 live tranches, 1/30 notional each):

        ret_u = (V/900) * SUM_{t in [u-30, u-1]} (K_t^2 - 365 r_u^2)/(2 K_t)
                - V*h/30

    Non-overlapping book (one live tranche at a time, full notional,
    opened every 30 days): the same daily accrual with a single strike.
    The haircut is amortized over the tranche's life in both cases, which
    is identical in total and smoother per day.

    Every strike used on day u is dated strictly before day u.
    """
    k = frame["k"].to_list()
    r = frame["r"].to_list()
    n = len(k)
    carry_cost = VEGA * haircut / TENOR
    out: list[float] = []

    if overlap:
        # inv_k[t] = 1/(2*K_t); k_half[t] = K_t/2 == K_t^2/(2*K_t)
        for u in range(n):
            lo = u - TENOR
            if lo < 0:
                out.append(0.0)
                continue
            rr = 365.0 * r[u] * r[u]
            acc = 0.0
            for t in range(lo, u):
                acc += (k[t] * k[t] - rr) / (2.0 * k[t])
            out.append(VEGA * acc / (TENOR * TENOR) - carry_cost)
    else:
        for u in range(n):
            opened = ((u - 1) // TENOR) * TENOR  # strike of the live tranche
            if opened < 0 or u == 0:
                out.append(0.0)
                continue
            strike = k[opened]
            rr = 365.0 * r[u] * r[u]
            acc = (strike * strike - rr) / (2.0 * strike)
            out.append(VEGA * acc / TENOR - carry_cost)

    return pl.Series("ret", out)


def build_cell(
    frames: dict[str, pl.DataFrame],
    currencies: tuple[str, ...],
    haircut: float,
    *,
    overlap: bool,
) -> pl.DataFrame:
    """Equal-weight book over `currencies`, aligned on the common window."""
    parts: list[pl.DataFrame] = []
    for currency in currencies:
        frame = frames[currency]
        parts.append(
            frame.select("timestamp").with_columns(
                tranche_stream(frame, haircut, overlap=overlap).alias(currency)
            )
        )
    book = parts[0]
    for part in parts[1:]:
        book = book.join(part, on="timestamp", how="inner")
    weight = 1.0 / len(currencies)
    book = book.with_columns(ret=sum(pl.col(c) * weight for c in currencies)).slice(
        TENOR
    )  # drop the warm-up days that carry no live tranche
    return book.select("timestamp", "ret")


@dataclass(frozen=True)
class Cell:
    """One declared cell of the study (docs/hypotheses/67 Section 4.4)."""

    metrics: Metrics
    dsr: float
    ci: CI
    skew: float
    kurt: float
    book: pl.DataFrame


def summarize(book: pl.DataFrame) -> tuple[Metrics, float, float, float]:
    equity = book.select(
        pl.col("timestamp"),
        (1.0 + pl.col("ret")).cum_prod().alias("equity"),
        pl.lit(1.0).alias("exposure"),
    )
    metrics = compute_metrics(equity, [], Interval.D1)
    rets = book["ret"]
    pp = (rets.mean() or 0.0) / (rets.std() or 1.0)
    skew = rets.skew()
    kurt = rets.kurtosis()
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=rets.len(),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, float(rets.var() or 0.0)),
    )
    return metrics, dsr, float(skew or 0.0), float(kurt or 0.0)


def join_rotation_stop(book: pl.DataFrame) -> pl.DataFrame:
    """Timestamp-joined, per meta-finding 5 (never join on position)."""
    series = SeriesStore(ROOT)
    rot = (
        series.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
        .sort("timestamp")
        .select(
            pl.col("timestamp").dt.truncate("1d").cast(pl.Datetime("us", "UTC")).alias("timestamp"),
            pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret"),
        )
        .group_by("timestamp")
        .agg(pl.col("rot_ret").last())
    )
    return (
        book.select("timestamp", pl.col("ret").alias("vrp_ret"))
        .join(rot, on="timestamp", how="inner")
        .drop_nulls()
    )


def correlation_with_rotation_stop(joined: pl.DataFrame) -> tuple[float, int]:
    if joined.height < 30:
        return float("nan"), joined.height
    return float(joined.select(pl.corr("vrp_ret", "rot_ret")).item()), joined.height


def tail_conditional_table(joined: pl.DataFrame) -> None:
    """What the linear correlation bar cannot see.

    Reported under Section 5's "reported, not gated" list. This is a
    diagnostic on the PRIMARY cell, not a new cell and not a new trial:
    it re-describes the same return stream conditioned on the incumbent
    book's own bad days.

    The VRP stream is driven by SQUARED returns, so it is direction-blind
    and its Pearson correlation with a directional book is near zero by
    construction. That is not independence.
    """
    print("\n--- tail dependence on rotation-stop (diagnostic, not a bar) ---")
    unconditional = joined["vrp_ret"].mean() or 0.0
    print(f"    {'rotation-stop bucket':<26} {'n':>5} {'mean VRP return':>18}")
    print(f"    {'all days':<26} {joined.height:>5} {unconditional * 100:+17.3f}%")
    for quantile, label in ((0.10, "worst decile"), (0.05, "worst 5%"), (0.01, "worst 1%")):
        threshold = joined["rot_ret"].quantile(quantile)
        subset = joined.filter(pl.col("rot_ret") <= threshold)
        print(
            f"    {label:<26} {subset.height:>5} {(subset['vrp_ret'].mean() or 0.0) * 100:+17.3f}%"
        )
    both = joined.filter((pl.col("rot_ret") < 0) & (pl.col("vrp_ret") < 0)).height
    independent = (joined["rot_ret"] < 0).mean() * (joined["vrp_ret"] < 0).mean()
    print(
        f"    both books lose: {100 * both / joined.height:.1f}% of days "
        f"vs {independent * 100:.1f}% under independence "
        "-> the dependence is in MAGNITUDE, not frequency"
    )


def gross_premium_table(frames: dict[str, pl.DataFrame]) -> None:
    """Descriptive: mean implied vs mean subsequent realized, in vol points.

    Part of cells 1-2, not a separate trial: it is the same measurement
    the P&L stream is built from, shown in the units the §4.3 haircut is
    quoted in so the two can be compared directly.

    The last two columns are the convexity gap §5 requires be reported.
    A variance position does not earn the naive `K - RV`; it earns
    `(K^2 - RV^2)/(2K)`. Realized VARIANCE is right-skewed, so its mean
    sits far above the square of mean realized VOL, and the second column
    is materially smaller than the first. A screen built on `IV - RV`
    overstates what is actually harvestable.
    """
    print("\n--- gross premium: implied vs subsequent realized (vol points) ---")
    print(
        f"    {'':6} {'mean IV':>9} {'mean RV':>9} {'K-RV':>8} {'days IV>RV':>12} "
        f"{'(K^2-RV^2)/2K':>15} {'convexity tax':>15}"
    )
    for currency, frame in frames.items():
        k = frame["k"]
        rv2 = (frame["r"].pow(2) * 365.0).rolling_mean(TENOR).shift(-TENOR)
        both = pl.DataFrame({"k": k, "rv2": rv2}).drop_nulls()
        simple = both["k"] - both["rv2"].sqrt()
        variance_form = (both["k"] ** 2 - both["rv2"]) / (2.0 * both["k"])
        print(
            f"    {currency:6} {both['k'].mean() * 100:9.2f} "
            f"{both['rv2'].sqrt().mean() * 100:9.2f} {simple.mean() * 100:8.2f} "
            f"{(simple > 0).mean() * 100:11.1f}% "
            f"{variance_form.mean() * 100:15.2f} "
            f"{(variance_form.mean() - simple.mean()) * 100:15.2f}"
        )
    print(f"    (the §4.3 cost haircut is {HAIRCUT_BASE * 100:.1f} vol points)")


def report_cell(name: str, book: pl.DataFrame, *, primary: bool) -> Cell:
    metrics, dsr, skew, kurt = summarize(book)
    rets = book["ret"]
    ci = daily_mean_ci(
        rets.to_list(),
        block=BLOCK,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    marker = " <== PRIMARY" if primary else ""
    print(
        f"  {name:<34} n={rets.len():>4}  "
        f"mean={ci.point * 1e4:+7.3f}bp  CI[{ci.low * 1e4:+7.3f},{ci.high * 1e4:+7.3f}]  "
        f"CAGR={metrics.cagr_pct:+8.2f}%  Sharpe={metrics.sharpe:6.2f}  "
        f"MDD={metrics.max_drawdown_pct:7.2f}%  DSR={dsr:.4f}{marker}"
    )
    return Cell(metrics=metrics, dsr=dsr, ci=ci, skew=skew, kurt=kurt, book=book)


def main() -> None:
    frames = load_inputs()

    print("=" * 100)
    print("H67 - VARIANCE RISK PREMIUM KILL TEST (family F3, trials 148-152)")
    print("=" * 100)
    for currency, frame in frames.items():
        print(
            f"  {currency}: n={frame.height}  "
            f"{str(frame['timestamp'].min())[:10]} -> {str(frame['timestamp'].max())[:10]}  "
            f"mean DVOL {frame['k'].mean() * 100:.1f}"
        )
    print(f"\n  Proxy: rolling {TENOR}d short-variance ladder, 1x notional, delta-hedged (§4.2)")
    print(
        f"  Straddle vega V = {VEGA:.6f} / unit notional / 1.00 vol; "
        f"haircut {HAIRCUT_BASE * 100:.1f} vol pts "
        f"= {VEGA * HAIRCUT_BASE / TENOR * 1e4:.3f} bp/day "
        f"= {VEGA * HAIRCUT_BASE / TENOR * 365 * 100:.2f} %/yr"
    )

    gross_premium_table(frames)

    print("\n--- the five declared cells (§4.4) ---")
    cells: dict[str, Cell] = {}
    cells["btc"] = report_cell(
        "1. BTC only, h=3.0",
        build_cell(frames, ("BTC",), HAIRCUT_BASE, overlap=True),
        primary=False,
    )
    cells["eth"] = report_cell(
        "2. ETH only, h=3.0",
        build_cell(frames, ("ETH",), HAIRCUT_BASE, overlap=True),
        primary=False,
    )
    cells["combined"] = report_cell(
        "3. Combined 50/50, h=3.0",
        build_cell(frames, ("BTC", "ETH"), HAIRCUT_BASE, overlap=True),
        primary=True,
    )
    cells["nonoverlap"] = report_cell(
        "4. Combined, non-overlapping",
        build_cell(frames, ("BTC", "ETH"), HAIRCUT_BASE, overlap=False),
        primary=False,
    )
    cells["stress"] = report_cell(
        "5. Combined, h=6.0 (2x cost)",
        build_cell(frames, ("BTC", "ETH"), HAIRCUT_STRESS, overlap=True),
        primary=False,
    )

    primary = cells["combined"]
    book = primary.book
    metrics = primary.metrics
    ci = primary.ci
    joined = join_rotation_stop(book)
    corr, corr_n = correlation_with_rotation_stop(joined)

    print("\n--- the seven pre-registered bars (§5) ---")
    a1 = ci.low > 0.0
    a2 = metrics.cagr_pct >= BAR_MIN_CAGR
    a3 = metrics.sharpe >= BAR_MIN_SHARPE
    a4 = primary.dsr >= BAR_DSR
    b5 = cells["stress"].ci.low > 0.0
    b6 = (
        cells["nonoverlap"].metrics.cagr_pct > 0.0
        and cells["nonoverlap"].metrics.sharpe >= BAR_MIN_SHARPE
    )
    c7 = abs(corr) < BAR_MAX_CORR

    def line(label: str, measured: str, ok: bool) -> None:
        print(f"  {label:<46} {measured:<28} -> {'PASS' if ok else 'FAIL'}")

    line(
        "A1. mean daily net > 0, CI excludes zero",
        f"{ci.point * 1e4:+.3f}bp, low {ci.low * 1e4:+.3f}bp",
        a1,
    )
    line(f"A2. net CAGR >= {BAR_MIN_CAGR:.0f}%/yr", f"{metrics.cagr_pct:+.2f}%", a2)
    line(f"A3. Sharpe >= {BAR_MIN_SHARPE:.1f}", f"{metrics.sharpe:.2f}", a3)
    line(f"A4. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS}", f"{primary.dsr:.4f}", a4)
    line(
        "B5. 2x-cost cell mean > 0, CI excludes zero",
        f"{cells['stress'].ci.point * 1e4:+.3f}bp, low {cells['stress'].ci.low * 1e4:+.3f}bp",
        b5,
    )
    line(
        "B6. non-overlap CAGR > 0 and Sharpe >= 1.0",
        f"{cells['nonoverlap'].metrics.cagr_pct:+.2f}%, {cells['nonoverlap'].metrics.sharpe:.2f}",
        b6,
    )
    line(
        f"C7. |corr| rotation-stop < {BAR_MAX_CORR:.2f}",
        f"{corr:+.4f} (n={corr_n})",
        c7,
    )

    gate_a = a1 and a2 and a3 and a4
    print(
        f"\n  Gate A {'PASS' if gate_a else 'FAIL'}   "
        f"Gate B {'PASS' if b5 and b6 else 'FAIL'}   "
        f"Gate C {'PASS' if c7 else 'FAIL'}"
    )

    print("\n--- reported, not gated (§5) ---")
    rets = book["ret"]
    print(
        f"  skew {primary.skew:+.3f}   excess kurtosis {primary.kurt:+.2f}   "
        f"worst day {rets.min() * 100:+.2f}%   best day {rets.max() * 100:+.2f}%"
    )
    print(f"  MDD {metrics.max_drawdown_pct:.2f}%", end="")
    if metrics.max_drawdown_pct < TAIL_CONDITION_MDD:
        print("  -> BREACHES the -40% tail condition: any F3 build must")
        print("     design tail limits BEFORE the build (§5).")
    else:
        print(f"  (tail condition {TAIL_CONDITION_MDD:.0f}% not breached)")
    breaches = int((rets <= -1.0).sum())
    if breaches:
        print(
            f"  WARNING: {breaches} day(s) with modelled return <= -100%. "
            "The linearized proxy has broken; real loss is unbounded there."
        )

    tail_conditional_table(joined)

    for window in (30, 90):
        rolling = book.select(pl.col("ret").rolling_sum(window)).drop_nulls()["ret"]
        print(f"  worst {window}-day window: {rolling.min() * 100:+.2f}%")

    print("\n  10 worst days (the episodes this strategy is short):")
    for row in book.sort("ret").head(10).iter_rows(named=True):
        print(f"    {str(row['timestamp'])[:10]}  {row['ret'] * 100:+8.2f}%")

    print("\n  per-year:")
    by_year = book.with_columns(year=pl.col("timestamp").dt.year())
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        r = group["ret"]
        n = group.height
        ann = r.sum() / (n / 365.25) * 100.0
        sharpe = (r.mean() or 0.0) / (r.std() or 1.0) * math.sqrt(365.25)
        print(
            f"    {year[0]}  n={n:>4}  net={ann:+8.2f}%/yr  "
            f"Sharpe={sharpe:6.2f}  worst day {r.min() * 100:+7.2f}%"
        )

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
