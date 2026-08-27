# PROJECT_STATE.md — operational snapshot (refreshed 2026-08-26)

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

All four started at $5,000. **Refreshed 2026-08-26** (previous refresh
2026-08-10 is superseded; figures below recomputed from each account's
full equity.jsonl, not carried forward).

| Account | Marks / distinct days | Window | Equity | Since start | Peak (date) | Max DD on record |
|---|---|---|---|---|---|---|
| vol-target | 52 / 47 | 07-10 → 08-26 | $5,248.91 | **+4.98%** | $5,294.97 (08-24) | −0.87% |
| rotation | 43 / 43 | 07-11 → 08-26 | $4,124.16 | **−17.52%** | $5,126.05 (07-13) | **−20.67%** |
| rotation-stop | 40 / 40 | 07-12 → **08-25** | $4,671.38 | **−6.57%** | $5,095.19 (07-13) | **−15.56%** |
| crash-bounce | 42 / 42 | 07-12 → 08-26 | $5,000.00 | 0.00% | — | 0.00% |

`OBSERVATION` — **rotation-stop's window ends 08-25, not 08-26.** It
missed today's mark; cause and fix in "Automation health" below.

`OBSERVATION` — direction of travel since the 08-10 refresh, per
account: vol-target +0.28% → +4.98%; rotation −15.55% → −17.52%;
rotation-stop −12.07% → −6.57%. rotation-stop's trough is no longer its
current mark — it bottomed at $4,302.60 on 08-21 and has recovered
since, so its drawdown from peak is now smaller than its max DD on
record (−15.56%), which the 08-10 refresh noted were then equal.

`OBSERVATION` — crash-bounce **still** has never taken a position: 42
marks, zero exposure throughout, $5,000.00 unchanged. Its trigger (BTC
day < −3%) has not fired once in the record window, now ~46 days.

`INTERPRETATION` (flagged, low confidence) — 40–52 marks remains far too
short for inference about any of these specs, and nothing here changes a
verdict in either direction. Recorded as operational fact only. The
eval-deferral decision below cites these numbers but does **not** rest
on them; see the reasoning there.

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

### Mid-run truncation — found and mitigated 2026-08-26

`OBSERVATION` — the "zero missed runs" claim above no longer holds. Two
**partial** days are on record since it was written:

| Date | Started | Completed | Accounts that lost their mark |
|---|---|---|---|
| 2026-08-20 | 09:46 (catch-up, not 03:10) | 1 of 4 | rotation, crash-bounce, rotation-stop |
| 2026-08-26 | 03:10 | 3 of 4 | **rotation-stop** |

`OBSERVATION` — Task Scheduler for the 2026-08-26 run: Last Run
03:10:02, **LastTaskResult 3221225786 = 0xC000013A
(STATUS_CONTROL_C_EXIT)**. The task was terminated mid-execution, not
completed. data/paper/runs.log contains **zero** occurrences of "error",
"traceback", or "failed" across all 2,982 lines — the truncation leaves
no trace in the log because the process is killed, not failed.

`OBSERVATION` — the 2026-08-20 run started at **09:46**, not 03:10. That
is StartWhenAvailable firing a missed schedule late, and it completed
only the first account in the loop. A catch-up run fires while the
machine is in use, which is exactly when it is most likely to be
interrupted.

`OBSERVATION` — the runner is a sequential `for` loop over accounts. Its
order was `vol-target rotation crash-bounce rotation-stop`, so
**rotation-stop — the deployed spec and the canonical eval candidate —
was last, and lost its mark in both truncations.**

`INTERPRETATION` — an exit code of STATUS_CONTROL_C_EXIT on a scheduled
task is consistent with the machine being shut down, slept, or logged
off while the loop was running. This matches the July gap
interpretation, now with a specific code rather than an inference. It is
not a code fault, and no defect in the paper trader is implied.

**Mitigation applied** (scripts/run_paper_daily.cmd): the loop is
reordered to `rotation-stop rotation vol-target crash-bounce` — ordered
by how much each record matters, deployed spec first, never-triggered
overlay last. This does not prevent truncation; it changes **which**
account absorbs one. Accounts are independent, so ordering has no effect
on any result.

