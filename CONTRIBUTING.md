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

Bars are never renegotiated downward once results exist.

## How trials are counted

The statistical bar for any new result is deflated against the *total*
number of trials ever run — currently 125, of which 2 survived. That
arithmetic only works if the count is honest, so:

- **Every evaluated candidate is a trial.** Variants, descriptive horizons,
  and cells inside an automated sweep that nobody read. There is no "I only
  looked at three of them" exemption.
- **Selection consumes trials; description does not.** A sweep that
  publishes its whole surface and picks no winner costs nothing. The moment
  a winner is chosen on a metric and carried forward as a claim, every cell
  it beat has entered the selection set.
- **An equal-weight or no-fitting baseline is mandatory** in any
  model-based hypothesis. This is not a formality — it has already won
  once, decisively (see `docs/hypotheses/58-learned-indicator-ensemble.md`).
- **Do not re-test a killed idea** without a new pre-registered spec and a
  stated reason for revisiting it.

If you are proposing research work, open an issue or a proposal document
and get a written decision **before** writing code. A worked example of a
proposal and the response to it is in
`docs/research/bounded-search-proposal-response.md`.

## Reporting a negative result

Negative results are as welcome as positive ones and are reviewed the same
way. Most hypotheses in this ledger were killed. If you test something and it
fails, that is a contribution — open the PR.

Never delete a trial from the ledger because it failed. Removing failures
inflates every subsequent finding.

## Where contributions are easiest to accept

Engineering work carries none of the research overhead above and is
genuinely wanted:

- Dashboard, CLI, and packaging fixes
- CI, typing, and test-infrastructure improvements
- Performance work on the engine and data layer
- Documentation, examples, and developer experience
- Bug fixes with a regression test

## Development setup

Python 3.12. From a clean checkout:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e .
```

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

On Linux/macOS the interpreter is `.venv/bin/python`.

The optional `research` extra pulls in scikit-learn and tensorflow-cpu. It
is only needed for the H58 ensemble and TSLA CNN modules, which skip
without it:

```bash
.venv/Scripts/python -m pip install -e ".[research]"
```

## Before you open a pull request

All four must pass. CI runs the same commands on every push.

```bash
.venv/Scripts/python -m pytest
```

```bash
.venv/Scripts/python -m ruff check .
```

```bash
.venv/Scripts/python -m ruff format --check .
```

```bash
.venv/Scripts/python -m mypy
```

## Two things that will bite you

**Line endings.** This repository stores CRLF, and the golden-baseline tests
fingerprint their inputs **byte for byte** — a checkout that converts line
endings changes every hash and every byte count, and those tests then fail
for reasons unrelated to your change. Do not "fix" line endings across
files. If the golden tests fail and you did not touch the research corpus,
check this first.

Those tests skip automatically on CI runners because they need the local
data lake.

**Data.** The Parquet lake under `data/` is not in the repository. Tests
that need it skip. If your change depends on real market data, say so in the
PR — it cannot be verified by CI alone and will need a local run.

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

## Pull requests

- **Branch from `main`, one concern per PR.** Small and reviewable beats
  complete and sprawling.
- **Say what you verified**, not just what you changed. "Tests pass" is
  weaker than "added a regression test that fails on the old code."
- **`main` is protected.** Every PR needs CI green and an approving review
  from the code owner before merge. This applies to everyone; it is process,
  not distrust.
- **Check `.github/CODEOWNERS` before you start.** It lists the paths
  covering the ledger, the reproducibility gates, and the capital path.
  Avoid them unless the PR is specifically about them.
- **Config changes affecting a running paper account** archive that
  account's record and restart it from a fresh $5,000. One spec per record —
  flag any such change explicitly.

## Adding a strategy

Implement `Strategy` in `src/martex_quant/strategies/`, add unit tests with
synthetic data, and register it in the CLI's strategy tables if it should be
runnable from the command line. Then pre-register a hypothesis and test it
properly.

## What will be rejected

- Results without costs.
- Strategies without a market hypothesis — a reason the edge should exist,
  and the conditions under which it should fail.
- Parameter sweeps presented as validation.
- Removing or weakening the live-trading gates.
- Anything that makes a return figure look better without making it truer.
- Committed secrets, API keys, or account data. `config/secrets/` is never
  tracked.
- Live-trading or order-placement changes from outside contributors. The
  path from research to real money is a deliberate, human-gated CLI step and
  stays that way.

Nothing in this repository is financial advice, and no PR should frame it
as such.

## Bugs and questions

Open an issue. If you have found a bug that makes a published result wrong,
say so directly — a correction to the ledger is more valuable than a new
feature.

If you are unsure whether something counts as research work, ask before
running it rather than after. The answer is cheap in advance and expensive
afterwards.
