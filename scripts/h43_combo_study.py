"""H43 combination batch: correlation screen + conditional blend trials.

    .venv/Scripts/python scripts/h43_combo_study.py

Pre-registered in docs/hypotheses/43-combo-batch.md. Reuses the cached
validation streams written by scripts/h41_h42_fub1_studies.py
(data/tmp/h4x_streams). Run that script first if the cache is missing.
"""

from __future__ import annotations

import contextlib
import json
import statistics
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.risk_management.prop_sim import PropFirmRules, simulate_evaluation

N_TRIALS = 107
SCREEN_BAR = 0.30
BOUNCE_COST_RT = 0.0022
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 51.80, static_max_loss_pct=0.06
)
CACHE_DIR = Path("data/tmp/h4x_streams")
SERIES = SeriesStore(Path("."))


def summarize(name: str, rets: pl.DataFrame, scale: float = 0.5) -> dict[str, float]:
    curve = pl.DataFrame(
        {
            "timestamp": rets["timestamp"],
            "equity": (1.0 + rets["ret"]).cum_prod() * 10_000.0,
            "exposure": pl.Series([1.0] * rets.height),
        }
    )
    m = compute_metrics(curve, [], Interval.D1)
    r = simulate_evaluation(rets["ret"].to_list(), FIRM_RULES, scale, n_paths=20_000)
    print(
        f"  {name:<28} {rets.height}d  Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
        f"MDD {m.max_drawdown_pct:.1f}%  prop@{scale}x {r.pass_rate:.1%} "
        f"(median {r.median_days_to_pass}d)"
    )
    return {"sharpe": m.sharpe, "mdd": m.max_drawdown_pct, "pass": r.pass_rate}


def dsr_of(rets: pl.Series, other_pp: float) -> float:
    pp = (rets.mean() or 0.0) / (rets.std() or 1.0)
    skew, kurt = rets.skew(), rets.kurtosis()
    return probabilistic_sharpe_ratio(
        pp,
        n_obs=rets.len(),
        skew=skew if isinstance(skew, float) else 0.0,
        kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, statistics.variance([pp, other_pp])),
    )


def pp_of(rets: pl.Series) -> float:
    return (rets.mean() or 0.0) / (rets.std() or 1.0)


