"""H68: cross-venue price dislocation, against its pre-registered bars.

    .venv/Scripts/python scripts/h68_cross_venue_killtest.py

Pre-registered in docs/hypotheses/68-cross-venue-dislocation.md, committed
2026-08-27 BEFORE this script was written (commit 3eb0fbc). The venues,
the panel, the $1M volume floor, the four signals, the 90-day percentile
window, the 10/90 thresholds, the horizons, the primary horizon and the
breadth bar are all fixed by that document and are read from it, not
chosen here.

Trials 153-164 (four signals x three horizons).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from martex_quant.features.panel import forward_return, trailing_percentile_rank
from martex_quant.stats.bootstrap import two_group_diff_ci

ROOT = Path(".")
VENUE_DIR = ROOT / "data/venues"

# ---------------------------------------------------------------- FIXED BY
# THE PRE-REGISTRATION (docs/hypotheses/68-cross-venue-dislocation.md).
# Do not edit any constant below to chase a result.
PCT_WINDOW = 90
LOW_PCT, HIGH_PCT = 0.10, 0.90
HORIZONS = (1, 7, 30)
PRIMARY_H = 7
BLOCK_DAYS = 30
N_BOOT = 5_000
SEED = 20260827
VOLUME_FLOOR = 1_000_000.0
BREADTH_MIN = 12
SPREAD_FLOOR = 0.005  # Section 5.3 reachability rule
N_TRIALS = 164

# Section 5.2. None = no directional prior was declared, stated honestly.
SIGNALS: dict[str, tuple[str, int | None]] = {
    "s1_raw_premium": ("S1 raw premium  c - b", +1),
    "s2_adj_premium": ("S2 peg-adjusted  c - (b+g)", +1),
    "s3_dispersion": ("S3 dispersion  sd{c, b+g, o+g}", None),
    "s4_peg": ("S4 peg deviation  g", +1),
}
# --------------------------------------------------------------------------


def _venue(venue: str, symbol: str) -> pl.DataFrame | None:
    path = VENUE_DIR / f"{venue}_{symbol}.parquet"
    if not path.exists():
        return None
    return pl.read_parquet(path).sort("timestamp")


def _segments(frame: pl.DataFrame) -> list[pl.DataFrame]:
    """Split a symbol's series at any break in consecutive daily bars.

    Coinbase suspended XRP/USD for 904 days over the SEC suit. Without
    this split, `shift(-h)` would pair 2021-01-19 with a date in 2023 and
    report a two-and-a-half-year move as a 7-day forward return, and the
    trailing percentile window would rank against prices from before the
    delisting. Segments make both operations respect the hole.
    """
    gaps = frame.select(
        (pl.col("timestamp").diff().dt.total_days() > 1).fill_null(False).alias("brk")
    )["brk"].to_list()
    out: list[pl.DataFrame] = []
    start = 0
    for i, is_break in enumerate(gaps):
        if is_break:
            out.append(frame.slice(start, i - start))
            start = i
    out.append(frame.slice(start, frame.height - start))
    return [s for s in out if s.height > PCT_WINDOW + max(HORIZONS)]


def build_panel() -> tuple[pl.DataFrame, list[str], list[tuple[str, float]]]:
    """Join the three venues plus the peg, derive the four signals."""
    peg = (
        pl.read_parquet(VENUE_DIR / "peg_usdt_usd.parquet")
        .sort("timestamp")
        .select("timestamp", pl.col("close").log().alias("g"))
    )
    symbols = sorted({p.stem.split("_", 1)[1] for p in VENUE_DIR.glob("binance_*.parquet")})

    parts: list[pl.DataFrame] = []
    kept: list[str] = []
    rejected: list[tuple[str, float]] = []

    for symbol in symbols:
        legs = {v: _venue(v, symbol) for v in ("binance", "okx", "coinbaseexchange")}
        if any(leg is None for leg in legs.values()):
            continue
        frame = legs["binance"].select(  # type: ignore[union-attr]
            "timestamp",
            pl.col("close").alias("binance_close"),
            pl.col("close").log().alias("b"),
            pl.col("quote_volume").alias("vb"),
        )
        frame = frame.join(
            legs["okx"].select(  # type: ignore[union-attr]
                "timestamp", pl.col("close").log().alias("o"), pl.col("quote_volume").alias("vo")
            ),
            on="timestamp",
            how="inner",
        ).join(
            legs["coinbaseexchange"].select(  # type: ignore[union-attr]
                "timestamp", pl.col("close").log().alias("c"), pl.col("quote_volume").alias("vc")
            ),
            on="timestamp",
            how="inner",
        )
        if frame.height == 0:
            continue

        floor = min(
            frame["vb"].median() or 0.0, frame["vo"].median() or 0.0, frame["vc"].median() or 0.0
        )
        if floor < VOLUME_FLOOR:
            rejected.append((symbol, float(floor)))
            continue

        frame = frame.join(peg, on="timestamp", how="inner").sort("timestamp")
        frame = frame.with_columns(
            s1_raw_premium=pl.col("c") - pl.col("b"),
            s2_adj_premium=pl.col("c") - (pl.col("b") + pl.col("g")),
            s4_peg=pl.col("g"),
        ).with_columns(
            s3_dispersion=pl.concat_list(
                pl.col("c"), pl.col("b") + pl.col("g"), pl.col("o") + pl.col("g")
            ).list.std()
        )

        for segment in _segments(frame):
            piece = segment
            for name in SIGNALS:
                ranks = trailing_percentile_rank(
                    piece[name].to_list(), window=PCT_WINDOW, skip_nulls=False
                )
                piece = piece.with_columns(pl.Series(f"pct_{name}", ranks, dtype=pl.Float64))
            for h in HORIZONS:
                feature = forward_return(h, price_column="binance_close")
                piece = piece.with_columns(**{feature.name: feature.expr})
            piece = piece.with_columns(
                trail1=pl.col("binance_close") / pl.col("binance_close").shift(1) - 1.0,
                trail7=pl.col("binance_close") / pl.col("binance_close").shift(7) - 1.0,
            )
            parts.append(piece.with_columns(pl.lit(symbol).alias("symbol")))
        kept.append(symbol)

    panel = pl.concat(parts).rename({"timestamp": "day"})
    return panel, kept, rejected


def pooled_diff(panel: pl.DataFrame, signal: str, horizon: int) -> tuple[float, float, float, int]:
    """Pooled E[fwd | HIGH] - E[fwd | LOW], block-bootstrapped by day."""
    col = f"fwd{horizon}"
    sub = panel.drop_nulls([col, f"pct_{signal}"])
    by_day = (
        sub.with_columns(
            low=(pl.col(f"pct_{signal}") <= LOW_PCT),
            high=(pl.col(f"pct_{signal}") >= HIGH_PCT),
        )
        .group_by("day")
        .agg(
            high_sum=pl.col(col).filter(pl.col("high")).sum(),
            high_n=pl.col("high").sum(),
            low_sum=pl.col(col).filter(pl.col("low")).sum(),
            low_n=pl.col("low").sum(),
        )
        .sort("day")
        .fill_null(0.0)
    )
    ci = two_group_diff_ci(
        by_day["high_sum"].to_list(),
        by_day["high_n"].to_list(),
        by_day["low_sum"].to_list(),
        by_day["low_n"].to_list(),
        block=BLOCK_DAYS,
        seed=SEED,
        n_boot=N_BOOT,
        empty_denominator="guard",
        short_series="error",
    )
    return ci.point, ci.low, ci.high, sub.height


def breadth(panel: pl.DataFrame, signal: str, horizon: int, pooled_sign: float) -> tuple[int, int]:
    """How many symbols share the pooled estimate's sign."""
    col = f"fwd{horizon}"
    agree = 0
    total = 0
    for symbol in sorted(panel["symbol"].unique().to_list()):
        sub = panel.filter(pl.col("symbol") == symbol).drop_nulls([col, f"pct_{signal}"])
        hi = sub.filter(pl.col(f"pct_{signal}") >= HIGH_PCT)[col].mean()
        lo = sub.filter(pl.col(f"pct_{signal}") <= LOW_PCT)[col].mean()
        if hi is None or lo is None:
            continue
        total += 1
        agree += (hi - lo) * pooled_sign > 0
    return agree, total


