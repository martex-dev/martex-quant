# Market Intelligence Lab — Phase 1: Repository Audit & Architecture Assessment

Date: 2026-08-10. Status: **assessment only, no code written.**
Baseline verified before writing: 228 tests pass, CI config green
(ruff lint + format, strict mypy, pytest).

This document answers the seven questions Phase 1 of the Market
Intelligence (MI) spec asks, flags four conflicts between the spec and
the existing architecture that must be resolved BEFORE implementation,
and proposes a build order that differs from the spec's suggested one
for a specific statistical reason.

---

## 1. What the existing system actually is

~5,400 lines of source across 11 packages, ~1,900 lines of one-off
research scripts, 26 pre-registered hypothesis documents, 120 ledger
trials. It is small, tight, and unusually honest. Nothing here is legacy
cruft; almost every module earns its place.

### The layer map

| Layer | Module | What it guarantees |
|---|---|---|
| Time model | `data/models.py` | Bar open time, UTC, ms precision. One dtype, one convention, everywhere. |
| Ingest | `data/collectors/binance.py` | ccxt adapter behind `Collector` interface |
| Validate | `data/processors/validation.py` | **Reports problems, never repairs them.** Errors block the write. |
| Store | `data/store/parquet_store.py` | Hive-partitioned lake, atomic year-file replace, idempotent upsert |
| Index | `data/store/catalog.py` | JSON registry: coverage + last validation outcome per dataset |
| Leakage gate | `backtesting/history.py` | Cursor-bounded view; **look-ahead is structurally inexpressible** |
| Engine | `backtesting/engine.py`, `multi.py` | Signal at close → fill at next open, through a cost model |
| Costs | `execution/simulated.py` | Fees, spread, slippage — the "does it survive execution" gate |
| Honest selection | `backtesting/research.py` | Train-only param selection; **shared with the live path** |
| Statistics | `backtesting/metrics.py` | Sharpe/MDD/PF + PSR + `expected_max_sharpe` (deflated Sharpe) |
| Constraint sim | `risk_management/prop_sim.py` | Monte-Carlo pass rates against real firm rule geometry |
| Decision core | `live/decision.py` | **One code path** for paper and live; stateful strategies replayed |
| Ops | `live/paper.py`, `guard.py`, `narrate.py`, dashboard | Nightly runs, kill switch, plain-English diary |

### The three safeguards that are the project's real asset

1. **`History` makes look-ahead structurally impossible.** Not a
   convention, not a lint rule — there is no API to index past the
   cursor. Everything MI adds must inherit this property rather than
   re-implement a weaker version of it.
2. **Pre-registration in git.** A numbered doc with verdict bars is
   committed *before* results exist. Git's commit history is the
   immutability mechanism, and it is stronger than any database
   constraint we could add (see conflict C3).
3. **Global trial accounting.** Every trial — including failed variants
   and descriptive horizons — joins the ledger, and DSR is benchmarked
   against ALL of them. This is rarer than the other two and it is what
   makes rotation's DSR 0.990 mean something. It is also the thing the
   MI spec most endangers (conflict C1).

### Operational reality check (PROJECT_STATE.md is ~4 weeks stale)

The state file describes a July eval sprint. As of today:

- Paper automation is **healthy** — 26–36 nightly marks per account
  through 2026-08-10, no gaps.
- No `config/secrets/`, no `symbol_map.json`, no live artifacts beyond
  the July dry-run. **The eval appears never to have been purchased.**
- Paper performance since mid-July: vol-target $5,014 (+0.3%),
  crash-bounce $5,000 (flat, no crash), **rotation $4,222 (−15.6%)**,
  **rotation-stop $4,396 (−12.1%)**.
- rotation-stop is behaving exactly as designed under stress: 34 of 38
  coins stop-latched, 84% cash. The stop is buying the 3.5pp it was
  validated to buy. This is a bad regime, not a broken system.

This matters for MI prioritization and is flagged, not acted on.

---

## 2. Answers to the seven Phase-1 questions

### 2.1 Existing abstractions to REUSE

- `History` — the leakage gate. `MarketState` should be its
  cross-sectional sibling, sharing the cursor discipline.
- `ParquetStore` + `Catalog` + `validate_ohlcv` — the
  collect→validate→store→catalog pattern generalizes to every new
  dataset. Reuse the *pattern*; the class itself needs one extension
  (conflict C2).
- `Interval`, `TIMESTAMP_DTYPE` — the single canonical time model.
- `run_backtest` / `run_multi_backtest` — source of truth for anything
  strategy-grade. MI findings graduate *through* these, never around.