def corr_on_common(a: pl.DataFrame, b: pl.DataFrame, name: str) -> float:
    joined = a.join(b.rename({"ret": "ret_b"}), on="timestamp", how="inner")
    corr = joined.select(pl.corr("ret", "ret_b")).item()
    print(
        f"  corr {name:<44} {corr:+.3f}  ({joined.height}d common)  "
        f"{'ADMITTED' if abs(corr) < SCREEN_BAR else 'SCREENED OUT'}"
    )
    assert isinstance(corr, float)
    return corr


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]

    v1 = SERIES.read(SeriesKind.RETURN_STREAM, "v1_stream")
    rot = SERIES.read(SeriesKind.EQUITY_STREAM, "rot_champion_stream")
    rot_stop = SERIES.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    rot_rets = rot.select("timestamp", pl.col("equity").pct_change().fill_null(0.0).alias("ret"))
    ts_dtype = rot_stop.schema["timestamp"]

    # Crash-bounce overlay on rotation-stop's own idle cash (H41 construction).
    frames = {}
    for symbol in universe:
        with contextlib.suppress(FileNotFoundError):
            frames[symbol] = store.read(symbol, Interval.D1)
    btc_ret = (
        frames["BTCUSDT"]
        .sort("timestamp")
        .select(
            pl.col("timestamp").cast(ts_dtype),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("btc_ret"),
        )
    )
    alt_parts = [
        df.sort("timestamp").select(
            pl.col("timestamp").cast(ts_dtype),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("aret"),
        )
        for s, df in frames.items()
        if s != "BTCUSDT"
    ]
    alt_ew = (
        pl.concat(alt_parts)
        .drop_nulls()
        .group_by("timestamp")
        .agg(pl.col("aret").mean().alias("alt_ew_ret"))
        .sort("timestamp")
    )
    book = (
        rot_stop.select(
            "timestamp",
            pl.col("equity").pct_change().fill_null(0.0).alias("ret"),
            "exposure",
        )
        .join(btc_ret, on="timestamp", how="left")
        .join(alt_ew, on="timestamp", how="left")
        .sort("timestamp")
        .with_columns(
            trigger_prev=(pl.col("btc_ret").shift(1) < -0.03).fill_null(False),  # noqa: FBT003
            idle_prev=(1.0 - pl.col("exposure").shift(1)).clip(0.0, 1.0),
        )
        .with_columns(
            overlay_ret=pl.when(pl.col("trigger_prev"))
            .then(pl.col("idle_prev") * (pl.col("alt_ew_ret") - BOUNCE_COST_RT))
            .otherwise(0.0)
            .fill_null(0.0)
        )
    )
    rot_stop_rets = book.select("timestamp", "ret")
    overlay = book.select("timestamp", pl.col("overlay_ret").alias("ret"))

    print("=== H43 correlation screen (descriptive, not trials) ===")
    c_a = corr_on_common(rot_stop_rets, v1, "(a) rotation-stop x vol-target V1")
    corr_on_common(rot_stop_rets, rot_rets, "(b) rotation-stop x champion rotation")
    c_c = corr_on_common(rot_stop_rets, overlay, "(c) rotation-stop x crash-bounce overlay")
    c_d = corr_on_common(v1, overlay, "(d) V1 x crash-bounce overlay")
    print()

    # ---------- 43a ----------
    if abs(c_c) < SCREEN_BAR:
        print("=== 43a: rotation-stop + crash-bounce overlay (FIRED) ===")
        n_trig = book.filter(pl.col("trigger_prev")).height
        mean_idle = book.filter(pl.col("trigger_prev"))["idle_prev"].mean()
        print(f"  bounce days: {n_trig}; mean idle cash deployed {(mean_idle or 0.0):.0%}")
        combined = book.with_columns(combined=pl.col("ret") + pl.col("overlay_ret"))
        m_base = summarize("rotation-stop alone", rot_stop_rets)
        m_comb = summarize(
            "rot-stop + bounce", combined.select("timestamp", pl.col("combined").alias("ret"))
        )
        dsr = dsr_of(combined["combined"], pp_of(rot_stop_rets["ret"]))
        bar1 = m_comb["sharpe"] > m_base["sharpe"]
        bar2 = m_comb["pass"] > m_base["pass"]
        bar3 = m_comb["mdd"] >= m_base["mdd"] - 5.0
        print(f"  combined DSR({N_TRIALS}): {dsr:.3f}")
        print(
            f"  43a VERDICT: bar1 Sharpe {'PASS' if bar1 else 'fail'}; "
            f"bar2 prop@0.5x {'PASS' if bar2 else 'fail'}; "
            f"bar3 MDD {'PASS' if bar3 else 'fail'} -> "
            f"{'ELIGIBLE FOR PAPER' if bar1 and bar2 and bar3 else 'KILLED'}\n"
        )
    else:
        print("43a SCREENED OUT (corr >= 0.30) — no trial consumed\n")

    # ---------- 43b ----------
    if abs(c_a) < SCREEN_BAR:
        print("=== 43b: 50/50 rotation-stop + V1 (FIRED) ===")
        blend = rot_stop_rets.join(v1.rename({"ret": "ret_v1"}), on="timestamp", how="inner")
        blend = blend.with_columns(ret=(pl.col("ret") + pl.col("ret_v1")) / 2.0)
        m_a = summarize("rotation-stop (common win)", blend.select("timestamp", "ret"))
        summarize("50/50 blend", blend.select("timestamp", "ret"))
        _ = m_a
    else:
        print("43b SCREENED OUT (corr >= 0.30) — no trial consumed")

    # ---------- 43c ----------
    if abs(c_a) < SCREEN_BAR and abs(c_c) < SCREEN_BAR and abs(c_d) < SCREEN_BAR:
        print("=== 43c: triple blend (FIRED) ===")
        # constructed only if all pairs admitted; see doc for spec
    else:
        print("43c SCREENED OUT (needs all three pairs < 0.30) — no trial consumed")


if __name__ == "__main__":
    main()
