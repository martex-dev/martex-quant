"""Base rate of the Solana launch cohort, from the recorded forward panel.

This is the number the whole meme program hinges on: what an **unselected** new
launch does, entered at a price we could actually have paid, net of AMM costs.
Everything else - filters, models, wallet signals - is only meaningful as a
delta against this.

    python scripts/meme_base_rate.py --notional 50

Reads the launch registry (cohort membership, fixed at birth) and the panel
(observed states), joins them, and reports gross outcomes, the upside tail, and
what an account of a given size would actually have kept.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl  # noqa: E402

from trading_bot.meme.economics import CostModel  # noqa: E402
from trading_bot.meme.panel import (  # noqa: E402
    HORIZONS_MIN,
    coverage_summary,
    measure_launch,
    read_panel,
)
from trading_bot.meme.registry import LaunchRegistry  # noqa: E402

logger = logging.getLogger("meme_base_rate")

# Upside thresholds, as fractional returns. 9.0 == 10x, 99.0 == 100x.
UPSIDE = ((0.5, "+50%"), (1.0, "2x"), (3.0, "4x"), (9.0, "10x"), (99.0, "100x"))

# Round-trip friction above which we treat a pool as untradable, matching
# economics.evaluate_trade's default ceiling.
COST_CEILING = 0.15

# Peak returns beyond this are almost certainly a price-from-near-zero artifact
# (a pool initialised at a dust price, then quoted normally) rather than a move
# anyone could have captured. Counted and reported, never silently dropped.
ABSURD_PEAK = 1_000.0  # 100,000%, i.e. 1000x


def _pct(count: int, total: int) -> str:
    return f"{100.0 * count / total:5.2f}%" if total else "    -"


def build(args: argparse.Namespace) -> pl.DataFrame:
    registry = LaunchRegistry(args.root)
    panel = read_panel(args.panel)
    logger.info("panel: %s", coverage_summary(panel))

    records: list[dict[str, Any]] = []
    for row in registry.iter_rows():
        address = row.get("pool_address")
        stamp = row.get("observed_at")
        if not isinstance(address, str) or not isinstance(stamp, str):
            continue
        observations = panel.get(address)
        if not observations:
            continue
        outcome = measure_launch(address, observations, datetime.fromisoformat(stamp))
        record = outcome.to_row()
        # Features known at registration - the only ones a filter may use.
        record["reserve_at_discovery"] = row.get("reserve_usd")
        record["fdv_at_discovery"] = row.get("fdv_usd")
        record["buys_m5_at_discovery"] = row.get("buys_m5")
        record["sells_m5_at_discovery"] = row.get("sells_m5")
        record["buyers_m5_at_discovery"] = row.get("buyers_m5")
        record["volume_m5_at_discovery"] = row.get("volume_m5")
        record["age_s_at_discovery"] = row.get("age_s")
        record["dex"] = row.get("dex")
        records.append(record)

    if not records:
        raise SystemExit("no launches with panel observations yet - let the pollers run longer")

    frame = pl.DataFrame(records, infer_schema_length=None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
    logger.info("joined %d launches -> %s", frame.height, args.out)
    return frame


def report(frame: pl.DataFrame, notional: float, model: CostModel) -> None:
    total = frame.height
    live = frame.filter(pl.col("entry_price").is_not_null())
    n = live.height

    print("\n" + "=" * 82)
    print("SOLANA LAUNCH COHORT - BASE RATE (unselected, first-sighting cohort)")
    print("=" * 82)
    print(f"launches with panel data : {total}")
    print(f"with a tradable entry    : {n} ({100.0 * n / total:.1f}%)")
    if n == 0:
        print("\nNot enough panel passes yet. Let the poller run and re-run this.")
        return

    delisted = int(live.get_column("delisted_at_min").is_not_null().sum())
    print(f"delisted during tracking : {delisted} ({100.0 * delisted / n:.1f}%)")

    print("\n--- gross forward return from a realistic entry ---")
    print(f"{'horizon':>8} {'n':>6} {'median':>9} {'mean':>9} {'p90':>9} {'p99':>10} {'up':>8}")
    for horizon in HORIZONS_MIN:
        series = live.get_column(f"ret_{horizon}m").drop_nulls()
        if series.len() == 0:
            continue
        print(
            f"{horizon:>7}m {series.len():>6} {series.median():>8.1%} {series.mean():>8.1%} "
            f"{series.quantile(0.90):>8.1%} {series.quantile(0.99):>9.1%} "
            f"{_pct(int((series > 0).sum()), series.len()):>8}"
        )

    print("\n--- upside ever reached (MFE - assumes a perfect exit) ---")
    header = "  ".join(f"{label:>7}" for _, label in UPSIDE)
    print(f"{'horizon':>8} {'n':>6}  {header}")
    for horizon in HORIZONS_MIN:
        series = live.get_column(f"mfe_{horizon}m").drop_nulls()
        if series.len() == 0:
            continue
        cells = "  ".join(_pct(int((series >= t).sum()), series.len()) for t, _ in UPSIDE)
        print(f"{horizon:>7}m {series.len():>6}  {cells}")

    print("\n--- downside endured (MAE) ---")
    print(f"{'horizon':>8} {'n':>6} {'median':>9} {'<-50%':>8} {'<-90%':>8}")
    for horizon in HORIZONS_MIN:
        series = live.get_column(f"mae_{horizon}m").drop_nulls()
        if series.len() == 0:
            continue
        print(
            f"{horizon:>7}m {series.len():>6} {series.median():>8.1%} "
            f"{_pct(int((series <= -0.5).sum()), series.len()):>8} "
            f"{_pct(int((series <= -0.9).sum()), series.len()):>8}"
        )

    _inertia_section(live)
    _tradable_universe(live, model)
    _net_section(live, notional, model)
    _tail_section(live)


def _tradable_universe(live: pl.DataFrame, model: CostModel) -> None:
    """How many launches can an account of a given size actually buy?

    This runs before any return statistics because it bounds them. A cohort
    strategy needs many tickets; if the median launch is too thin to absorb one
    ticket at any sane cost, the number of available tickets - not the hit rate
    - is the binding constraint, and no model changes that.
    """
    depth = live.get_column("entry_liquidity").drop_nulls()
    if depth.len() == 0:
        return
    cohort = live.height
    print("\n--- tradable universe (pools inside a 15% round-trip cost ceiling) ---")
    # Two denominators, both reported, because they say different things: the
    # aggregator omits a liquidity figure entirely for most launches (they are
    # dust), and a pool with no reported depth is not a pool we can size into.
    print(
        f"  {depth.len()}/{cohort} launches report any liquidity at entry "
        f"({100.0 * depth.len() / cohort:.1f}%); the rest are too small to quote"
    )
    print(f"{'ticket':>9} {'tradable':>10} {'of quoted':>11} {'of cohort':>11}")
    for ticket in (10.0, 25.0, 50.0, 100.0, 250.0, 1_000.0):
        ok = sum(
            1 for liquidity in depth if model.round_trip_cost_frac(ticket, float(liquidity)) <= 0.15
        )
        print(
            f"${ticket:>8,.0f} {ok:>10} {100.0 * ok / depth.len():>10.1f}% "
            f"{100.0 * ok / cohort:>10.1f}%"
        )
    print(
        "  depth deciles: "
        + ", ".join(
            f"p{int(q * 100)}=${depth.quantile(q):,.0f}" for q in (0.1, 0.25, 0.5, 0.75, 0.9)
        )
    )


def _net_section(live: pl.DataFrame, notional: float, model: CostModel) -> None:
    """Net outcomes, computed ONLY over pools the ticket could actually enter.

    Two corrections versus the naive version, both of which changed the
    headline materially:

    Applying a 204%-friction cost to a pool we would never trade produces a
    "net return" of -189%, which is not a loss any spot position can take. The
    universe is therefore restricted to pools inside the cost ceiling first,
    and net returns are floored at -100%. Reporting the unrestricted number
    would answer a question nobody can act on.

    Means are reported alongside a trimmed mean because a single 5,600,000x
    outlier moves the raw mean by thousands of percent. The raw mean is kept
    visible rather than dropped - in a power-law market the tail IS the
    result, and hiding it would misrepresent the strategy just as badly.
    """
    print(f"\n--- what a ${notional:,.0f} ticket actually keeps ---")
    depth = live.get_column("entry_liquidity").drop_nulls()
    if depth.len() == 0:
        print("no liquidity recorded at entry")
        return
    print(
        f"pool depth at entry      : median ${depth.median():,.0f}, "
        f"p10 ${depth.quantile(0.10):,.0f}, p90 ${depth.quantile(0.90):,.0f}"
    )

    tradable = live.filter(
        pl.col("entry_liquidity").is_not_null()
        & (
            pl.col("entry_liquidity").map_elements(
                lambda liq: model.round_trip_cost_frac(notional, float(liq)),
                return_dtype=pl.Float64,
            )
            <= COST_CEILING
        )
    )
    print(
        f"tradable at ${notional:,.0f}       : {tradable.height}/{live.height} "
        f"({100.0 * tradable.height / live.height:.1f}% of cohort)"
    )
    if tradable.height == 0:
        print("no pool in this cohort can absorb that ticket -- nothing to report")
        return

    tradable_depth = tradable.get_column("entry_liquidity")
    median_cost = model.round_trip_cost_frac(notional, float(tradable_depth.median()))
    print(f"round-trip friction      : {median_cost:.1%} at median TRADABLE depth")
    print(f"breakeven move needed    : +{median_cost:.1%} before any profit")

    print(
        f"\n{'horizon':>8} {'n':>6} {'net med':>9} {'trim mean':>11} {'raw mean':>12} {'win%':>7}"
    )
    for horizon in HORIZONS_MIN:
        joined = tradable.select(
            pl.col(f"ret_{horizon}m").alias("ret"),
            pl.col("entry_liquidity").alias("liq"),
        ).drop_nulls()
        if joined.height == 0:
            continue
        nets = [
            # Floored at -100%: a spot position cannot lose more than the stake,
            # however brutal the modelled friction.
            max(-1.0, float(ret) - model.round_trip_cost_frac(notional, float(liq)))
            for ret, liq in zip(joined.get_column("ret"), joined.get_column("liq"), strict=True)
        ]
        series = pl.Series(nets)
        ordered = sorted(nets)
        cut = int(len(ordered) * 0.01)
        trimmed = ordered[cut : len(ordered) - cut] if len(ordered) > 20 * 2 else ordered
        trim_mean = sum(trimmed) / len(trimmed) if trimmed else 0.0
        print(
            f"{horizon:>7}m {series.len():>6} {series.median():>8.1%} {trim_mean:>10.1%} "
            f"{series.mean():>11.1%} {_pct(int((series > 0).sum()), series.len()):>7}"
        )


def _tail_section(live: pl.DataFrame) -> None:
    """How concentrated is the upside? This decides whether tickets can work."""
    peaks = live.get_column("peak_return").drop_nulls().sort(descending=True)
    if peaks.len() == 0:
        return
    print("\n--- concentration of upside (peak return, best first) ---")
    for k in (1, 5, 10, 25, 50):
        if peaks.len() >= k:
            print(f"  #{k:<3} best peak : {peaks[k - 1]:>14.1%}")
    positive = peaks.filter(peaks > 0)
    print(
        f"  pools with any positive peak : {positive.len()}/{peaks.len()} "
        f"({100.0 * positive.len() / peaks.len():.1f}%)"
    )
    absurd = peaks.filter(peaks >= ABSURD_PEAK)
    print(
        f"  peaks above 1000x (likely dust-price artifacts, excluded from no "
        f"statistic below): {absurd.len()}"
    )
    credible = peaks.filter(peaks < ABSURD_PEAK)
    if credible.len() > 0:
        print(f"  best credible peak (<1000x)  : {credible.max():.1%}")


def _inertia_section(live: pl.DataFrame) -> None:
    """How many launches simply never trade again after we see them?

    This is the modal outcome and it is invisible in return statistics, which
    report it as a clean 0.0%. A pool that is created and then never touched is
    not a flat trade - it is an asset with no bid, and it is the single most
    common thing that happens to a new Solana token.
    """
    print("\n--- did the token ever actually trade? ---")
    for horizon in HORIZONS_MIN:
        frame = live.select(
            pl.col(f"ret_{horizon}m").alias("ret"),
            pl.col(f"mfe_{horizon}m").alias("mfe"),
            pl.col(f"mae_{horizon}m").alias("mae"),
        ).drop_nulls()
        if frame.height == 0:
            continue
        frozen = frame.filter(
            (pl.col("ret").abs() < 1e-9)
            & (pl.col("mfe").abs() < 1e-9)
            & (pl.col("mae").abs() < 1e-9)
        ).height
        print(
            f"{horizon:>7}m {frame.height:>6} observed, {frozen:>6} never moved "
            f"({100.0 * frozen / frame.height:>5.1f}%)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/meme/launches"))
    parser.add_argument("--panel", type=Path, default=Path("data/meme/panel"))
    parser.add_argument("--out", type=Path, default=Path("data/meme/launch_outcomes.jsonl"))
    parser.add_argument("--notional", type=float, default=50.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
    frame = build(args)
    report(frame, args.notional, CostModel())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
