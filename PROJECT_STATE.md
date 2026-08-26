# PROJECT_STATE.md — operational snapshot (refreshed 2026-08-10)

Read together with PROJECT_MEMORY.md (knowledge/lessons) and CLAUDE.md
(standing instructions). This file = what is RUNNING and what happens next.

**Refresh note:** the previous version of this file was written
2026-07-12 and described a July eval sprint as imminent. It went stale.
This refresh is built from verified repository/OS evidence only,
gathered 2026-08-10. Historical conclusions in PROJECT_MEMORY.md and in
docs/ are NOT touched by this refresh — no verdict, ledger entry, or
research result is changed here.

**Convention used below:** `OBSERVATION` = a measured fact with its
source. `INTERPRETATION` = a reading of those facts, explicitly marked
as such and not to be cited as evidence. Where an interpretation would
require a sample we do not have, it says so.

---

## Phase

Phase 5 (paper trading), running continuously since 2026-07-10.

New in parallel: **Market Intelligence Lab, Phase 1** — repository audit
complete (docs/research/market-intelligence-lab-audit.md, 2026-08-10).
Approved scope: Layers 1-4 only (feature/statistics consolidation,
multiple-testing framework, bitemporal series infrastructure,
MarketState + poison tests). Large-scale discovery engine NOT approved.

---

## Paper accounts — verified state (source: data/paper/<name>/equity.jsonl)

All four started at $5,000. Figures are the last mark, 2026-08-10 00:10 UTC.

| Account | Marks / distinct days | Window | Equity | Since start | Peak (date) | Max DD on record |
|---|---|---|---|---|---|---|
| vol-target | 36 / 31 | 07-10 → 08-10 | $5,014.11 | +0.28% | $5,024.58 (08-07) | −0.21% |
| rotation | 28 / 28 | 07-11 → 08-10 | $4,221.78 | **−15.55%** | $5,126.05 (07-13) | **−20.67%** |
| rotation-stop | 26 / 26 | 07-12 → 08-10 | $4,395.58 | **−12.07%** | $5,095.19 (07-13) | **−13.73%** |
| crash-bounce | 27 / 27 | 07-12 → 08-10 | $5,000.00 | 0.00% | — | 0.00% |

`OBSERVATION` — rotation's trough was $4,066.28 on 2026-08-04; it has
recovered to $4,221.78. rotation-stop's trough IS its current mark, so
its drawdown from peak (−13.73%) equals its max drawdown on record.

`OBSERVATION` — crash-bounce has never taken a position: 27 marks, zero
exposure throughout, $5,000.00 unchanged. Its trigger (BTC day < −3%)
has not fired in the record window.

`OBSERVATION` — vol-target holds 1 non-zero exposure, cash $4,700.73.
Its per-symbol lookbacks at the last mark: BTC 180, ETH 180, BNB 90,
SOL 180, XRP 60, ADA 60, DOGE 180, LTC 180.

### rotation-stop latch state (2026-08-10)

`OBSERVATION` — from the account's own diary story and state file:
- 38 coins ranked (universe config lists 40; 2 lack data at rank time).
- **34 of 38 coins carry an active safety stop** (fell > 2×ATR14 from
  their 30-day high; skipped until a fresh 30-day high clears the latch).
- Single held position: HMSTRUSDT at 15.92% of equity.
- Cash $3,695.64 = **84.1% of equity**.
- Lookback parameter 90; `last_reselect` 2026-07-12, so the next 90-day
  reselect is due ~2026-10-10.

`INTERPRETATION` (flagged, low confidence) — the latch mechanism is
doing mechanically what H42b specified: as trends broke, positions were
exited and re-entry blocked, leaving the book mostly in cash, and
rotation-stop is 3.5pp ahead of un-stopped rotation over the same
window. **This is not evidence that the stop works.** 26 daily marks is
far too short for any inference about the spec, and one shared drawdown
episode is a single observation, not a sample. The validated claim for
H42b rests on the pre-registered backtest (DSR 0.992), not on this
record, and nothing here changes that verdict in either direction.

`INTERPRETATION` — no conclusion is drawn here about *why* the
cross-sectional book drew down. Any such analysis must be pre-registered
before the window is examined (see "Guardrail" below).

---

## Automation health

`OBSERVATION` — Task Scheduler task "TradingBot Paper Trader":
State Enabled, Status Ready, Schedule Type Daily 03:10, Last Run
2026-08-10 03:10:01, **Last Result 0**, Next Run 2026-08-11 03:10.

`OBSERVATION` — **The nightly record has gaps.** Missing calendar days
per account:

