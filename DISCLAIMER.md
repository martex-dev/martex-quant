# Disclaimer

**This software is a research platform. It is not financial advice, and it is
not a money-making product.**

Read this before you install it, and read it again before you connect it to
anything that holds real money.

## What this is

A toolkit for *testing* trading hypotheses honestly: a data pipeline, an
event-driven backtester, statistical validation (deflated Sharpe ratio,
bootstrap, multiple-testing correction), Monte Carlo simulation against
prop-firm rule sets, and a paper-trading loop with a dashboard.

It ships with the author's own research ledger — 120 pre-registered
hypotheses and their verdicts. **Most of them were killed.** That ledger is
included as evidence of method, not as a catalogue of edges you can switch
on.

## What this is not

- It is **not** a profitable trading bot. Nothing in this repository is
  claimed to make money, and the two strategies that survived the author's
  statistical bar have *not* been proven profitable with real capital.
- It is **not** financial, investment, tax, or legal advice. The authors are
  not licensed advisors.
- It is **not** audited. There is no warranty of any kind (see `LICENSE`).

## Risk

Trading leveraged and crypto instruments can lose you more than you deposit.
Backtested and paper-traded results are **not** predictive of live results —
demonstrating that gap is one of the things this platform is built to
measure. Automated systems fail in ways manual trading does not: stale data
feeds, exchange outages, API changes, and bugs in code you did not read.

If you run this against real money, you do so entirely at your own risk, and
you are responsible for:

- verifying every strategy against your own research, not the author's ledger;
- complying with the rules of your exchange, broker, or prop firm (many
  prohibit automated trading — check before you pay any fee);
- complying with the law and tax rules of your jurisdiction.

## Live trading is gated on purpose

Real-money execution is never a dashboard button. It requires a deliberate
command-line action, a configured broker adapter with your own API keys, and
a risk guard whose KILLED latch only a human can clear. Please do not remove
those gates. They exist because the author needed them.

## API keys

Never commit API keys. `config/secrets/`, `*.key`, `*.pem`, and `.env` are
gitignored. Use exchange keys scoped to trading only — never with withdrawal
permission enabled.
