# Contributing

Contributions are welcome. This project has unusual rules, though, and they
are not negotiable — they are the only reason its research record is worth
anything. Please read this before opening a pull request.

## The one rule that matters

**Pre-register every hypothesis before you test it.**

A numbered document in `docs/hypotheses/`, stating what you predict, what
data you will use, and the exact bars that decide pass or fail — committed
*before* any test runs. Not after. Not "I'll write it up once it works."

This is not bureaucracy. Deciding what counts as success after seeing the
results is how almost every retail backtest fools its author, and it is
undetectable in review. The commit timestamp is the evidence.

A pull request with a new strategy and no pre-registered hypothesis will be
asked for the hypothesis first, however good the numbers look.

## Reporting a negative result

Negative results are as welcome as positive ones and are reviewed the same
way. Most hypotheses in this ledger were killed. If you test something and it
fails, that is a contribution — open the PR.

Never delete a trial from the ledger because it failed. Every trial ever run
stays, because the statistical bar for any new result is deflated against the
*total* number of trials. Removing failures inflates every subsequent
finding.

## Before you open a pull request

```bash
pytest              # tests
ruff check .        # lint
ruff format .       # format
mypy                # strict type check
```

CI runs all four on every push. All must be green.

## Engineering rules

- **Strategies never touch orders or sizing.** A strategy maps market history
  to a target exposure in `[-1, +1]`. Portfolio and risk layers turn that
  into orders. This keeps strategies unit-testable and the risk layer
  un-bypassable.
- **The event-driven engine is the source of truth.** Vectorized screening is
  for cheap pre-engine filtering only; anything that survives screening must
  pass the engine before it is trusted.
- **New features must beat the deployed system**, not zero.
- **Costs are never optional.** Fees, spread, and slippage go into every
  result. A backtest without them is not a result.
- Python 3.12, type hints everywhere, stdlib-first — new dependencies need a
  reason.
- Keep components independent and files small.

## What will be rejected

- Results without costs.
- Strategies without a market hypothesis — a reason the edge should exist,
  and the conditions under which it should fail.
- Parameter sweeps presented as validation.
- Removing or weakening the live-trading gates.
- Anything that makes a return figure look better without making it truer.

## Adding a strategy

Implement `Strategy` in `src/trading_bot/strategies/`, add unit tests with
synthetic data, and register it in the CLI's strategy tables if it should be
runnable from the command line. Then pre-register a hypothesis and test it
properly.

## Bugs and questions

Open an issue. If you have found a bug that makes a published result wrong,
say so directly — a correction to the ledger is more valuable than a new
feature.
