"""Strategy-grade studies: FU-B1 (blend-V1), H41 (combined book), H42 (stops).

    .venv/Scripts/python scripts/h41_h42_fub1_studies.py

Pre-registered in docs/hypotheses/33-40-timeseries-batch.md (FU-B1),
docs/hypotheses/41-combined-book.md and docs/hypotheses/42-stop-overlay.md.
All comparisons are same-window/same-engine/same-costs vs the DEPLOYED spec.
"""

from __future__ import annotations

import contextlib
import json
import statistics
from datetime import timedelta
from pathlib import Path

import polars as pl

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from martex_quant.backtesting.research import walk_forward_backtest
from martex_quant.backtesting.walkforward import walk_forward_windows
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.risk_management.prop_sim import PropFirmRules, simulate_evaluation
from martex_quant.strategies.blend import BlendMomentum
from martex_quant.strategies.rotation import VolTargetRotation
from martex_quant.strategies.stops import StopVolTargetMomentum, StopVolTargetRotation
from martex_quant.strategies.vol_target import VolTargetMomentum

LEGACY8 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
TRAIN, TEST = 365, 90
V1_GRID = [7, 14, 30, 60, 90, 180]
ROT_GRID = [30, 90]
N_TRIALS = 104
BOUNCE_COST_RT = 0.0022  # H22's round-trip cost on the one-day bounce trade
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 51.80, static_max_loss_pct=0.06
)
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)
CACHE_DIR = Path("data/tmp/h4x_streams")


def cached(name: str, build) -> pl.DataFrame:  # noqa: ANN001
    """Persist expensive walk-forward streams so a failed section can be
    re-run without recomputing the earlier ones (deterministic builds)."""
    path = CACHE_DIR / f"{name}.parquet"
    if path.exists():
        print(f"  (cached: {name})")
        return pl.read_parquet(path)
    df = build()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    return df


def slice_frames(frames: dict[str, pl.DataFrame], start, end) -> dict[str, pl.DataFrame]:  # noqa: ANN001
    out = {}
    for s, df in frames.items():
        part = df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        if part.height > 30:
            out[s] = part
    return out


def rotation_wf_stream(frames: dict[str, pl.DataFrame], factory) -> pl.DataFrame:  # noqa: ANN001
    """Champion walk-forward protocol; returns stitched timestamp/equity/exposure."""
    master = frames["BTCUSDT"]["timestamp"].to_list()
    stitched = []
    level = 10_000.0
    for w in walk_forward_windows(len(master), TRAIN, TEST):
        t0 = master[w.train_start]
        t1 = master[w.train_end - 1] + timedelta(days=1)
        t2 = master[w.test_end - 1] + timedelta(days=1)
        best_param, best_sharpe = ROT_GRID[0], float("-inf")
        for lookback in ROT_GRID:
            train = run_multi_backtest(
                slice_frames(frames, t0, t1),
                factory(lookback),
                config=CONFIG,
                warmup_bars=max(lookback, 30) + 1,
            )
            if train.equity_curve.height < 30:
                continue
            sharpe = compute_metrics(train.equity_curve, [], Interval.D1).sharpe
            if sharpe > best_sharpe:
                best_param, best_sharpe = lookback, sharpe
        warm = t1 - timedelta(days=max(best_param, 30) + 11)
        test = run_multi_backtest(
            slice_frames(frames, warm, t2),
            factory(best_param),
            config=CONFIG,
            warmup_bars=max(best_param, 30) + 1,
        )
        curve = test.equity_curve.filter(pl.col("timestamp") >= t1)
        if curve.height == 0:
            continue
        first, last = curve["equity"][0], curve["equity"][-1]
        stitched.append(curve.with_columns(pl.col("equity") * (level / first)))
        level *= last / first
    return pl.concat(stitched)


def v1_wf_stream(frames: dict[str, pl.DataFrame], factory) -> pl.DataFrame:  # noqa: ANN001
    """V1 protocol: per-symbol walk-forward, EW-8 portfolio daily returns."""
    per_symbol = []
    for symbol in LEGACY8:
        outcome = walk_forward_backtest(
            frames[symbol],
            symbol,
            Interval.D1,
            V1_GRID,
            factory,
            lambda p: max(int(p), 30) + 1,
            TRAIN,
            TEST,
            config=BacktestConfig(initial_cash=10_000.0),
        )
        per_symbol.append(
            outcome.oos_equity.select(
                "timestamp", pl.col("equity").pct_change().fill_null(0.0).alias(symbol)
            )
        )
    wide = per_symbol[0]
    for part in per_symbol[1:]:
        wide = wide.join(part, on="timestamp", how="inner")
    return wide.select("timestamp", pl.mean_horizontal([pl.col(s) for s in LEGACY8]).alias("ret"))


