# Phase 3 Verdict — Strategy Research Conclusion (2026-07-11)

Data: 8 USDT majors, 4y Binance spot OHLCV (1h + 1d), full cost model
(10 bps taker, 1 bp half-spread, volume-impact slippage, one-bar latency).
Every hypothesis pre-registered its verdict standard before results.
Total trials across Phase 3: **23** (6 hourly TSMOM + 6 daily TSMOM +
6 vol-filtered + 4 mean-reversion band widths + 1 portfolio aggregation).

## Scoreboard

| # | Hypothesis | Verdict | Median DSR | Beat B&H (Sharpe) |
|---|---|---|---|---|
| 01 | TSMOM, 1h bars | REJECTED | 0.393 | 2/8 |
| 02 | TSMOM, 1d bars | **INCONCLUSIVE-POSITIVE → candidate** | 0.624 (0.828 as portfolio) | 6/8 |
| 03 | Vol-regime-gated TSMOM | REJECTED (worse than 02) | 0.495 | 1/8 |
| 04 | Mean reversion, 1h | REJECTED decisively | 0.092 | 0/8 |
| 05 | Carry (funding) | Feasibility CONFIRMED; build deferred post-Phase 4 | n/a | n/a |

## The chosen strategy

**Daily-bar time-series momentum, long/flat, equal-weight across the
8-symbol universe, with the lookback re-selected every 90 days by
walk-forward (1-year train, grid L ∈ {7,14,30,60,90,180} days).**

Out-of-sample over ~3 years, portfolio level: **Sharpe 0.87, +108%
total, max drawdown -44%, deflated-Sharpe probability 0.828** against
the expected-best of all 23 trials.

Why this exact spec and not a single fixed lookback: picking the best
fixed L from the robustness table (L=14, median Sharpe 0.74) would be
best-of-6 selection — precisely the trap the DSR machinery exists to
catch. The walk-forward protocol IS the strategy; its adaptive selection
was itself validated out-of-sample.

## What this is NOT

DSR 0.828 means roughly a 17% probability this is selection luck, not
skill — above any deploy-real-money threshold this project will accept
(0.95). The candidate is promoted for ENGINEERING purposes (Phase 4 risk
work needs a realistic strategy to wrap), not as a validated edge. The
-44% OOS drawdown is far outside funded-account constraints; unmanaged,
this strategy fails every prop-firm ruleset instantly — which is exactly
what Phase 4 exists to address (sizing, drawdown caps, kill switch), and
prop-firm evaluation EV will be computed then, not assumed.

## Cheapest paths to a sharper verdict (in order)

1. Extend daily history to 2017+ (Binance 1d goes back ~8-9 years for
   BTC/ETH) — roughly triples OOS sample; DSR verdict becomes real.
2. Widen the universe (more symbols = more diversification, more power).
3. Vol-targeted sizing as a new hypothesis (06) — likely bigger Sharpe
   lever than any signal tweak, and it attacks the -44% MDD directly.
4. Carry infrastructure (funding dataset + two-leg engine) — hypothesis
   05's premium is real and uncorrelated with momentum.
