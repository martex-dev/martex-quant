"""Phase 3 hypothesis studies. Reproducible:

    .venv/Scripts/python scripts/phase3_studies.py --study daily-tsmom
    .venv/Scripts/python scripts/phase3_studies.py --study vol-filter
    .venv/Scripts/python scripts/phase3_studies.py --study meanrev
    .venv/Scripts/python scripts/phase3_studies.py --study carry

Protocols pre-registered in docs/hypotheses/02..05. Study 1 (hourly TSMOM)
lives in scripts/tsmom_study.py.
"""

from __future__ import annotations

import argparse
import statistics
from collections.abc import Callable, Sequence
from pathlib import Path

import polars as pl

from trading_bot.backtesting.engine import BacktestConfig, run_backtest
from trading_bot.backtesting.metrics import (
    compute_metrics,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from trading_bot.backtesting.research import walk_forward_backtest
from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.strategies.base import Strategy
from trading_bot.strategies.benchmark import BuyAndHold
from trading_bot.strategies.meanrev import BollingerReversion
from trading_bot.strategies.momentum import TimeSeriesMomentum
from trading_bot.strategies.vol_filter import VolFilteredMomentum

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"]
CONFIG = BacktestConfig(initial_cash=10_000.0)
STORE = ParquetStore(Path("data/lake"))


def per_period_sharpe(equity: pl.Series) -> float:
    returns = equity.pct_change().drop_nulls()
    mean, std = returns.mean(), returns.std()
    if not isinstance(mean, float) or not isinstance(std, float) or std == 0.0:
        return 0.0
    return mean / std


def run_wf_study(
    interval: Interval,
    grid: Sequence[float],
    factory: Callable[[float], Strategy],
    warmup_of: Callable[[float], int],
    train: int,
    test: int,
) -> None:
    header = (
        f"{'symbol':<9} {'OOS ret':>9} {'OOS shp':>8} {'OOS MDD':>9} {'in mkt':>7} "
        f"{'B&H ret':>9} {'B&H shp':>8} {'B&H MDD':>9} {'DSR':>6}  chosen per window"
    )
    print(header)
    print("-" * len(header))
    dsrs = []
    beat = 0
    for symbol in SYMBOLS:
        df = STORE.read(symbol, interval)
        outcome = walk_forward_backtest(
            df, symbol, interval, grid, factory, warmup_of, train, test, config=CONFIG
        )
        oos = outcome.oos_equity
        m = compute_metrics(oos, [], interval)

        oos_start = oos["timestamp"][0]
        span = df.filter(pl.col("timestamp") >= oos_start)
        bh = run_backtest(span, symbol, BuyAndHold(), config=CONFIG)
        bh_m = compute_metrics(bh.equity_curve, bh.fills, interval)

        trial_sharpes = []
        for param in grid:
            fixed = run_backtest(
                df, symbol, factory(param), config=CONFIG, warmup_bars=warmup_of(param)
            )
            curve = fixed.equity_curve.filter(pl.col("timestamp") >= oos_start)
            trial_sharpes.append(per_period_sharpe(curve["equity"]))

        oos_returns = oos["equity"].pct_change().drop_nulls()
        skew = oos_returns.skew()
        kurt = oos_returns.kurtosis()
        dsr = probabilistic_sharpe_ratio(
            per_period_sharpe(oos["equity"]),
            n_obs=oos.height,
            skew=skew if isinstance(skew, float) else 0.0,
            kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
            benchmark_sharpe=expected_max_sharpe(len(grid), statistics.variance(trial_sharpes)),
        )
        dsrs.append(dsr)
        beat += m.sharpe > bh_m.sharpe

        chosen = ",".join(
            str(int(w.chosen_param) if w.chosen_param == int(w.chosen_param) else w.chosen_param)
            for w in outcome.windows
        )
        print(
            f"{symbol:<9} {m.total_return_pct:>8.1f}% {m.sharpe:>8.2f} "
            f"{m.max_drawdown_pct:>8.1f}% {m.time_in_market_pct:>6.1f}% "
            f"{bh_m.total_return_pct:>8.1f}% {bh_m.sharpe:>8.2f} "
            f"{bh_m.max_drawdown_pct:>8.1f}% {dsr:>6.3f}  {chosen}"
        )
    print(f"\n{beat}/{len(SYMBOLS)} beat B&H on Sharpe; median DSR = {statistics.median(dsrs):.3f}")


def study_daily_tsmom() -> None:
    print("Study 2 — daily TSMOM  grid=[7,14,30,60,90,180]d  train=365d test=90d\n")
    run_wf_study(
        Interval.D1,
        grid=[7, 14, 30, 60, 90, 180],
        factory=lambda p: TimeSeriesMomentum(int(p)),
        warmup_of=lambda p: int(p) + 1,
        train=365,
        test=90,
    )


def study_vol_filter() -> None:
    print("Study 3 — vol-filtered daily TSMOM  vol windows FIXED 30/90d\n")
    run_wf_study(
        Interval.D1,
        grid=[7, 14, 30, 60, 90, 180],
        factory=lambda p: VolFilteredMomentum(int(p)),
        warmup_of=lambda p: max(int(p), 90) + 1,
        train=365,
        test=90,
    )


def study_meanrev() -> None:
    print("Study 4 — 1h Bollinger reversion  window FIXED 168h  grid k=[1,1.5,2,2.5]\n")
    run_wf_study(
        Interval.H1,
        grid=[1.0, 1.5, 2.0, 2.5],
        factory=lambda p: BollingerReversion(band_k=p),
        warmup_of=lambda p: 168,
        train=8766,
        test=2160,
    )


def study_carry() -> None:
    """Data-only feasibility: measure the gross funding premium on Binance
    USDT-margined perps. No backtest — see hypothesis 05 for why."""
    import ccxt

    print("Study 5 — carry feasibility: Binance perp funding history\n")
    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    print(f"{'symbol':<16} {'records':>8} {'span':>22} {'mean 8h rate':>13} {'annualized':>11}")
    for base in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
        symbol = f"{base}/USDT:USDT"
        rates: list[float] = []
        first_ts = None
        last_ts = None
        since: int | None = None
        for _ in range(20):  # pages of 1000, oldest-first
            batch = exchange.fetch_funding_rate_history(symbol, since=since, limit=1000)
            if not batch:
                break
            rates.extend(float(r["fundingRate"]) for r in batch)
            if first_ts is None:
                first_ts = batch[0]["datetime"][:10]
            last_ts = batch[-1]["datetime"][:10]
            new_since = int(batch[-1]["timestamp"]) + 1
            if since is not None and new_since <= since:
                break
            since = new_since
            if len(batch) < 1000:
                break
        mean_rate = statistics.mean(rates)
        annualized = mean_rate * 3 * 365  # 8h funding, 3x daily
        print(
            f"{symbol:<16} {len(rates):>8} {first_ts} .. {last_ts} "
            f"{mean_rate * 100:>12.4f}% {annualized * 100:>10.2f}%"
        )
    print(
        "\nGROSS premium only: before fees on both legs, basis moves, margin"
        "\ncosts, and squeeze/liquidation tail risk. Decision bar: 5%/yr gross."
    )


STUDIES = {
    "daily-tsmom": study_daily_tsmom,
    "vol-filter": study_vol_filter,
    "meanrev": study_meanrev,
    "carry": study_carry,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", required=True, choices=[*STUDIES, "all"])
    args = parser.parse_args()
    if args.study == "all":
        for fn in STUDIES.values():
            print(f"\n{'=' * 100}\n")
            fn()
    else:
        STUDIES[args.study]()


if __name__ == "__main__":
    main()