| Account | Missing days |
|---|---|
| vol-target | 07-23 |
| rotation | 07-23, 07-24, 07-27 |
| rotation-stop | 07-22, 07-23, 07-24, 07-27 |
| crash-bounce | 07-23, 07-24, 07-27 |

`OBSERVATION` — all gaps fall in 2026-07-22 → 07-27. No run since
07-28 has been missed by any account. data/paper/runs.log (1,940 lines)
contains zero occurrences of "error", "traceback", or "failed".

`OBSERVATION` — vol-target has 36 marks across 31 distinct days, i.e.
five days carry more than one mark (consistent with manual/extra runs).

`INTERPRETATION` — the clustering of every gap into one six-day window,
with a clean log and a healthy scheduler before and after, is consistent
with the machine being off or asleep during that window rather than with
a code fault. This has not been confirmed against OS event logs.

`OBSERVATION` — Dashboard autostart is registered: HKCU Run key
`TradingBotDashboard` → `.venv\Scripts\pythonw.exe scripts/dashboard_service.pyw`.

**Consequence for the shakedown gate:** the pre-registered gate was
"no missed nightly runs over 2 weeks".

`OBSERVATION` — **that gate FAILED.** Four nightly runs were missed on
rotation-stop (three on rotation and crash-bounce, one on vol-target)
during 2026-07-22 → 07-27. This is a permanent historical fact about
the July shakedown and is not erased or re-satisfied by later evidence.

`OBSERVATION` — separately, as *current* operational evidence: the most
recent 13 days (2026-07-28 → 08-10) show zero missed runs across all
four accounts.

The second observation describes the system's present reliability. It is
**not** retroactive satisfaction of the July gate. Any future decision
that requires a clean shakedown needs a newly pre-registered window,
not a re-reading of this one.

---

## Evaluation / funded-challenge status

`OBSERVATION` — every artifact the July sprint plan required is absent
from the repository:

| Expected artifact | Status |
|---|---|
| `config/secrets/hyro.json` (API keys) | ABSENT |
| `config/symbol_map.json` | ABSENT |
| `config/universe_hyro.json` | ABSENT |
| `src/trading_bot/live/bybit_broker.py` | ABSENT |
| `data/live/guard/` (guard run state) | ABSENT |

`OBSERVATION` — `data/live/` contains only the legacy vol-target
dry-run record, last written 2026-07-11, `"dry_run": true`.

`OBSERVATION` — no commit after 2026-07-13 touches eval, broker, or
sprint code. Last commits: 2026-07-13 (single-attempt config canonical),
then 2026-08-10 (TSLA CNN negative result).

**Conclusion (verified):** no funded evaluation appears to have been
purchased, and no live order has ever been placed. The July sprint plan
(docs/research/july-sprint.md, the single-attempt revision, and the
eval-runbook amendment) remains pre-registered and **unexecuted**. Those
documents are not withdrawn or invalidated by this refresh; they are
simply not in progress.

`OBSERVATION` — the canonical eval config, if and when an attempt is
made, remains the one committed 2026-07-13: rotation-stop alone at
RISK_SCALE 0.85, one fee, no retries (P(pass) 62.3%, bust 37.7%,
median 48d). That record stands unchanged.

---

## Data lake

`OBSERVATION` — data/lake/catalog.json: 48 datasets, 40 symbols
(40 × 1d, 8 × 1h). **0 validation errors, 49 warnings** across all
datasets. Newest coverage end: 2026-07-10 21:00 UTC; oldest: 2026-07-09.

`OBSERVATION` — the lake has not been refreshed since 2026-07-11. The
paper trader does not read the lake: it fetches from Binance per run
(live/decision.py `fetch_frames`), so the stale lake has not affected
paper trading. It DOES mean any research run today is working on data
that ends 2026-07-10.

`OBSERVATION` — ancillary datasets live OUTSIDE the lake and outside
the catalog/validation path: `data/funding/` (8 files), `data/perp/`
(8), `data/intraday/` (34 files, 3 distinct ad-hoc schemas: `_15m`,
`_tb15m`, `_oi1h`). Addressing this is Layer 3 of the MI Lab.

`OBSERVATION` — `config/universe.json`: 40 symbols, rule "top40 by 24h
quote volume, 2026-07-12, union legacy 8, stables/leveraged excluded".

---

## Code health

`OBSERVATION` — full suite **567 tests, 566 passing** (2026-08-26), of
which 30 are golden-output regressions over the whole research corpus.
The single failure is the pre-existing frozen-fingerprint mismatch on
`research_graph_report` recorded below (hypothesis doc 59 edited after
the baseline was frozen); it needs a deliberate re-freeze and is not a
code defect. +24 of the new tests cover the CLI, workspace scaffolding,
and the packaging contract. CI workflow runs ruff check, ruff format --check,
mypy (strict), pytest on every push; the golden tests skip in CI (no
market data there) and are a LOCAL gate.

