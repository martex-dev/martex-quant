# Trading Bot — Quantitative Research Platform

[![CI](https://github.com/MartexHACK/trading-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/MartexHACK/trading-bot/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A platform for testing trading hypotheses honestly: a validated data
pipeline, an event-driven backtester, real statistical validation, Monte
Carlo simulation against prop-firm rule sets, paper trading, and an
operations dashboard.

**It is not a profitable trading bot, and it does not pretend to be one.**
It ships with the full research ledger behind it — 125 pre-registered trials
across 120 hypotheses — and most of them were killed. That ledger is the
product. The tooling exists to produce more of it.

> Research software. Not financial advice. No strategy here is proven
> profitable with real money. Read [DISCLAIMER.md](DISCLAIMER.md) before
> connecting this to anything that holds money.

---

## Install

```bash
pip install martex-quant
```

```bash
martex-quant init my-lab
cd my-lab
martex-quant quickstart
```

`quickstart` downloads real market data, walk-forward backtests it with fees,
spread, and slippage included, and then explains why the number it just
printed is not evidence of an edge.

Python 3.12+. Full instructions, including installing a downloaded `.whl` and
troubleshooting: [docs/INSTALL.md](docs/INSTALL.md).

## What you can do with it

| Command | What it does |
|---|---|
| `martex-quant doctor` | Check the install, dependencies, corpus, and workspace |
| `martex-quant quickstart` | Guided first run: pull data, backtest it, read the result |
| `martex-quant data pull` | Download, **validate**, and store OHLCV history |
| `martex-quant backtest` | Walk-forward backtest, out of sample, costs included |
| `martex-quant montecarlo` | Prop-firm evaluation pass odds, with confidence intervals |
| `martex-quant paper` | One forward-testing day on a simulated $5,000 account |
| `martex-quant dashboard` | Equity curves, trade journals, daily diaries, the Lab |
| `martex-quant ledger` | Every trial ever run, and its verdict |

Full reference: [docs/USAGE.md](docs/USAGE.md).

## Why this exists

The base rate for retail algorithmic trading is poor. Most edges reachable
with public data and one developer's compute are gone. So the goal was never
a good-looking backtest — it was infrastructure rigorous enough to tell a
real edge from noise, and to say *"no edge found"* out loud when that is the
answer.

Concretely, that means:

- **Pre-registration.** Every hypothesis is a numbered document with its
  pass/fail bars, committed *before* the test runs. Deciding what counts as
  success after seeing results is how most retail backtests fool their
  authors, and the commit timestamp is the only defense.
- **Every trial counts, forever.** Failed variants stay in the ledger. The
  statistical bar (deflated Sharpe ratio) is benchmarked against *all* trials
  ever run, not just the survivors — so the graveyard is load-bearing
  evidence, not an embarrassment.
- **Costs are never optional.** Fees, spread, and slippage are inside every
  result.
- **The event-driven engine is the source of truth.** It processes one
  timestamp at a time through the same code path as live trading, which makes
  look-ahead leakage structurally impossible. Vectorized screening is for
  cheap pre-filtering only.
- **Negative results are reported with the same rigor as positive ones.**

## What the research found

- **125 trials across 120 hypotheses**, 124 run, 1 data-blocked. Kill rate
  37%.
- **2 strategies cleared the bar** (deflated Sharpe > 0.95):
  - Cross-sectional rotation across a 40-coin universe (DSR 0.990) — which
    got *stronger*, not weaker, as the universe widened.
  - Rotation with a chandelier stop (DSR 0.992) — better on every metric:
    Sharpe 1.47 vs 1.10, max drawdown −29% vs −58%, simulated prop-firm pass
    probability 73% vs 63%.
- **Market structure worth knowing:** crypto trends at daily-and-slower
  horizons but reverts intraday — and that intraday reversion is real but
  *smaller than retail execution costs*, confirmed four independent ways.
- Neither validated strategy has been proven profitable with real capital.
  Paper trading exists precisely to measure the gap between backtest and
  live.

Every hypothesis, verdict, and the reasoning behind it:
[`PROJECT_MEMORY.md`](PROJECT_MEMORY.md). What is running right now:
[`PROJECT_STATE.md`](PROJECT_STATE.md). Or just run `martex-quant ledger`.

## Architecture

Event-driven core with a vectorized research layer. Backtest and live share
the same strategy, portfolio, and risk code paths and differ only in the data
feed and the execution adapter — the standard defense against "worked in
backtest, died live."

```
src/trading_bot/
  cli.py               the `martex-quant` command
  data/
    collectors/        exchange adapters (ccxt) behind a common interface
    processors/        validation — reports problems, never silently repairs
    store/             Parquet lake + catalog
  strategies/          pure functions: market history -> exposure in [-1, +1]
  backtesting/         event-driven engine, screener, walk-forward harness
  stats/               deflated Sharpe, bootstrap, multiple-testing correction
  risk_management/     sizing policy, drawdown tracking, kill switch, prop sim
  execution/           simulated fills + live broker adapters
  live/                decision core shared by paper and live, guard, narration
  research/            the hypothesis ledger and its query layer
  dashboard/           local operations view
docs/
  hypotheses/          one pre-registered document per hypothesis
  research/            the trial ledger, evaluation runbook, design notes
```

A strategy never touches orders or sizing. It emits a target exposure;
portfolio and risk layers translate that into orders, and risk has veto power
over every one of them. That is what makes strategies unit-testable and the
risk layer un-bypassable.

## Development

```bash
git clone https://github.com/MartexHACK/trading-bot.git
cd trading-bot
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -e .
pip install -r requirements-dev.txt
```

Then run the checks, one per line rather than chained with `&&` — Windows
PowerShell has no `&&` operator, and chaining there is a parser error that
runs none of them:

```
pytest
ruff check .
mypy
```

560+ tests, strict mypy, ruff-clean, CI green on every push.

Contributions welcome — but read [CONTRIBUTING.md](CONTRIBUTING.md) first.
The pre-registration rule applies to pull requests too.

## Real money

Live execution is not reachable from this CLI, is never a dashboard button,
requires your own broker credentials and a deliberate command-line action,
and sits behind a risk guard whose KILLED latch only a human can clear. Those
gates are deliberate. Please leave them there.

## License

MIT — see [LICENSE](LICENSE). Provided with no warranty of any kind. Read
[DISCLAIMER.md](DISCLAIMER.md).

See [`CLAUDE.md`](CLAUDE.md) for the full project charter and engineering
rules.

---

*The project leans heavily on Claude Code (Fable 5) — largely vibe-coded with
light human supervision. Stating that plainly, as a disclaimer. It still runs
smoothly: the suite is green in CI, and the dashboard is live and updating
daily at 8:10 PM EST.* — Martex
