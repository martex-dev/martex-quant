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

`OBSERVATION` — full suite **228 tests, all passing** (2026-08-10).
Working tree clean except the new MI audit document. CI workflow runs
ruff check, ruff format --check, mypy (strict), pytest on every push.

`OBSERVATION` — trial ledger: **120 registered, 119 run, 1 data-blocked
(H54)**. Single source of truth remains PROJECT_MEMORY.md.

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