`OBSERVATION` — trial ledger: **125 registered, 124 run, 1 data-blocked
(H54)** as of 2026-08-11. H58 added 5 (learned indicator ensemble,
KILLED). Single source of truth remains PROJECT_MEMORY.md; the machine-
readable mirror is docs/research/ledger/trials.toml, whose documented
per-hypothesis deltas sum to 120 with the unexplained 5 carried
explicitly in `[unallocated]` rather than distributed by guess.

`INTERPRETATION` — every future strategy claim is now deflated against
125 rather than 120. That is a real cost, accepted deliberately and
recorded in the H58 registration before the test ran.

---

## Public distribution — v1.0.0 (new, 2026-08-26)

`OBSERVATION` — the project is now packaged as installable software, not
only a readable repository. Nothing in the research changed: no verdict,
ledger entry, cost model, or statistic was touched. This is packaging.

What shipped:

- `tradingbot` console entry point (`src/trading_bot/cli.py`) covering
  init, doctor, quickstart, data pull/status, backtest, montecarlo,
  paper, dashboard, ledger.
- **Workspaces** (`src/trading_bot/workspace.py`). Nearly every path in
  this codebase is cwd-relative (`data/lake`, `data/paper/<strategy>`,
  `docs/research/ledger/trials.toml`, `config/universe.json`), which
  only worked from a checkout. The CLI now resolves a workspace from
  `--workspace` / `$TRADING_BOT_HOME` / cwd and chdirs into it before
  dispatch — one decision point instead of threading a root through
  modules the ledger depends on.
- **The corpus ships inside the wheel.** `setup.py` vendors `docs/` and
  `config/` into `trading_bot/_bundle/` at build time (secrets excluded);
  `src/trading_bot/bundle.py` resolves the live checkout first and the
  packaged copy otherwise. A `pip install` therefore carries the 29
  hypothesis documents and the 125-trial ledger, not just code.
- MIT `LICENSE`, `DISCLAIMER.md`, `CONTRIBUTING.md` (pre-registration
  rule applies to PRs), `SECURITY.md`, `CHANGELOG.md`, `docs/INSTALL.md`,
  `docs/USAGE.md`, rewritten `README.md`.
- `.github/workflows/release.yml`: tag `v*` -> build, verify the wheel
  carries the corpus and carries no credentials, smoke-test the built
  wheel on Linux/Windows/macOS, attach to a GitHub Release. The PyPI job
  is present but gated behind `if: false` until the name is registered
  with a trusted publisher.
- `scripts/*.cmd` de-hardcoded (they contained an absolute path to this
  machine) plus `.sh` equivalents for Linux/macOS.

`OBSERVATION` — verified end to end: built wheel installed into a clean
venv with no checkout present, then `init` -> `doctor` -> `ledger` ->
`quickstart` (real Binance pull + walk-forward) -> `paper` all succeeded,
resolving the corpus from site-packages.

`OBSERVATION` — distribution name `trading-bot` was confirmed unclaimed
on PyPI at build time. Registering it is a manual step the maintainer
must take before the PyPI job is enabled.

`INTERPRETATION` — the risk this introduces is reputational, not
statistical: a public audience may read "validated" as "profitable".
The README, DISCLAIMER, and the quickstart's closing text all state
plainly that neither validated strategy has been shown profitable with
real capital. That wording is load-bearing and should not be softened
for marketing.

---

## Data lake: TWO lakes, and why (decided 2026-08-11)

`OBSERVATION` — the lake was stale (ended 2026-07-09 against a paper record
starting 07-10) and was refreshed: 40/40 symbols pulled, daily, no failures.
`data/lake` now runs to 2026-08-10.

`OBSERVATION` — refreshing it into the single lake **broke the golden
baseline**. All 30 deterministic scripts changed their `inputs` fingerprint,
and at least one changed its STDOUT: `h58_ensemble_study` went from 30 to 31
walk-forward windows (accuracy 0.5109 -> 0.5139) because an extra month of
data admits an extra window. H58's verdict is unaffected — still noise, still
killed — but the published figures moved.

`INTERPRETATION` — this is not a bug in either the refresh or the goldens. It
is the consequence of a design gap: the goldens prove that refactors change
no published number, and that guarantee is only meaningful against a FROZEN
input set. Published numbers were computed on data through 2026-07-09. A lake
that moves underneath them cannot serve as their witness.