def summarize(name: str, rets: pl.DataFrame, scale: float) -> dict[str, float]:
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
        f"  {name:<24} {rets.height}d  Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
        f"MDD {m.max_drawdown_pct:.1f}%  prop@{scale}x {r.pass_rate:.1%} "
        f"(median {r.median_days_to_pass}d)"
    )
    return {"sharpe": m.sharpe, "mdd": m.max_drawdown_pct, "pass": r.pass_rate}


def dsr_of(rets: pl.Series, n_obs: int, other_pp: float) -> float:
    pp = (rets.mean() or 0.0) / (rets.std() or 1.0)
    skew, kurt = rets.skew(), rets.kurtosis()
    return probabilistic_sharpe_ratio(
        pp,
        n_obs=n_obs,
        skew=skew if isinstance(skew, float) else 0.0,
        kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
        benchmark_sharpe=expected_max_sharpe(N_TRIALS, statistics.variance([pp, other_pp])),
    )


def pp_of(rets: pl.Series) -> float:
    return (rets.mean() or 0.0) / (rets.std() or 1.0)


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    wide_frames = {}
    for symbol in universe:
        with contextlib.suppress(FileNotFoundError):
            wide_frames[symbol] = store.read(symbol, Interval.D1)
    legacy_frames = {s: store.read(s, Interval.D1) for s in LEGACY8}
    print(f"universe: {len(wide_frames)} symbols; legacy 8 loaded\n")

    # ---------- FU-B1: blend-V1 vs V1 (8 majors) ----------
    print("=== FU-B1: multi-horizon blend vs V1 (identical protocol) ===")
    v1 = cached(
        "v1_stream",
        lambda: v1_wf_stream(legacy_frames, lambda p: VolTargetMomentum(int(p))),
    )

    def build_blend() -> pl.DataFrame:
        parts = []
        for symbol in LEGACY8:
            result = run_backtest(
                legacy_frames[symbol],
                symbol,
                BlendMomentum(),
                config=BacktestConfig(initial_cash=10_000.0),
                warmup_bars=181,
            )
            parts.append(
                result.equity_curve.select(
                    "timestamp", pl.col("equity").pct_change().fill_null(0.0).alias(symbol)
                )
            )
        joined = parts[0]
        for part in parts[1:]:
            joined = joined.join(part, on="timestamp", how="inner")
        return joined.select(
            "timestamp", pl.mean_horizontal([pl.col(s) for s in LEGACY8]).alias("ret")
        )

    blend = cached("blend_stream", build_blend)
    common = v1.join(blend, on="timestamp", how="inner", suffix="_b").sort("timestamp")
    v1_c = common.select("timestamp", "ret")
    blend_c = common.select("timestamp", pl.col("ret_b").alias("ret"))
    m_v1 = summarize("V1 (deployed)", v1_c, 1.5)
    m_blend = summarize("blend-V1", blend_c, 1.5)
    dsr = dsr_of(blend_c["ret"], blend_c.height, pp_of(v1_c["ret"]))
    bar1 = m_blend["sharpe"] > m_v1["sharpe"]
    bar2 = m_blend["pass"] > 0.50
    print(f"  blend DSR({N_TRIALS}): {dsr:.3f}")
    print(
        f"  FU-B1 VERDICT: bar1 Sharpe>{m_v1['sharpe']:.2f} {'PASS' if bar1 else 'fail'}; "
        f"bar2 prop@1.5x>50.0% {'PASS' if bar2 else 'fail'} -> "
        f"{'CANDIDATE' if bar1 and bar2 else 'KILLED'}\n"
    )

    # ---------- H42a: V1 + chandelier stop ----------
    print("=== H42a: V1 + stop vs V1 (identical protocol) ===")
    v1s = cached(
        "v1_stop_stream",
        lambda: v1_wf_stream(legacy_frames, lambda p: StopVolTargetMomentum(int(p))),
    )
    common = v1.join(v1s, on="timestamp", how="inner", suffix="_s").sort("timestamp")
    v1_c = common.select("timestamp", "ret")
    v1s_c = common.select("timestamp", pl.col("ret_s").alias("ret"))
    m_v1 = summarize("V1 (deployed)", v1_c, 1.5)
    m_v1s = summarize("V1 + stop", v1s_c, 1.5)
    dsr = dsr_of(v1s_c["ret"], v1s_c.height, pp_of(v1_c["ret"]))
    bar1 = m_v1s["sharpe"] > m_v1["sharpe"]
    bar2 = m_v1s["pass"] > m_v1["pass"]
    print(f"  V1+stop DSR({N_TRIALS}): {dsr:.3f}")
    print(
        f"  H42a VERDICT: bar1 Sharpe {'PASS' if bar1 else 'fail'}; "
        f"bar2 prop@1.5x {'PASS' if bar2 else 'fail'} -> "
        f"{'CANDIDATE' if bar1 and bar2 else 'KILLED'}\n"
    )

    # ---------- champion rotation stream (shared by H41 and H42b) ----------
    print("=== champion rotation stream (wide, walk-forward) ===")
    rot = cached(
        "rot_champion_stream",
        lambda: rotation_wf_stream(wide_frames, lambda lb: VolTargetRotation(lb, top_k=2)),
    )
    rot_rets = rot.select(
        "timestamp",
        pl.col("equity").pct_change().fill_null(0.0).alias("ret"),
        "exposure",
    )
    summarize("rotation (champion)", rot_rets.select("timestamp", "ret"), 0.5)

    # ---------- H42b: rotation + stop ----------
    print("\n=== H42b: rotation + stop vs champion ===")
    rots = cached(
        "rot_stop_stream",
        lambda: rotation_wf_stream(wide_frames, lambda lb: StopVolTargetRotation(lb, top_k=2)),
    )
    rots_rets = rots.select("timestamp", pl.col("equity").pct_change().fill_null(0.0).alias("ret"))
    common = rot_rets.join(rots_rets, on="timestamp", how="inner", suffix="_s").sort("timestamp")
    rot_c = common.select("timestamp", "ret")
    rots_c = common.select("timestamp", pl.col("ret_s").alias("ret"))
    m_rot_c = summarize("rotation (common win)", rot_c, 0.5)
    m_rots = summarize("rotation + stop", rots_c, 0.5)
    dsr = dsr_of(rots_c["ret"], rots_c.height, pp_of(rot_c["ret"]))
    bar1 = m_rots["sharpe"] > m_rot_c["sharpe"]
    bar2 = m_rots["pass"] > m_rot_c["pass"]
    print(f"  rotation+stop DSR({N_TRIALS}): {dsr:.3f}")
    print(
        f"  H42b VERDICT: bar1 Sharpe {'PASS' if bar1 else 'fail'}; "
        f"bar2 prop@0.5x {'PASS' if bar2 else 'fail'} -> "
        f"{'CANDIDATE' if bar1 and bar2 else 'KILLED'}\n"
    )

    # ---------- H41: rotation + crash-bounce overlay ----------
    print("=== H41: rotation + crash-bounce combined book ===")
    ts_dtype = rot_rets.schema["timestamp"]
    btc_ret = (
        wide_frames["BTCUSDT"]
        .sort("timestamp")
        .select(
            pl.col("timestamp").cast(ts_dtype),
            (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("btc_ret"),
        )
    )
    alt_parts = []
    for s, df in wide_frames.items():
        if s == "BTCUSDT":
            continue
        alt_parts.append(
            df.sort("timestamp").select(
                pl.col("timestamp").cast(ts_dtype),
                (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("aret"),
            )
        )
    alt_ew = (
        pl.concat(alt_parts)
        .drop_nulls()
        .group_by("timestamp")
        .agg(pl.col("aret").mean().alias("alt_ew_ret"))
        .sort("timestamp")
    )
    book = (
        rot_rets.join(btc_ret, on="timestamp", how="left")
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
        .with_columns(combined=pl.col("ret") + pl.col("overlay_ret"))
    )
    n_trig = book.filter(pl.col("trigger_prev")).height
    corr = book.select(pl.corr("ret", "overlay_ret")).item()
    mean_idle = book.filter(pl.col("trigger_prev"))["idle_prev"].mean()
    print(
        f"  bounce days in OOS window: {n_trig}; mean idle cash deployed "
        f"{(mean_idle or 0.0):.0%}; corr(rotation, overlay) {corr:.3f}"
    )
    m_rot2 = summarize("rotation alone", book.select("timestamp", "ret"), 0.5)
    m_comb = summarize(
        "combined book", book.select("timestamp", pl.col("combined").alias("ret")), 0.5
    )
    dsr = dsr_of(book["combined"], book.height, pp_of(book["ret"]))
    bar1 = m_comb["sharpe"] > m_rot2["sharpe"]
    bar2 = m_comb["pass"] > m_rot2["pass"]
    bar3 = m_comb["mdd"] >= m_rot2["mdd"] - 5.0
    print(f"  combined DSR({N_TRIALS}): {dsr:.3f}")
    print(
        f"  H41 VERDICT: bar1 Sharpe {'PASS' if bar1 else 'fail'}; "
        f"bar2 prop@0.5x {'PASS' if bar2 else 'fail'}; "
        f"bar3 MDD within 5pts {'PASS' if bar3 else 'fail'} -> "
        f"{'ELIGIBLE (runbook engine candidate)' if bar1 and bar2 and bar3 else 'NOT eligible'}"
    )


if __name__ == "__main__":
    main()
