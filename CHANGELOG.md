# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-08-26

First public release. The platform was already complete as research code;
this release makes it *installable software* rather than a repository you
have to reverse-engineer.

### Added

- **`tradingbot` command line interface** — one entry point for the whole
  platform: `init`, `doctor`, `quickstart`, `data pull`, `data status`,
  `backtest`, `montecarlo`, `paper`, `dashboard`, `ledger`.
- **Workspaces.** `tradingbot init my-lab` scaffolds a directory holding the
  data lake, paper-trading state, and the full research corpus. Commands
  resolve their workspace from `--workspace`, `$TRADING_BOT_HOME`, or the
  current directory, so an installed copy no longer has to be run from a git
  checkout.
- **The research corpus ships inside the package.** The 29 pre-registered
  hypothesis documents, the 125-trial ledger, the evaluation runbook, and the
  universe config are vendored into the wheel at build time, so
  `pip install trading-bot` carries the evidence, not just the code.
- **`tradingbot quickstart`** — a guided first run that pulls real data,
  walk-forward backtests it with costs, and explains why one good-looking
  backtest is not an edge.
- **`tradingbot ledger`** — browse every trial ever run, with verdicts, kill
  rate, and published deflated Sharpe ratios.
- **`tradingbot doctor`** — checks the install, dependencies, corpus, and
  workspace, and says exactly what to run next when something is missing.
- `LICENSE` (MIT) and `DISCLAIMER.md`, `docs/INSTALL.md`, `docs/USAGE.md`,
  `CONTRIBUTING.md`, `SECURITY.md`.
- Release automation: tagging `v*` builds an sdist and wheel, attaches them
  to a GitHub Release, and (once enabled) publishes to PyPI via trusted
  publishing.
- Cross-platform launchers under `scripts/` replacing the hardcoded Windows
  paths, plus scheduling instructions for Linux and macOS.

### Changed

- Version moves from `0.1.0` to `1.0.0`, and is now read from installed
  package metadata rather than duplicated in source.
- `README.md` rewritten for people who have not read the ledger: what this
  is, what it honestly is not, and how to run it in three commands.

### Notes

Nothing in this release changes a single research verdict, strategy, cost
model, or statistic. The ledger is untouched. This is packaging.
