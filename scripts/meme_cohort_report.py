"""Measure the base rate of the Solana launch cohort.

This answers the question every meme-coin plan has to answer before any model
is worth building: **what does an unselected new token actually do?** Without
that number there is no baseline to beat, and every "our model found a 5x" is
unfalsifiable — 5x may be the median.

The cohort comes from the launch registry (first-sighting only, no survivor
filtering), outcomes come from minute bars pulled after the fact, and entries
are priced at the first bar we could actually have traded. Costs are then
applied with the AMM model so the headline is net, not gross.

    python scripts/meme_cohort_report.py --sample 200 --min-age-min 60

Sampling is random with a fixed seed rather than "the first N", because the
registry is time-ordered and the first N would all share one market minute.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl  # noqa: E402

from trading_bot.meme.economics import CostModel, evaluate_trade  # noqa: E402
from trading_bot.meme.http import RateLimitedJsonClient  # noqa: E402
from trading_bot.meme.outcomes import HORIZONS_MIN, measure  # noqa: E402
from trading_bot.meme.registry import LaunchRegistry  # noqa: E402
from trading_bot.meme.sources.geckoterminal import GeckoTerminalClient  # noqa: E402

GECKO_ACCEPT = "application/json;version=20230302"

logger = logging.getLogger("meme_cohort")

# Multiples reported in the upside table. 2x is "a good trade"; 10x and 100x are
# the outcomes the public winner screenshots are made of.
UPSIDE_MULTIPLES = (0.25, 0.5, 1.0, 2.0, 4.0, 9.0, 99.0)


def _pct(count: int, total: int) -> str:
    return f"{100.0 * count / total:5.1f}%" if total else "    n/a"


def build(args: argparse.Namespace) -> pl.DataFrame:
    registry = LaunchRegistry(args.root)
    rows = list(registry.iter_rows())
    now = datetime.now(UTC)

    eligible: list[dict[str, Any]] = []
    for row in rows:
        stamp = row.get("observed_at")
        if not isinstance(stamp, str):
            continue
        observed_at = datetime.fromisoformat(stamp)
        age_min = (now - observed_at).total_seconds() / 60.0
        if age_min < args.min_age_min:
            continue
        row["_observed_at"] = observed_at
        eligible.append(row)

    logger.info(
        "registry: %d rows, %d aged >= %.0f min", len(rows), len(eligible), args.min_age_min
    )
    if not eligible:
        raise SystemExit("no launches old enough yet — let the recorder run longer")

    rng = random.Random(args.seed)
    sample = rng.sample(eligible, min(args.sample, len(eligible)))
    logger.info("pulling bars for %d sampled pools", len(sample))

    # Slower than the client default: the recorder is usually running alongside
    # this and both share one 30-request/minute budget. Getting throttled here
    # would also stall the recorder, which is the more valuable of the two.
    client = GeckoTerminalClient(
        network="solana",
        client=RateLimitedJsonClient(min_interval_s=args.min_interval, accept=GECKO_ACCEPT),
    )

    # Resume support: bar pulls are slow (one throttled request each, slower
    # still when the API throttles us), so a run that is interrupted must not
    # throw away what it already fetched. Rows are appended as they complete
    # and addresses already present are skipped.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    done: set[str] = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            existing: dict[str, Any] = json.loads(line)
            records.append(existing)
            done.add(str(existing.get("pool_address")))
        logger.info("resuming: %d pools already measured", len(done))

    pending = [row for row in sample if row["pool_address"] not in done]
    with args.out.open("a", encoding="utf-8") as handle:
        for i, row in enumerate(pending, start=1):
            address = row["pool_address"]
            try:
                bars = client.ohlcv(address, timeframe="minute", aggregate=1, limit=1000)
            except Exception as exc:  # noqa: BLE001 - a dead pool 404s; that is data, not failure
                logger.debug("ohlcv failed for %s: %s", address, exc)
                bars = []
            outcome = measure(address, bars, row["_observed_at"])
            record = outcome.to_row()
            record["reserve_usd_at_discovery"] = row.get("reserve_usd")
            record["fdv_usd_at_discovery"] = row.get("fdv_usd")
            record["buys_m5_at_discovery"] = row.get("buys_m5")
            record["sells_m5_at_discovery"] = row.get("sells_m5")
            record["buyers_m5_at_discovery"] = row.get("buyers_m5")
            record["volume_m5_at_discovery"] = row.get("volume_m5")
            record["age_s_at_discovery"] = row.get("age_s")
            record["dex"] = row.get("dex")
            record["name"] = row.get("name")
            records.append(record)
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
            handle.flush()
            if i % 10 == 0:
                logger.info("  %d/%d measured", i, len(pending))
                sys.stdout.flush()

    logger.info("wrote %d outcome rows -> %s", len(records), args.out)
    return pl.DataFrame(records, infer_schema_length=None)


def report(frame: pl.DataFrame, notional: float, model: CostModel) -> None:
    total = frame.height
    measurable = frame.filter(pl.col("entry_price").is_not_null())
    n = measurable.height

    print("\n" + "=" * 78)
    print("SOLANA LAUNCH COHORT — BASE RATE")
    print("=" * 78)
    print(f"sampled pools            : {total}")
    print(f"priceable entry found    : {n} ({100.0 * n / total:.1f}%)")
    if n == 0:
        return

    print("\n--- forward returns, gross (close-to-close from realistic entry) ---")
    print(f"{'horizon':>8} {'n':>6} {'median':>9} {'mean':>9} {'p90':>9} {'p99':>10} {'>0':>7}")
    for horizon in HORIZONS_MIN:
        col = f"ret_{horizon}m"
        series = measurable.get_column(col).drop_nulls()
        if series.len() == 0:
            continue
        wins = int((series > 0).sum())
        print(
            f"{horizon:>7}m {series.len():>6} "
            f"{series.median():>8.1%} {series.mean():>8.1%} "
            f"{series.quantile(0.90):>8.1%} {series.quantile(0.99):>9.1%} "
            f"{_pct(wins, series.len()):>7}"
        )

    print("\n--- upside reachable at any point (MFE, i.e. a perfect exit) ---")
    hits_header = "  ".join(f"{'+' + format(m * 100, '.0f') + '%':>7}" for m in UPSIDE_MULTIPLES)
    print(f"{'horizon':>8} {'n':>6}  {hits_header}")
    for horizon in HORIZONS_MIN:
        series = measurable.get_column(f"mfe_{horizon}m").drop_nulls()
        if series.len() == 0:
            continue
        cells = "  ".join(_pct(int((series >= m).sum()), series.len()) for m in UPSIDE_MULTIPLES)
        print(f"{horizon:>7}m {series.len():>6}  {cells}")

    print("\n--- downside suffered (MAE, i.e. the worst moment you had to sit through) ---")
    print(f"{'horizon':>8} {'n':>6} {'median':>9} {'<-50%':>8} {'<-90%':>8}")
    for horizon in HORIZONS_MIN:
        series = measurable.get_column(f"mae_{horizon}m").drop_nulls()
        if series.len() == 0:
            continue
        print(
            f"{horizon:>7}m {series.len():>6} {series.median():>8.1%} "
            f"{_pct(int((series <= -0.5).sum()), series.len()):>8} "
            f"{_pct(int((series <= -0.9).sum()), series.len()):>8}"
        )

    _cost_section(measurable, notional, model)


def _cost_section(measurable: pl.DataFrame, notional: float, model: CostModel) -> None:
    """Turn gross moves into what a real account would have kept."""
    reserves = measurable.get_column("reserve_usd_at_discovery").drop_nulls()
    print(f"\n--- cost reality at ${notional:,.0f} per position ---")
    if reserves.len() == 0:
        print("no reserve data recorded at discovery")
        return

    print(
        f"pool depth at discovery  : median ${reserves.median():,.0f}, "
        f"p10 ${reserves.quantile(0.10):,.0f}, p90 ${reserves.quantile(0.90):,.0f}"
    )

    verdicts = [evaluate_trade(notional, float(r), model) for r in reserves]
    tradable = [v for v in verdicts if v.viable]
    fracs = sorted(v.round_trip_frac for v in verdicts)
    median_frac = fracs[len(fracs) // 2]
    print(f"round-trip friction      : median {median_frac:.1%} of position")
    print(
        f"pools inside cost floor  : {len(tradable)}/{len(verdicts)} "
        f"({100.0 * len(tradable) / len(verdicts):.1f}%)"
    )
    print(f"breakeven move required  : {median_frac:+.1%} before a cent of profit")

    # Net expectancy of the null strategy: buy every launch, hold to horizon.
    print("\n--- buy-every-launch, hold to horizon, NET of costs ---")
    print(f"{'horizon':>8} {'n':>6} {'net mean':>10} {'net median':>11} {'net >0':>8}")
    for horizon in HORIZONS_MIN:
        joined = measurable.select(
            pl.col(f"ret_{horizon}m").alias("ret"),
            pl.col("reserve_usd_at_discovery").alias("reserve"),
        ).drop_nulls()
        if joined.height == 0:
            continue
        nets = [
            float(ret) - model.round_trip_cost_frac(notional, float(reserve))
            for ret, reserve in zip(
                joined.get_column("ret"), joined.get_column("reserve"), strict=True
            )
        ]
        series = pl.Series(nets)
        print(
            f"{horizon:>7}m {series.len():>6} {series.mean():>9.1%} "
            f"{series.median():>10.1%} {_pct(int((series > 0).sum()), series.len()):>8}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/meme/launches"))
    parser.add_argument("--out", type=Path, default=Path("data/meme/outcomes.jsonl"))
    parser.add_argument("--sample", type=int, default=200, help="pools to pull bars for")
    parser.add_argument("--min-age-min", type=float, default=45.0, help="min age to be measurable")
    parser.add_argument("--notional", type=float, default=50.0, help="position size for costing")
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--min-interval", type=float, default=3.0, help="seconds between requests")
    parser.add_argument("--reuse", action="store_true", help="report from --out without refetching")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)

    if args.reuse and args.out.exists():
        rows = [
            json.loads(line) for line in args.out.read_text(encoding="utf-8").splitlines() if line
        ]
        frame = pl.DataFrame(rows, infer_schema_length=None)
        logger.info("reusing %d rows from %s", frame.height, args.out)
    else:
        frame = build(args)

    report(frame, args.notional, CostModel())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