**Decision — two lakes, both real, neither hidden:**

| Path | Contents | Role |
|---|---|---|
| `data/lake` | through **2026-07-09** | the FROZEN research lake. The input set every published figure was computed on. Immutable until a deliberate, recorded epoch bump. |
| `data/lake-current` | through **2026-08-10** | the CURRENT lake. New research, and the divergence hunt. |

The frozen one keeps the plain name because every committed script points at
`data/lake`; renaming would touch the whole corpus and would itself invalidate
the goldens it was meant to protect.

**Bumping the epoch is a deliberate act, never a side effect.** It means:
re-verify every stdout golden against the OLD lake first, swap, re-freeze,
and record in PROJECT_MEMORY which published figures moved and by how much.
It is not done by running a pull.

`OBSERVATION` — both lakes are under `data/`, which is gitignored, so neither
is in version control. A backup of the frozen lake was taken before the pull
and the restore was verified by reading both back.

### Consequence for the H59 divergence hunt

The hunt is now UNBLOCKED: `data/lake-current` covers 2026-07-10..08-10, the
live paper window. The pre-registered market-context question — did the whole
market fall? — is answerable for the first time, and answering it is the
next step.

---

## Meme layer — new, 2026-08-11 (running)

`OBSERVATION` — two collectors started 2026-08-11 ~16:05 UTC, both free and
keyless, both holding an atomic PID lock so a duplicate launch cannot double
the request rate or interleave writes:

| Job | Cadence | Writes |
|---|---|---|
| `scripts/meme_record.py` | 10 pages / 150s | `data/meme/launches/*.jsonl` |
| `scripts/meme_panel.py` | full cohort / 300s | `data/meme/panel/*.jsonl` |

`OBSERVATION` — capture rate ~2,000 Solana launches/hour. First 1,535
launches, panel span 0.2h: 14.4% report any liquidity at entry; median depth
among those is **$6**; a $50 ticket clears a 15% round-trip cost ceiling in
**5.6%** of the cohort; **7.8%** ever traded above entry.

`INTERPRETATION` (low confidence, 10 minutes of panel) — the binding
constraint on a cohort strategy looks like the *number of tradable tickets*,
not the hit rate. Not to be cited until the panel has ≥12h.

H60 is registered (docs/hypotheses/60-meme-launch-cohort.md) with verdict bars
and a pre-committed expectation of KILLED. Ledger 125 → 134 (+1 descriptive).
The layer produces signals only; no order path, no keys, no funds.

`OBSERVATION` — **pre-existing test failure, not caused by this work:**
`test_frozen_fingerprint_categories[research_graph_report]` fails because
`docs/hypotheses/59-live-drawdown-consistency.md` was edited after the golden
baseline was frozen (14,101 → 14,165 bytes). Verified by stashing the meme
layer and re-running. Needs a deliberate re-freeze.

---

## Guardrail for MI work (new, 2026-08-10)

The rotation/rotation-stop drawdown described above is an open,
unexplained window in a live paper record. It is exactly the kind of
material that invites post-hoc explanation.

**Rule:** any strategy × market-state analysis touching the
2026-07-12 → 2026-08-10 window must be pre-registered with verdict bars
BEFORE the window is examined, per the standing project rule. The
drawdown is recorded here as an observation so that it cannot later be
presented as a discovery.

---

## Next actions (in order)

1. **MI Lab design gate (in progress):** statistical/accounting design
   for the hierarchical trial framework —
   docs/research/mi-trial-accounting-design.md. Review required before
   any Layer 1 code.
2. **MI Layer 1** after design review: consolidate 6 duplicated panel
   builders, 11 block-bootstrap copies, 11 forward-return definitions
   into canonical infrastructure with regression tests proving
   historical behaviour is preserved. Research-integrity work, not
   cleanup.
3. **Data availability contract** to be written before Layer 3.
4. **Decide the eval question explicitly.** It has been open and
   undecided for ~4 weeks. Either register a decision to attempt with
   the canonical single-attempt config, or record a decision to defer,
   with a reason. Leaving it implicit is the one state that costs
   information without buying any.
5. **Refresh the lake** before any research run that needs data past
   2026-07-10.
6. **October:** move the paper task 03:10 → 02:10 local (DST) to stay
   near the UTC close.

---

## Backlog (unchanged, docs/research/backlog.md)

Options/Deribit VRP data project; correlation-spike de-risking; carry
infrastructure (post-eval, own-capital); own-capital book = rotation-stop
+ crash-bounce overlay (43a: Sharpe 1.55, +79%/yr, fails only eval
geometry) — own-capital bars to be registered post-funding.
