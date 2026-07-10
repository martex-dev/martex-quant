# Trading Bot — Quantitative Research Platform

A professional-grade algorithmic trading research platform, built incrementally.
Current phase: **Phase 1 — Validated Data Foundation**.

The goal is not a profitable-looking backtest. The goal is infrastructure rigorous
enough to distinguish a real trading edge from noise — and to say "no edge found"
honestly when that is the answer.

## Current scope (Milestone 1)

- Binance OHLCV collector (via ccxt)
- Data validation pipeline (gaps, duplicates, OHLC coherence, outliers)
- Parquet data lake with a dataset catalog
- Data-quality report command

Target deliverable:

```
python -m trading_bot.data.pull --symbol BTCUSDT --interval 1h --years 4
```

produces validated, gap-audited Parquet plus a quality report.

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

CI runs all three on every push.

## Layout

```
src/trading_bot/    # the package (src layout: tests run against the installed package)
  data/
    collectors/     # exchange adapters behind a common interface
    processors/     # validation — reports problems, never silently repairs
    store/          # Parquet lake + catalog
tests/
data/lake/          # market data (gitignored; regenerable from exchanges)
```

## Roadmap

1. **Data foundation** ← current
2. Event-driven backtesting engine
3. Strategy research (hypothesis-first, walk-forward validated)
4. Risk engine & prop-firm rule simulation
5. Paper trading

See `CLAUDE.md` for the full project charter and engineering rules.
