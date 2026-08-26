# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-08-26

### Changed

- **Renamed the project to `martex-quant`, throughout.** The old name was
  `trading-bot`, and every name derived from it moved:

  | | Before | After |
  |---|---|---|
  | PyPI distribution | `trading-bot` | `martex-quant` |
  | Command | `tradingbot` | `martex-quant` |
  | Import package | `trading_bot` | `martex_quant` |
  | Repository | `martex-dev/trading-bot` | `martex-dev/martex-quant` |
  | Workspace env var | `TRADING_BOT_HOME` | `MARTEX_QUANT_HOME` |

  The trigger was PyPI refusing `trading-bot` as too similar to an existing
  project. Checking that the exact name returned 404 was not sufficient —
  that only proves nobody holds it, not that PyPI will let you register it,
  because the similarity check collapses separators. `tradingbot`,
  `trading-bots`, and `tradebot` all already exist.

  No research artefact changed. No hypothesis document referenced the package
  name, the frozen-baseline gate excludes the `code` category by design, and
  no golden stdout contained it — so no verdict, ledger entry, statistic, or
  frozen baseline was touched by the rename.

  GitHub redirects the old repository URL, so existing clones and links keep
  working. `git remote set-url` is still worth running on any local clone.

- Enabled the PyPI publishing job, which runs on every version tag via
  trusted publishing (OIDC, no stored API token).

### Fixed

- The v1.0.0 release notes told users to run `tradingbot init my-lab && cd
  my-lab`. Windows PowerShell has no `&&` operator — it is a parser error, so
  neither half runs, which is exactly how the first release attempt failed.
  Every chained command in the README, INSTALL, the `--help` epilog, and the
  release template is now one per line. The published v1.0.0 notes were
  corrected in place.
- The release template interpolated the git tag straight into a pip command,
  emitting `==v1.0.0` (with the `v`), which pip rejects. The version is now
  derived by stripping the prefix.

---

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
  resolve their workspace from `--workspace`, `$MARTEX_QUANT_HOME`, or the
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

### Fixed

- **CI, which had been failing on every push before this release.** Two
  causes: `mypy` reported 128 errors because `numpy` — a real transitive
  dependency of the research modules — was never declared in
  requirements-dev.txt; and test collection aborted outright because
  `test_ensemble.py` and `test_tesla_cnn.py` import `sklearn`/`keras` at
  module scope, so the exact install commands in the README left a new
  contributor unable to run the suite at all.
- The frozen-baseline golden gate no longer runs on hosted runners, where it
  could never pass: the fingerprint hashes inputs byte for byte and the
  repository stores CRLF, so a Linux checkout's LF changes every hash. It was
  always documented as a local gate; now it behaves like one. Local strength
  is unchanged.

### Notes

Nothing in this release changes a single research verdict, strategy, cost
model, or statistic. The ledger is untouched. This is packaging.