def main() -> None:
    panel, kept, rejected = build_panel()

    print("=" * 104)
    print("H68 - CROSS-VENUE PRICE DISLOCATION (family F2 kill test, trials 153-164)")
    print("=" * 104)
    print(
        f"\nPanel: {len(kept)} symbols, {panel.height:,} symbol-days, "
        f"{str(panel['day'].min())[:10]} -> {str(panel['day'].max())[:10]}"
    )
    print(f"  kept    : {', '.join(kept)}")
    print(
        "  rejected by the $1M/day floor: "
        + ", ".join(f"{s} (${v / 1e6:.2f}M)" for s, v in rejected)
    )

    print("\n--- signal levels (basis points) ---")
    print(f"    {'signal':32}{'mean':>10}{'sd':>10}{'p10':>10}{'p90':>10}")
    for name, (label, _) in SIGNALS.items():
        col = panel[name].drop_nulls() * 1e4
        print(
            f"    {label:32}{col.mean():>10.2f}{col.std():>10.2f}"
            f"{col.quantile(0.10):>10.2f}{col.quantile(0.90):>10.2f}"
        )
    ident = (panel["s1_raw_premium"] - panel["s2_adj_premium"] - panel["s4_peg"]).abs().max()
    print(f"    identity check  max |S1 - S2 - S4| = {ident:.3e}  (must be ~0)")

    print(f"\n--- the twelve declared cells: E[fwd|HIGH] - E[fwd|LOW], primary h={PRIMARY_H} ---")
    print(f"    {'signal':22}{'h':>4}{'diff':>9}{'95% CI':>22}{'breadth':>10}{'n':>9}  verdict")
    results: dict[str, dict[int, tuple[float, float, float, int, int]]] = {}
    for name, (label, predicted) in SIGNALS.items():
        results[name] = {}
        for h in HORIZONS:
            point, lo, hi, n = pooled_diff(panel, name, h)
            sign = 1.0 if point >= 0 else -1.0
            agree, total = breadth(panel, name, h, sign)
            results[name][h] = (point, lo, hi, agree, total)

            excludes_zero = lo > 0.0 or hi < 0.0
            if not excludes_zero:
                verdict = "NOISE"
            elif predicted is not None and point * predicted < 0:
                verdict = "REVERSED"
            elif agree < BREADTH_MIN:
                verdict = f"CI ok, breadth FAILS ({agree}/{total})"
            else:
                verdict = "SIGNAL"
            mark = "  <- PRIMARY" if h == PRIMARY_H else ""
            print(
                f"    {label[:22]:22}{h:>3}d{point:>8.2%}"
                f"{'[' + f'{lo:+.2%}, {hi:+.2%}' + ']':>22}{f'{agree}/{total}':>10}{n:>9,}"
                f"  {verdict}{mark}"
            )

    print("\n--- Section 5.4 diagnostic: is it just momentum? (need |corr| small) ---")
    print(f"    {'signal':32}{'corr trail-1d':>15}{'corr trail-7d':>15}")
    for name, (label, _) in SIGNALS.items():
        sub = panel.drop_nulls([name, "trail1", "trail7"])
        c1 = sub.select(pl.corr(name, "trail1")).item()
        c7 = sub.select(pl.corr(name, "trail7")).item()
        print(f"    {label:32}{c1:>15.4f}{c7:>15.4f}")

    print("\n    same test with the top/bottom trailing-7d return deciles REMOVED:")
    lo_q = panel["trail7"].quantile(0.10)
    hi_q = panel["trail7"].quantile(0.90)
    trimmed = panel.filter(pl.col("trail7").is_between(lo_q, hi_q))
    for name, (label, _) in SIGNALS.items():
        point, lo, hi, _n = pooled_diff(trimmed, name, PRIMARY_H)
        full = results[name][PRIMARY_H][0]
        print(f"    {label:32}{point:>9.2%}  CI[{lo:+.2%}, {hi:+.2%}]   (full panel {full:+.2%})")

    print("\n--- Section 5.3 reachability rule (>= 0.5% at h=7 to proceed) ---")
    for name, (label, _) in SIGNALS.items():
        point, lo, hi, *_ = (*results[name][PRIMARY_H][:3], 0)
        ok = abs(point) >= SPREAD_FLOOR and (lo > 0.0 or hi < 0.0)
        print(f"    {label:32}|{point:.2%}| vs 0.50%  -> {'clears' if ok else 'does NOT clear'}")

    # Diagnostics on the DECLARED cells, not new cells and not new trials.
    # Both exist because this ledger has been burned by each failure mode:
    # H67 and the carry family each found a full-sample result that lived
    # entirely before 2024, and meta-finding 5 records a diversification
    # claim that was really one event counted twice.
    print(f"\n--- diagnostic: does it survive by year? (h={PRIMARY_H}, declared cells) ---")
    print(f"    {'year':6}{'symbols':>9}{'S1 diff':>11}{'S1 CI':>22}{'S2 diff':>11}{'S2 CI':>22}")
    panel_y = panel.with_columns(year=pl.col("day").dt.year())
    for year in sorted(panel_y["year"].unique().to_list()):
        group = panel_y.filter(pl.col("year") == year)
        cells = []
        for name in ("s1_raw_premium", "s2_adj_premium"):
            try:
                point, lo, hi, _ = pooled_diff(group, name, PRIMARY_H)
                cells.append((point, lo, hi))
            except Exception:
                cells.append((float("nan"),) * 3)
        (p1, l1, h1), (p2, l2, h2) = cells
        print(
            f"    {year:<6}{group['symbol'].n_unique():>9}"
            f"{p1:>10.2%}{'[' + f'{l1:+.2%}, {h1:+.2%}' + ']':>22}"
            f"{p2:>10.2%}{'[' + f'{l2:+.2%}, {h2:+.2%}' + ']':>22}"
        )

    print(f"\n--- diagnostic: is it a few symbols? (h={PRIMARY_H}, leave-out) ---")
    for name, (label, _) in SIGNALS.items():
        if name not in ("s1_raw_premium", "s2_adj_premium"):
            continue
        contributions = []
        for symbol in sorted(panel["symbol"].unique().to_list()):
            sub = panel.filter(pl.col("symbol") == symbol).drop_nulls(
                [f"fwd{PRIMARY_H}", f"pct_{name}"]
            )
            hi = sub.filter(pl.col(f"pct_{name}") >= HIGH_PCT)[f"fwd{PRIMARY_H}"].mean()
            lo = sub.filter(pl.col(f"pct_{name}") <= LOW_PCT)[f"fwd{PRIMARY_H}"].mean()
            if hi is not None and lo is not None:
                contributions.append((hi - lo, symbol))
        biggest = [s for _, s in sorted(contributions, reverse=True)[:2]]
        trimmed_panel = panel.filter(~pl.col("symbol").is_in(biggest))
        point, lo, hi, _ = pooled_diff(trimmed_panel, name, PRIMARY_H)
        full = results[name][PRIMARY_H][0]
        print(
            f"    {label:32}drop {', '.join(biggest):12} -> {point:>7.2%} "
            f"CI[{lo:+.2%}, {hi:+.2%}]   (full {full:+.2%})"
        )

    print("\n--- reported, not gated: panel composition by year ---")
    by_year = panel.with_columns(year=pl.col("day").dt.year())
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        print(
            f"    {year[0]}  symbols={group['symbol'].n_unique():>3}  "
            f"symbol-days={group.height:>6,}  "
            f"mean S2 {group['s2_adj_premium'].mean() * 1e4:+7.2f}bp  "
            f"mean S4 {group['s4_peg'].mean() * 1e4:+7.2f}bp"
        )

    print(f"\n--- per-symbol HIGH-minus-LOW at h={PRIMARY_H} ---")
    header = f"    {'symbol':9}" + "".join(f"{n.split('_')[0].upper():>12}" for n in SIGNALS)
    print(header)
    for symbol in sorted(panel["symbol"].unique().to_list()):
        sub = panel.filter(pl.col("symbol") == symbol)
        cells = []
        for name in SIGNALS:
            s = sub.drop_nulls([f"fwd{PRIMARY_H}", f"pct_{name}"])
            hi = s.filter(pl.col(f"pct_{name}") >= HIGH_PCT)[f"fwd{PRIMARY_H}"].mean()
            lo = s.filter(pl.col(f"pct_{name}") <= LOW_PCT)[f"fwd{PRIMARY_H}"].mean()
            cells.append("n/a" if hi is None or lo is None else f"{hi - lo:+.2%}")
        print(f"    {symbol:9}" + "".join(f"{c:>12}" for c in cells))

    print("\n" + "=" * 104)


if __name__ == "__main__":
    main()