- `walk_forward_backtest` / `select_param` — honest OOS selection.
- `compute_metrics`, `probabilistic_sharpe_ratio`, `expected_max_sharpe`
  — the multiple-testing machinery already exists and is used correctly
  in 9 study scripts.
- `SimulatedBroker` / `ExecutionConfig` — the cost gate that killed
  H52/H53/H57. Every MI "economic significance" claim must pass through it.
- `prop_sim` — for the "does this survive the constraint geometry" question.
- `docs/hypotheses/*.md` — the registration convention, unchanged.

### 2.2 Abstractions that must NOT be duplicated

- **No second backtester or fill model.** MI produces information; the
  existing engine adjudicates strategies.
- **No second time model.** One `TIMESTAMP_DTYPE`, one UTC convention.
- **No second ledger.** PROJECT_MEMORY.md stays the human source of
  truth; any database is a *derived index* (conflict C3).
- **No second statistics implementation.** The 11 copy-pasted block
  bootstraps get extracted upward into one library, not forked sideways.
- **No separate `research` CLI.** Convention is `python -m martex_quant.X`.

### 2.3 Where MI plugs in naturally

| MI concept | Plugs into |
|---|---|
| MarketObservation | New sibling of `ParquetStore` for non-OHLCV series |
| MarketFeature | New `features/` package — extracts 6 duplicated panel builders |
| MarketState | New object with `History`'s cursor discipline, panel-wide |
| Relationship engine | New `stats/` package — extracts 11 duplicated bootstraps |
| Hypothesis lifecycle | Front-matter inside existing `docs/hypotheses/*.md` |
| Strategy × state | Consumes `MultiResult.equity_curve` — no engine change |
| Cost/economic gate | Existing `ExecutionConfig` |
| Reports/diary | Existing `narrate.py` + dashboard patterns |

### 2.4 Where the architecture needs a clean extension

Two places, both in the data layer, both concrete:

**(a) Availability semantics do not exist.** The whole system carries an
implicit assumption: `availability_time = event_time + interval`. For
exchange OHLCV that is exactly right. It is wrong for every dataset MI
wants — funding settles on an 8h cycle, OI is a snapshot, on-chain data
lags by blocks *and* by provider, macro releases describe January and
publish in February, news has embargo/wire lag. The four-timestamp model
(`event_time` / `observation_time` / `availability_time` /
`ingestion_time`) is the right extension. **It should be added for new
data types only — not retrofitted onto OHLCV**, where it would add
ceremony without adding truth.

