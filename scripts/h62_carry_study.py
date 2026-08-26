"""H62: delta-neutral funding carry, against its five pre-registered bars.

    .venv/Scripts/python scripts/h62_carry_study.py

Pre-registered in docs/hypotheses/62-delta-neutral-carry.md, committed
2026-08-27 BEFORE this script was written. The universe, the always-on
rule, the 1x collateralization and all five bars are fixed by that
document and are read from it, not chosen here.

Trial 126.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from martex_quant.backtesting.carry import CarryConfig, build_symbol_frame, run_carry
from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.stats.bootstrap import daily_mean_ci

ROOT = Path(".")
N_TRIALS = 126
SEED = 20260827
N_BOOT = 2_000
BLOCK = 30

# FIXED BY THE PRE-REGISTRATION. Do not edit to chase a result.
UNIVERSE = (
    "ADAUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "ETHUSDT",
    "LTCUSDT",
    "SOLUSDT",
    "XRPUSDT",
)
BAR_MIN_CAGR = 2.0
BAR_MIN_SHARPE = 1.0
BAR_MAX_CORR = 0.30
BAR_DSR = 0.95


def load_frames() -> dict[str, pl.DataFrame]:
    store = ParquetStore(ROOT / "data/lake")
    frames: dict[str, pl.DataFrame] = {}
    for symbol in UNIVERSE:
        spot = store.read(symbol, Interval.D1)
        perp = pl.read_parquet(ROOT / f"data/perp/{symbol}.parquet")
        funding = pl.read_parquet(ROOT / f"data/funding/{symbol}.parquet")
        frames[symbol] = build_symbol_frame(spot, perp, funding)
    return frames


def correlation_with_rotation_stop(daily: pl.DataFrame) -> tuple[float, int]:
    """Timestamp-joined correlation on the common window.

    Meta-finding 5: tail-count alignment once produced a false 0.35 where
    the true figure was 0.77. Join on timestamp, never on position.
    """
    series = SeriesStore(ROOT)
    rot = series.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    rot_ret = (
        rot.sort("timestamp")
        .select(
            pl.col("timestamp").dt.truncate("1d").alias("timestamp"),
            pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret"),
        )
        .group_by("timestamp")
        .agg(pl.col("rot_ret").last())
    )
    ours = daily.select(
        pl.col("timestamp").dt.truncate("1d").alias("timestamp"),
        pl.col("ret").alias("carry_ret"),
    )
    joined = ours.join(rot_ret, on="timestamp", how="inner").drop_nulls()
    if joined.height < 30:
        return float("nan"), joined.height
    corr = joined.select(pl.corr("carry_ret", "rot_ret")).item()
    return float(corr), joined.height


def main() -> None:
    config = CarryConfig()
    frames = load_frames()
    result = run_carry(frames, config)
    daily = result.daily
    rets = daily["ret"].to_list()

    print("=" * 78)
    print("H62 — DELTA-NEUTRAL FUNDING CARRY (trial 126)")
    print("=" * 78)
    print(f"\nUniverse: {result.n_symbols} symbols (fixed by pre-registration)")
    print(
        f"Common window: {result.n_days} days, "
        f"{str(daily['timestamp'].min())[:10]} -> {str(daily['timestamp'].max())[:10]}"
    )
    print(
        f"Collateralization: {config.collateral_ratio:.0%} spot / "
        f"{1 - config.collateral_ratio:.0%} margin (perp leverage 1.0x)"
    )
    print(
        f"Costs: {config.fee_bps:.0f}bp fee + {config.half_spread_bps:.0f}bp "
        f"half-spread, BOTH legs\n"
    )

    metrics = compute_metrics(result.equity, [], Interval.D1)

    print("--- return decomposition (annualized, of deployed capital) ---")
    yrs = result.n_days / 365.25
    for name, col in (
        ("funding collected", "funding_ret"),
        ("basis drift", "basis_ret"),
        ("costs", "cost_ret"),
    ):
        total = sum(daily[col].to_list())
        print(f"  {name:<20} {total / yrs * 100:+8.3f} %/yr")
    print(f"  {'NET':<20} {sum(rets) / yrs * 100:+8.3f} %/yr (simple sum)")

    ci = daily_mean_ci(
        rets,
        block=BLOCK,
        seed=SEED,
        n_boot=N_BOOT,
        accumulation="prefix_delta",
        short_series="error",
    )
    corr, corr_n = correlation_with_rotation_stop(daily)

    pp = (sum(rets) / len(rets)) / (pl.Series(rets).std() or 1.0)
    skew, kurt = pl.Series(rets).skew(), pl.Series(rets).kurtosis()
    var = pl.Series(rets).var() or 0.0
    dsr = probabilistic_sharpe_ratio(
        pp,
        n_obs=len(rets),
        skew=float(skew) if skew is not None else 0.0,
        kurtosis=(float(kurt) + 3.0) if kurt is not None else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, float(var)),
    )

    print("\n--- the five pre-registered bars ---")
    b1 = ci.low > 0.0
    b2 = metrics.cagr_pct >= BAR_MIN_CAGR
    b3 = metrics.sharpe >= BAR_MIN_SHARPE
    b4 = abs(corr) < BAR_MAX_CORR
    b5 = dsr >= BAR_DSR
    print(
        f"  1. mean daily net > 0, CI excludes zero : {ci.point * 1e4:+.3f}bp/day "
        f"CI [{ci.low * 1e4:+.3f}, {ci.high * 1e4:+.3f}]bp  -> {'PASS' if b1 else 'FAIL'}"
    )
    print(
        f"  2. net CAGR >= {BAR_MIN_CAGR:.0f}%/yr                : "
        f"{metrics.cagr_pct:+.2f}%  -> {'PASS' if b2 else 'FAIL'}"
    )
    print(
        f"  3. Sharpe >= {BAR_MIN_SHARPE:.1f}                     : "
        f"{metrics.sharpe:.2f}  -> {'PASS' if b3 else 'FAIL'}"
    )
    print(
        f"  4. |corr| with rotation-stop < {BAR_MAX_CORR:.2f}     : "
        f"{corr:+.4f} (n={corr_n})  -> {'PASS' if b4 else 'FAIL'}"
    )
    print(
        f"  5. DSR_global >= {BAR_DSR:.2f} @ {N_TRIALS} trials   : "
        f"{dsr:.4f}  -> {'PASS' if b5 else 'FAIL'}"
    )
    print(
        f"\n  MDD {metrics.max_drawdown_pct:.2f}%   "
        f"({'; '.join(f'{k}={v}' for k, v in (('days', result.n_days),))})"
    )

    # Mandatory robustness. H05 flagged IN ADVANCE that "the recent regime
    # is much thinner than the 4y mean", so this is a pre-flagged concern
    # being checked, not a post-hoc slice hunt. It can only weaken the
    # result, never strengthen it: no bar is revised from what it finds.
    print("\n--- robustness: regime concentration (H05's pre-flagged concern) ---")
    by_year = daily.with_columns(year=pl.col("timestamp").dt.year())
    for year, group in sorted(by_year.group_by("year"), key=lambda kv: kv[0]):
        r = group["ret"]
        n = group.height
        ann = r.sum() / (n / 365.25) * 100.0
        sharpe = (r.mean() or 0.0) / (r.std() or 1.0) * (365.25**0.5)
        fund = group["funding_ret"].sum() / (n / 365.25) * 100.0
        print(
            f"  {year[0]}  n={n:>4}  net={ann:+7.2f}%/yr  "
            f"funding={fund:+6.2f}%/yr  Sharpe={sharpe:6.2f}"
        )
    for window in (365, 730):
        tail = daily.tail(window)["ret"]
        ann = tail.sum() / (window / 365.25) * 100.0
        sharpe = (tail.mean() or 0.0) / (tail.std() or 1.0) * (365.25**0.5)
        print(f"  last {window:>3}d: net={ann:+7.2f}%/yr  Sharpe={sharpe:6.2f}")

    passed = [b1, b2, b3, b4, b5]
    print("\n" + "=" * 78)
    if all(passed):
        print("VERDICT: ALL FIVE BARS PASS -> strategy-grade, paper-eligible.")
    elif b1 and b2 and b3 and b5 and not b4:
        print("VERDICT: STANDALONE-VIABLE — real edge, but NOT the independent")
        print("diversifier it was built to be (bar 4 failed). Not deployed.")
        print("Per docs/research/standalone-viable-amendment.md.")
    else:
        print(f"VERDICT: KILLED — {sum(passed)}/5 bars. Four of five is not a pass.")
    print("=" * 78)

    out = ROOT / "data/tmp/h62_carry"
    out.mkdir(parents=True, exist_ok=True)
    daily.write_parquet(out / "carry_stream.parquet")
    (out / "verdict.json").write_text(
        json.dumps(
            {
                "n_days": result.n_days,
                "cagr_pct": metrics.cagr_pct,
                "sharpe": metrics.sharpe,
                "mdd_pct": metrics.max_drawdown_pct,
                "corr_rotation_stop": corr,
                "dsr": dsr,
                "bars": {f"bar{i + 1}": bool(b) for i, b in enumerate(passed)},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