`OBSERVATION` — the 2026-08-26 rotation-stop mark was **not**
backfilled. A mark written ~19h after its scheduled slot would carry a
timestamp inconsistent with every other mark in the series, and one
recorded gap is cheaper than one silently irregular observation. The gap
stands in the record.

---

## Evaluation / funded-challenge status

`OBSERVATION` — every artifact the July sprint plan required is absent
from the repository:

| Expected artifact | Status |
|---|---|
| `config/secrets/hyro.json` (API keys) | ABSENT |
| `config/symbol_map.json` | ABSENT |
| `config/universe_hyro.json` | ABSENT |
| `src/martex_quant/live/bybit_broker.py` | ABSENT |
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

### DECISION — eval DEFERRED (owner, 2026-08-26)

Next-action #4 ("decide the eval question explicitly") is **CLOSED as a
deferral**. This is the recorded decision the previous refresh asked for;
the question is no longer open.

**Decision:** no funded evaluation will be attempted, and no eval fee
will be paid, until the system demonstrates profitability. The eval is
untouched until then.

**Reason (owner's, stated plainly):** paying to be evaluated on a book
that is not yet making money buys nothing. The evaluation fee is a real
cost with a known failure probability (37.7% bust on the canonical
config); spending it before there is profit to demonstrate converts
research uncertainty into a cash loss without producing information the
ledger does not already have.

**Supporting numbers at the time of the decision** (2026-08-26, from
each account's own equity.jsonl — see the refreshed table above):
rotation-stop **−6.57%**, rotation **−17.52%**, crash-bounce **0.00%**
(never triggered), vol-target **+4.98%**, after ~46 days.

`INTERPRETATION` (flagged) — these paper figures are **not** evidence
against the deployed spec, and this decision does not rest on them as if
they were. 40 marks is far too short for inference about H42b, whose
validation rests on the pre-registered backtest (DSR 0.992), unchanged.
The decision rests on the asymmetry instead: deferring costs only time,
while attempting costs a fee at a 37.7% bust rate for a demonstration
there is currently no reason to make.

**Condition to revisit:** a re-registered decision, with a stated
profitability criterion met. Not a mood, not a good month — a written
criterion, decided before the window it is measured over, per the
project's standing rule that bars are set before results exist. Until
that document exists, the eval stays closed and the runbook stays
un-actioned.

**What this does NOT change:** the July sprint plan and the eval-runbook
remain pre-registered and valid documents, not withdrawn. The canonical
single-attempt config above stands as the config that *would* be used.
Deferral is not invalidation.

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
and the packaging contract.

`OBSERVATION` — **CI was red on every push and had been for some time**;
found 2026-08-26 while preparing the public release. The green-badge
claim in the README was false. Two independent causes, both now fixed:

1. mypy, 128 errors. CI installs `-e .` + requirements-dev.txt, which
   omitted numpy; mypy type-checks research/tesla/* and
   research/ensemble.py unconditionally and cannot resolve their
   annotations without it. It passed locally only because this machine's
   venv happens to have numpy. Fixed by declaring numpy in
   requirements-dev.txt.
2. Test collection aborted: test_ensemble.py and test_tesla_cnn.py import
   sklearn/keras at module scope, so a plain dev install — the exact
   commands the README gives — died with ModuleNotFoundError. Fixed by
   gating those two modules in tests/conftest.py, with a separate CI job
   installing the `research` extra so coverage is not lost.

`OBSERVATION` — the golden fingerprint gate did NOT skip in CI as this
file previously claimed. `research_graph_report` declares only committed
markdown as inputs, so `inputs_present` was true on the runner and the
test ran. It could never pass there: the fingerprint hashes inputs byte
for byte and this repo stores CRLF, so a Linux checkout's LF changes
every hash and byte count (PROJECT_MEMORY.md 16,640 -> 16,429); the
environment category also records interpreter and package versions the
runner resolves independently. The skip is now keyed on the runner.
**Local strength is unchanged** — still keyed only on inputs being
entirely absent, so a present-but-CHANGED input remains a hard failure.

`OBSERVATION` — CI green as of 2026-08-26 (run 32964842194), three jobs:
lint/types/tests, the research extra, and a wheel-install smoke test.

`INTERPRETATION` — the lesson is not about numpy. A local venv that had
accumulated extras silently diverged from the declared dependency set,
and the only signal was a badge nobody read. Treat CI status as a gate,
not decoration, and check it in any session that claims a clean run.

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

- `tradingbot` console entry point (`src/martex_quant/cli.py`) covering
  init, doctor, quickstart, data pull/status, backtest, montecarlo,
  paper, dashboard, ledger.
- **Workspaces** (`src/martex_quant/workspace.py`). Nearly every path in
  this codebase is cwd-relative (`data/lake`, `data/paper/<strategy>`,
  `docs/research/ledger/trials.toml`, `config/universe.json`), which
  only worked from a checkout. The CLI now resolves a workspace from
  `--workspace` / `$MARTEX_QUANT_HOME` / cwd and chdirs into it before
  dispatch — one decision point instead of threading a root through
  modules the ledger depends on.
- **The corpus ships inside the wheel.** `setup.py` vendors `docs/` and
  `config/` into `martex_quant/_bundle/` at build time (secrets excluded);
  `src/martex_quant/bundle.py` resolves the live checkout first and the
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

`OBSERVATION` — the distribution is named **`martex-quant`**
(`pip install martex-quant`), and the command is `martex-quant`. The
import package is unchanged — still `import martex_quant` — and so is the
repository name.

`OBSERVATION` — the first choice, `trading-bot`, was rejected by PyPI as
too similar to an existing project. The pre-check was wrong: querying
`pypi.org/pypi/trading-bot/json` returned 404, which proves only that
nobody *holds* the exact name. PyPI additionally refuses names that are
too similar to existing ones, and its similarity check collapses
separators, so `trading-bot` reads as a duplicate of `tradingbot` (which
exists, as do `trading-bots` and `tradebot`).

`INTERPRETATION` — availability and registrability are different
questions on PyPI, and only the second one matters. A 404 is necessary
but not sufficient; the name is not proven until an upload succeeds, and
a pending publisher does not reserve it in the meantime.

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

## H67 — variance risk premium KILLED; family F3 closed without a build (2026-08-27)

`OBSERVATION` — pre-registered (commit afa6c3e) before any study code
existed; run the same day. **Ledger 147 -> 152.** First hypothesis of
family F3 (options/VRP) and a KILL TEST, not a strategy build: its job
was to decide whether a Deribit option-chain collector and a Greeks layer
were worth building. **They are not, and were not built.**

New data collected and kept: `data/dvol/{BTC,ETH}.parquet` — Deribit
DVOL, the 30-day model-free implied-vol index, 1,983 daily bars each from
2021-03-24, free and unauthenticated (`scripts/pull_dvol.py`).
**Structural limit:** only BTC and ETH publish usable DVOL history, so
this family can never be broad the way carry's universe is.

| | gross `IV − RV` | harvestable `(K²−RV²)/2K` | vs 3.0 vol-pt cost |
|---|---|---|---|
| BTC | +8.72 vol pts (IV>RV on 72.3% of days) | **+6.01** | clears, then halved by cost |
| ETH | +4.55 | **+1.24** | **never cleared it** |

`OBSERVATION` — the primary book (50/50, declared in advance) nets CAGR
+1.09%, Sharpe 0.16, CI [−2.14, +3.93] bp/day. Gate A fails all four
bars; Gate B fails both; Gate C passes at +0.0237.

`INTERPRETATION` — **the premium is real and the harvest is not.** That
is the intraday-reversion pattern for the fifth time: a genuine,
statistically clear premium sitting below what retail execution costs to
reach.

**Two findings outlive the kill** (both now in PROJECT_MEMORY meta-findings
9 and 11):

1. **The correlation bar is blind to tail dependence.** Full-sample corr
   with rotation-stop is +0.0237, but on rotation-stop's worst 1% of days
   this book returns **−1.296%/day** against +0.004% unconditional.
   Joint-loss frequency is at independence; the dependence is entirely in
   magnitude. Any short-convexity edge passes `|corr| < 0.30` almost
   automatically. **Open decision, not yet adopted:** add a
   tail-conditional bar for asymmetric payoffs.
2. **Screen in the units the position pays in.** The naive `IV − RV`
   screen overstates the harvestable premium by a third on BTC and 73% on
   ETH.

`OBSERVATION` — regime decay, monotone: 2021 +15.66%/yr, 2022 +9.30,
2023 +6.79, **2024 −0.53, 2025 −8.60, 2026 −17.59**. Carry died over the
same window across three independent hypotheses.

`INTERPRETATION` — two mechanically unrelated premia going to zero
together reads as market maturation, but both are measured on the same
calendar window and that is the confound that would fake it. Held as a
hypothesis. The operational consequence stands either way: **anything
sized on 2021-2023 history is sized on a regime that is gone.**

`OBSERVATION` — honest caveat, stated in the pre-registration before the
run: **March 2020 is outside the DVOL window.** The reported MDD of
−24.31% excludes the worst short-vol event in crypto's history and is the
least trustworthy figure in the study. The kill does not rest on it.

---

## H62 — carry: first validated edge outside the momentum family (2026-08-27)

`OBSERVATION` — pre-registered 2026-08-27 before any code was written;
run the same day. **All five bars passed.** 2,124 common days
(2020-09-15 -> 2026-07-09), 8 symbols, 1x collateralized, costs on both
legs.

| Metric | H62 carry | rotation-stop (deployed) |
|---|---|---|
| Sharpe | **2.29** | 1.47 |
| CAGR | +3.24% | +42.9% |
| MDD | **-5.09%** | -29.0% |
| corr with rotation-stop | **+0.0041** | — |
| DSR @126 | 0.9754 | 0.9909 |

`OBSERVATION` — **the correlation is the result that matters: +0.0041.**
Meta-finding 5 records that every long-crypto momentum book measured so
far correlates 0.52-0.82 with every other one, which is why H43b/H43c
were screened out without ever running. Carry is the first stream in the
ledger that is genuinely independent of the deployed spec.

`OBSERVATION` — **and the regime finding is equally load-bearing.** H05
warned in advance that the recent funding regime is thin. It is worse
than thin: the edge is concentrated in 2021 (+15.68%/yr), inverted in
2022 (-4.83%/yr), and over the **last 365 days earns +0.08%/yr at Sharpe
0.34** — indistinguishable from zero.

`INTERPRETATION` — carry is a **regime harvest, not a constant**. The
full-sample verdict stands as pre-registered and is not revised, but any
forward expectation built on +3.24% is an expectation about 2021.
Deploying capital into today's regime earns approximately nothing.
Infrastructure now exists (`backtesting/carry.py`, 10 unit tests) and
that is durable; the premium is not.

**Next question this opens (NOT tested, needs its own numbered doc):** a
funding-conditional variant — hold only when trailing funding is rich.
It introduces a tunable threshold and must not be bolted on.

---

## Next actions (in order)

**Read this first (2026-08-26).** Items 1–4 and 7 below are struck
through: every one was already finished, some for over two weeks. This
list was written 2026-08-10 — **one day before the entire MI Lab merged**
— and was never updated, so the project's own answer to "what next"
pointed at completed work while the real question went unasked.

**Superseded in part, 2026-08-27.** Carry was built and tested. See
"H62 — carry" below; the ledger is now **126**.

`INTERPRETATION` — with the MI Lab scope complete, the eval deferred, and
the contributor proposal declined on feasibility, **there is no large
piece of infrastructure left to build.** The binding constraint is now
research, and `docs/research/owncap-sizing.md` §3 already names it:

> "The route to higher sustainable monthly returns is a higher-Sharpe
> book, not more leverage [...] Every genuinely independent edge added
> raises the ceiling itself. **This is now a primary research
> objective.**"

The book tops out near +10%/month average at survivable 2× leverage. More
leverage cannot fix that — only a genuinely independent edge can. The
backlog's candidates (Deribit VRP, correlation-spike de-risking, carry
infrastructure) are the standing shortlist, and each needs a
pre-registered hypothesis before anything runs.

1. ~~**MI Lab design gate (in progress).**~~ **CLOSED — and it was
   already closed.** docs/research/mi-trial-accounting-design.md §11 has
   recorded "approved with amendments 1–9" since 2026-08-10, but its
   status header still read "DESIGN — for review", so this list carried
   the gate as open work for 16 days when only the header was stale.
   Header reconciled 2026-08-26. **Layer 1 is unblocked and is now the
   first action.** One new amendment (10, selection vs description) is
   PROPOSED in §2 and needs an owner yes/no; it does not block Layer 1.
2. ~~**MI Layer 1.**~~ **DONE — merged 2026-08-11 in `990ac63`**, Steps
   0–5. Verified against its own definition of done 2026-08-26; the
   audit table is appended to
   docs/research/mi-layer1-consolidation-plan.md. Canonical
   `stats/bootstrap.py` (4 estimator shapes + RNG-contract test),
   `features/panel.py`, canonical `forward_return`; 13 scripts migrated;
   30 frozen goldens. The `def daily_panel` / `def diff_ci` names still
   in scripts are thin wrappers passing historical parameters — the
   "parameterize, never normalize" rule, not surviving duplication.
3. ~~**Data availability contract before Layer 3.**~~ **MOOT — Layer 3
   merged 2026-08-11** (`909d778`), along with Layers 2 (`d53c5e5`), 4
   (`92dfab2`) and 5 (`0fefa50`) and stages 6, 8, 9, 10. **The entire
   approved MI Lab scope (Layers 1–4) is complete.** If a data
   availability contract is still wanted it is now a retrospective
   document, not a prerequisite.
4. ~~**Decide the eval question explicitly.**~~ **CLOSED 2026-08-26 —
   deferred by owner decision.** See "DECISION — eval DEFERRED" above.
   Reopening requires a written profitability criterion, registered
   before the window it is measured over.
5. **Refresh the lake** before any research run that needs data past
   2026-07-10.
6. **October:** move the paper task 03:10 → 02:10 local (DST) to stay
   near the UTC close.
7. ~~**Decide the H43a census.**~~ **DONE 2026-08-26 —
   docs/research/h43a-bounce-census.md, 0 trials.** Result: the
   contributor proposal's `f(trailing_vol; k1, k2)` form is **DECLINED on
   feasibility**. `corr(trailing_vol, breach indicator) = −0.0310` — the
   relationship the form depends on does not exist, and
   `corr(trailing_vol, overlay P&L) = +0.1113` means shrinking on high vol
   cuts the earning days. Breaches by vol quintile are 9/5/6/3/6: no tail
   to cut. The base book breaches once in 2,880 days; the overlay adds 29.
   **Nothing further is owed on that proposal** beyond sending the census.
   A flagged post-hoc observation in §5 must NOT be advanced without its
   own pre-registration.
8. **New, 2026-08-26 — watch for further truncated paper runs.** Two are
   on record (08-20, 08-26). The loop reorder protects the deployed spec
   but does not stop truncation. If partial days keep appearing, the
   scheduler settings need attention, not the runner.

---

## Backlog (unchanged, docs/research/backlog.md)

~~Options/Deribit VRP data project~~ — **CLOSED 2026-08-27 by H67**:
DVOL collected, premium measured and real, harvest killed on cost. No
option-chain collector is owed. Correlation-spike de-risking; carry
infrastructure (post-eval, own-capital); own-capital book = rotation-stop
+ crash-bounce overlay (43a: Sharpe 1.55, +79%/yr, fails only eval
geometry) — own-capital bars to be registered post-funding.