**(b) `ParquetStore.write` silently destroys revisions.** Line 65:
`.unique(subset="timestamp", keep="last")` — freshly pulled rows
overwrite stored ones. For immutable closed exchange bars this is
correct and deliberate. For any revisable dataset it is a silent
point-in-time violation, and it directly contradicts MI spec §7 ("do not
silently replace historical data"). The fix is not to change
`ParquetStore` — it is to give revisable data a different store whose
key is `(event_time, observation_time)`, so a revision is a new row and
the old vintage survives.

### 2.5 Safeguards that must remain untouched

`History`'s cursor. The validation-blocks-write rule. Signal-at-close /
fill-at-next-open. Train-only parameter selection. The
pre-registration-before-results rule. The shared paper/live decision
core. Global trial accounting. The guard's human-cleared KILLED latch.

### 2.6 Existing assumptions about time, markets, assets

- All timestamps UTC, ms, bar-open convention.
- Daily bars close 00:00 UTC; the nightly task runs 03:10 local to be
  near that close.
- Universe is config-driven (`config/universe.json`, 38–40 coins) with a
  legacy-8 fallback; symbols may list at different dates and join the
  decision set when they have bars.
- Long/flat only (the short leg was tested and killed, H36).
- Survivorship is *mitigated, not eliminated* — fully delisted coins are
  absent. MI must not silently assume the universe is point-in-time correct.

### 2.7 Existing research conventions

Numbered doc → verdict bars committed first → kill test (cheap info
study, vectorized allowed) → strategy grade only via the event-driven
engine → every trial counted → near-misses stay closed → negative
results written up with equal care.

**The convention gap MI should close:** all of this lives in prose and
in ~1,900 lines of one-off scripts. Measured duplication:

- `daily_panel` / `build_panel` reimplemented **6 times** across kill-test scripts
- Block-bootstrap CI machinery copy-pasted into **11 scripts**
- Forward-return definitions (`shift(-N)`) redefined in **11 scripts**

Every copy is a chance for a subtly different alignment — and the ledger
already records one such bug costing a near-miss verdict (the false 0.35
correlation, meta-finding 5). This duplication is the strongest
*evidence-based* argument for the MI feature and statistics layers, and
it is independent of any new data source.

---

## 3. Four conflicts to resolve before implementation

### C1 — Industrial-scale discovery mechanically destroys the existing ledger's standing

This is the most important finding in this audit.

The project's rule is that DSR is benchmarked against **all trials ever
run**. `expected_max_sharpe` scales with trial count:

| Trials | E[max Sharpe]/σ | Hurdle vs today |
|---|---|---|
| 120 (today) | 2.594 | ×1.00 |
| 500 | 3.053 | ×1.18 |
| 2,000 | 3.447 | ×1.33 |
| 10,000 | 3.861 | ×1.49 |
| 100,000 | 4.391 | ×1.69 |

The MI spec explicitly anticipates "thousands of experiments" (§48) and
feature × target × horizon × regime grids (§13–§15). A 10-horizon ×
20-feature × 3-regime sweep is 600 trials in one afternoon — a 33%
higher Sharpe hurdle for everything, retroactively. Rotation's DSR 0.990
was computed at 104 trials; it is the only absolutely-validated spec in
the project and the one currently on a paper account.

**Under the project's own stated accounting rule, building the discovery
engine first would demote its own best existing finding.**

There are only three coherent resolutions, and one must be chosen
explicitly and written into the rules:

1. **Hierarchical families with family-level FDR** (spec §19 done
   properly): trials are grouped, error is controlled *within* family,
   and the cross-family count that enters DSR is the number of
   *families*, not the number of cells. This is the statistically
   standard answer and I recommend it — but it requires that families be
   declared before the sweep, with a fixed cell count, or it degenerates
   into the same dredging with nicer labels.
2. **Two ledgers with a hard wall**: an EXPLORATORY ledger that never
   feeds DSR, and a CONFIRMATORY ledger that does; promotion from one to
   the other costs a pre-registration and a fresh holdout. Simpler, but
   the wall only works if the holdout is genuinely untouched.
3. **Cap the discovery rate**: keep the global counter, accept that every
   sweep is expensive, and therefore run few. Most faithful to the
   current culture, least compatible with the spec's ambition.

**Recommendation: (1) as the mechanism, (2) as the bookkeeping, and the
statistical framework built BEFORE the discovery engine** — i.e. spec
Phase 7 moves ahead of Phase 5. Building discovery first and accounting
later is how research labs talk themselves into false discoveries.

### C2 — Point-in-time vs. the lake's revision policy

Covered in §2.4(b). Decision needed: revisable data gets a separate
store keyed by `(event_time, observation_time)`; `ParquetStore` stays as
it is for immutable exchange bars. Alternative — generalizing
`ParquetStore` to bitemporal for everything — would touch code that four
paper accounts depend on nightly, for zero benefit on OHLCV. Not worth
the risk.

### C3 — "Database with immutable research history" vs. git

Spec §51/§52 asks for a storage layer with immutable research records.
The project already has one: markdown docs committed to git before
results exist. A SQLite table with an append-only convention is *weaker*
— it is mutable by any process with a file handle, and it is not
diffable in review.

**Recommendation:** hypotheses stay in `docs/hypotheses/*.md`, gaining a
machine-readable YAML front-matter block (id, family, status, maturity
level, predictor, outcome, horizons, bars, related ids). A SQLite index
is *generated* from those docs and from experiment output, and is
disposable/rebuildable at any time. This gives §43 search, §44
contradiction detection, and §31 graph queries without creating a second
source of truth that can drift from the ledger. If the index and the
docs ever disagree, the docs win, and a test asserts they agree.

### C4 — "Extend the existing CLI" — there isn't one

There are six `python -m martex_quant.X` entry points plus ~30 ad-hoc
scripts. There is no unified command surface to extend. Building one is
justified but is new construction, not extension, and it should follow
the existing module convention rather than introducing a `research`
binary.

---

## 4. Proposed architecture

```
src/martex_quant/
  data/
    store/parquet_store.py      (unchanged — immutable exchange bars)
    series/                     NEW: non-OHLCV observations
      schema.py                   4-timestamp model, provenance record
      store.py                    bitemporal store, (event_time, observation_time)
      providers/                  funding, oi, basis, macro, onchain, sentiment
  features/                     NEW: the deterministic transformation layer
    registry.py                   id -> spec, metadata, dependencies, version
    panel.py                      ONE panel builder (replaces 6 copies)
    price.py / xsection.py / derivatives.py / regime.py
  marketstate/                  NEW: MarketState(t), cursor-disciplined
  stats/                        NEW: extracted from 11 scripts
    bootstrap.py                  block bootstrap, CIs
    multiple_testing.py           FDR, family accounting, permutation
    (metrics.py stays where it is — do not move DSR)
  research/
    registry.py                 NEW: derived index over docs/hypotheses
    protocols.py                NEW: exploratory/confirmatory/replication/stress
    relationships.py            NEW: feature -> outcome engine
```

Guarantees the new layers must inherit:

- **Availability filtering is enforced in the data layer, not requested
  by callers.** `MarketState(t)` physically cannot return a value whose
  `availability_time > t`. Same philosophy as `History`.
- **Poison tests** (spec §47) mirror the existing anti-lookahead tests:
  inject a future-derived series, assert the state engine refuses it.
  This is the acceptance criterion for the MarketState layer — not a
  nice-to-have.
- **Every feature is a pure, versioned, deterministic function** with no
  undocumented `fill`/`dropna`/`clip`.

---

## 5. Recommended build order (differs from the spec)

| # | Layer | Why here |
|---|---|---|
| 1 | **Feature registry + one panel builder + `stats/`** | Pays for itself immediately by deleting 6 panel copies and 11 bootstrap copies; zero new data; zero new trials; reduces the risk of the exact alignment bug the ledger already recorded once. |
| 2 | **Statistical/multiple-testing framework + family accounting** | Moved ahead of discovery. Resolves C1 before any sweep can damage the ledger. |
| 3 | **Series store with availability semantics + provenance** | The genuine architectural gap. Brings funding/perp/OI/intraday in from the cold (they are currently 34 bare parquet files with 5 different ad-hoc schemas, outside the catalog, outside validation). |
| 4 | **MarketState engine + poison tests** | Needs 1 and 3. Poison tests are the acceptance gate. |
| 5 | **Relationship engine + horizon profiles** | The first thing that can generate new trials — deliberately after the accounting exists. |
| 6 | **Hypothesis front-matter + derived registry + graveyard search** | Formalizes what the markdown ledger already does. |
| 7 | **Strategy × market-state analysis (spec §29)** | Highest immediate practical value; needs 4. |
| 8+ | Replication/stress engines, anomaly discovery, ML layer, research graph, dashboard, NL search | Only after 1–7 have earned their keep. |

**Deferred deliberately:** the ML layer (§25), the AI research assistant
(§35), the research graph (§31), and natural-language search (§43). Each
is a multi-week project whose value is conditional on layers 1–7
existing and being used. The ledger's own meta-finding 4 applies to
infrastructure too: an impressive capability that does not change a
decision is not an improvement.

---

## 6. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Trial inflation demotes existing findings (C1) | **High** | Family accounting built before discovery; explicit rule written into CLAUDE.md |
| MI becomes a months-long build with zero income impact, while the eval sits unbought and the deployed spec drifts | **High** | Layers 1–4 are ~2 weeks and mostly consolidation; re-decide after layer 4 |
| Post-hoc rationalization of the current −12% paper drawdown as a "regime finding" | **High** | Any strategy×state work must be pre-registered before looking at the drawdown window; the drawdown is 26 marks — far too short for any inference |
| Refactoring breaks the nightly paper path | Medium | Layers 1–3 are additive; `decision.py`, `engine.py`, `multi.py`, `history.py` untouched; full suite green per commit |
| New data sources are unvalidated (no gap/outlier checks today) | Medium | Series store reuses the validate-blocks-write rule |
| Scope creep from the 58-section spec | Medium | Fixed build order; each layer ships with tests and a WHAT/WHY/RISKS summary |

---

## 7. Decisions needed before Layer 1

1. **C1 resolution** — hierarchical families + exploratory/confirmatory
   wall (recommended), or one of the alternatives?
2. **C3 confirmation** — docs stay the source of truth, SQLite is a
   disposable derived index? (recommended)
3. **Scope for now** — layers 1–4 (~consolidation + the real data gap),
   then re-assess? Or a different cut?
4. **Operational** — PROJECT_STATE.md needs a refresh regardless: the
   eval status, the July sprint outcome, and the current paper drawdown
   should be recorded before MI work starts, so the ledger stays honest
   about where the project actually is.
