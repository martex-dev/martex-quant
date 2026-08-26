"""H51 strategy-grade study: intraday fade strategies (51a, 51b).

    .venv/Scripts/python scripts/h51_fade_study.py

Pre-registered in docs/hypotheses/51-intraday-fade.md. Event-driven
engine over 15m Bybit bars, TAKER-floor costs (fee 5.5bp + half-spread
0.5bp + impact 0.5bp per side); a cheaper maker-entry sensitivity run
(fee 2bp) is reported alongside. Portfolio: EW across symbols, 30% vol
target on trailing 30d, gross <= 1. Bars: net Sharpe > 0.7 AND corr vs
rotation-stop < 0.30, OR net Sharpe > 1.10.
"""

from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from martex_quant.backtesting.engine import BacktestConfig, run_backtest
from martex_quant.backtesting.metrics import compute_metrics
from martex_quant.data.models import Interval
from martex_quant.data.series.store import SeriesKind, SeriesStore
from martex_quant.execution.simulated import ExecutionConfig
from martex_quant.risk_management.prop_sim import PropFirmRules, simulate_evaluation
from martex_quant.strategies.base import Strategy
from martex_quant.strategies.fade import FadeFirstHour, FadeORB

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
TAKER = ExecutionConfig(fee_bps=5.5, half_spread_bps=0.5, impact_bps=0.5)
MAKER_IN = ExecutionConfig(fee_bps=2.0, half_spread_bps=0.5, impact_bps=0.5)
FIRM_RULES = PropFirmRules(
    "1step-5k-static", 5_000.0, 0.10, None, 0.03, None, 108.0, static_max_loss_pct=0.06
)
CACHE_DIR = Path("data/tmp/h4x_streams")
SERIES = SeriesStore(Path("."))
VOL_TARGET = 0.30


def daily_returns(symbol: str, strategy: Strategy, execution: ExecutionConfig) -> pl.DataFrame:
    df = pl.read_parquet(DATA / f"{symbol}_15m.parquet").rename({"ts": "timestamp"})
    result = run_backtest(
        df,
        symbol,
        strategy,
        config=BacktestConfig(initial_cash=10_000.0, allow_short=True, execution=execution),
        warmup_bars=1,
    )
    curve = result.equity_curve.with_columns(day=pl.col("timestamp").dt.date())
    eod = curve.group_by("day").agg(pl.col("equity").last()).sort("day")
    return eod.with_columns(pl.col("equity").pct_change().fill_null(0.0).alias(symbol)).select(
        "day", symbol
    )


def portfolio(name: str, factory, execution: ExecutionConfig) -> pl.DataFrame:  # noqa: ANN001
    parts = []
    for symbol in SYMBOLS:
        parts.append(
            daily_returns(symbol, factory(), execution)
            .rename({symbol: "r"})
            .with_columns(pl.lit(symbol).alias("s"))
        )
    ew = pl.concat(parts).group_by("day").agg(pl.col("r").mean().alias("ret")).sort("day")
    # 30% vol target on trailing 30d of the EW stream (shifted: no lookahead).
    ew = ew.with_columns(
        scale=(VOL_TARGET / (pl.col("ret").rolling_std(30).shift(1) * math.sqrt(365))).clip(
            0.0, 1.0
        )
    ).drop_nulls("scale")
    ew = ew.with_columns(sret=pl.col("ret") * pl.col("scale"))
    print(f"  built {name}: {ew.height} days")
    return ew.select("day", "sret")


def evaluate(name: str, ew: pl.DataFrame, rot_daily: pl.DataFrame) -> None:
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
    print(
        f"  {name:<28} {ew.height}d  Sharpe {m.sharpe:.2f}  CAGR {m.cagr_pct:+.1f}%  "
        f"MDD {m.max_drawdown_pct:.1f}%  corr(rot-stop) {corr:+.3f}"
    )
    for scale in (0.5, 1.0, 2.0, 4.0):
        r = simulate_evaluation(ew["sret"].to_list(), FIRM_RULES, scale, n_paths=20_000)
        print(f"    prop@{scale}x: pass {r.pass_rate:.1%} (median {r.median_days_to_pass}d)")
    bar = (m.sharpe > 0.7 and abs(corr) < 0.30) or m.sharpe > 1.10
    print(
        f"  VERDICT {name}: Sharpe {m.sharpe:.2f}, corr {corr:+.2f} -> "
        f"{'CANDIDATE (diversifier)' if bar else 'KILLED'}\n"
    )


def main() -> None:
    rot_stop = SERIES.read(SeriesKind.EQUITY_STREAM, "rot_stop_stream")
    rot_daily = rot_stop.with_columns(day=pl.col("timestamp").dt.date()).select(
        "day", pl.col("equity").pct_change().fill_null(0.0).alias("rot_ret")
    )
    for name, factory in (("51a fade-ORB", FadeORB), ("51b fade-first-hour", FadeFirstHour)):
        print(f"=== {name} (taker floor) ===")
        ew = portfolio(name, factory, TAKER)
        evaluate(name, ew, rot_daily)
        print(f"=== {name} (maker-entry sensitivity) ===")
        ew_m = portfolio(name, factory, MAKER_IN)
        evaluate(f"{name} maker", ew_m, rot_daily)


if __name__ == "__main__":
    main()
