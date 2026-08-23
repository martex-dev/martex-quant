# Trading Bot — Quantitative Research Platform

A professional-grade algorithmic trading research platform for crypto markets,
built incrementally, hypothesis-first, with statistical validation at every
gate.

The goal was never a good-looking backtest. The goal is infrastructure
rigorous enough to distinguish a real trading edge from noise — and to say
"no edge found" honestly when that's the answer. Most tested ideas here were
killed. That's the process working, not failing.

**Current phase: Phase 5 — paper trading, moving toward a live funded-account
evaluation.**

## Where the project stands

- **120 hypotheses pre-registered and tested** (119 run, 1 data-blocked),
  every one committed to a written spec *before* results — no retroactively
  deciding what counts. Every trial, including failed variants, stays in the
  ledger permanently; the statistical bar is benchmarked against all of them,
  not just the survivors.
- **2 strategies validated** above the project's absolute statistical bar
  (deflated Sharpe ratio > 0.95):
  - **Cross-sectional rotation** across a 40-coin universe (DSR 0.990) — got
    *stronger*, not weaker, as the universe widened.
  - **Rotation + chandelier stop** (DSR 0.992) — beats the base rotation
    strategy on every metric: Sharpe 1.47 vs 1.10, max drawdown -29% vs -58%,
    prop-firm pass probability 73% vs 63%.
- **~200 automated tests**, strict mypy, ruff-clean, CI green on every push.
- **4 live paper-trading accounts** ($5,000 each), running nightly and
  unattended via a scheduled task, each writing its own equity curve, trade
  journal, and plain-English daily diary.
- A real funded-account evaluation attempt is priced, planned, and gated on
  a clean paper-trading shakedown — sized using Monte Carlo simulation
  against the firm's actual rule set, not guesswork.

Along the way the research also mapped real market structure: crypto trends
at daily-and-slower horizons but reverts intraday, and that intraday
reversion is real but smaller than retail execution costs — confirmed four
independent ways. Full detail, every hypothesis, every verdict, and the
reasoning behind each: [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md). What's
running right now and what happens next: [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Architecture

Event-driven core (structurally incapable of look-ahead bias) with a
vectorized layer for cheap hypothesis screening; anything that survives
screening must also pass the event-driven engine before being trusted.
Backtest and live share the same strategy/portfolio/risk code paths and
differ only in the data feed and execution adapter — the standard defense
against "worked in backtest, died live."

```
src/trading_bot/
  data/
    collectors/       # exchange adapters (ccxt) behind a common interface
    processors/        # validation — reports problems, never silently repairs
    store/              # Parquet lake + catalog
  strategies/          # pure functions: market state -> signals (no orders, no sizing)
  backtesting/         # event-driven engine, vectorized screener, walk-forward harness
  risk_management/     # sizing policy, drawdown/daily-loss tracking, kill switch
  execution/           # simulated fills + live broker adapters
live/                  # decision core shared by paper + live, broker adapters, guard
docs/
  hypotheses/          # one numbered, pre-registered doc per hypothesis
  research/            # eval runbook, sprint plans, backlog
data/                  # market data + paper trading records (gitignored, regenerable)
tests/
```

## Setup

Requires Python 3.12+.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
pip install -r requirements-dev.txt
```

## Development

```
pytest              # run tests
ruff check .        # lint
ruff format .       # format
mypy                # type check
```

CI runs all three on every push. Every session runs this full check before
committing.

## Research process

1. **Pre-register** — numbered hypothesis doc with verdict bars, committed
   before any test runs.
2. **Kill test** — cheap information study before any strategy is built.
3. **Event-driven validation** — the engine is the source of truth; vectorized
   screening is pre-engine only.
4. **Beat the deployed system, not zero** — new features must improve on
   what's already validated.
5. **Report negative results with the same rigor as positive ones** — the
   ledger's honesty is the project's only real asset.

## Roadmap

1. Data foundation — done (48 validated datasets, 0 errors)
2. Event-driven backtesting engine — done
3. Strategy research — done for this cycle (120 hypotheses, 2 validated)
4. Risk engine & prop-firm rule simulation — done
5. Paper trading — **in progress** (Phase 5, shakedown before live eval)
6. Live funded-account evaluation — next

See [`CLAUDE.md`](CLAUDE.md) for the full project charter and engineering
rules.
