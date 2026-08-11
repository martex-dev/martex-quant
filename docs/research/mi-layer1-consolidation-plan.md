# MI Lab Layer 1 — Consolidation Plan & Semantic-Difference Audit

Date: 2026-08-10. Status: **PLAN — for review. No code changed yet.**
Scope: consolidate the duplicated analytical machinery found in the
repository audit into canonical, regression-tested infrastructure.
Treated as **research integrity work**, not cleanup: these duplicates are
where a silent divergence would corrupt the ledger.

---

## 0. The decisive enabling finding

All 13 research scripts were executed today against the current
repository state:

| Script | Runtime | Result |
|---|---|---|
| h53_killtest | <1s | rc=0 |
| h08, h09, h10, h11, h22_h23 | 1s each | rc=0 |
| v2_m1, h13_h14 | 2s each | rc=0 |
| h44_50 | 4s | rc=0 |
| h33_40 | 5s | rc=0 |
| h15_21 | 6s | rc=0 |
| h52_55_57 | 7s | rc=0 |
| h24_32 | 10s | rc=0 |

**~40s for the whole corpus.** Output is byte-identical across repeated
runs (verified on h24_32, h33_40, h44_50), and reproduces published
ledger figures exactly — e.g. H53 prints
`-0.0187% CI [-0.0280%, -0.0080%]`, character-identical to
docs/hypotheses/52-57-intraday-frontier.md; H11 prints +0.823% / +1.021%
against the ledger's "+0.8–1.0%/wk"; H40 prints −8.77% against the
ledger's −8.77%.

This is possible because the inputs are frozen: the lake's last write was
2026-07-11, `config/universe.json` is dated 2026-07-12, and the funding /
perp / intraday caches are static files.

**Therefore golden-output regression is available, cheap, and exact.**
That is a far stronger guarantee than unit-testing the new functions: it
proves the refactor changed nothing that any published verdict rests on.
It is the backbone of this plan.

---

## 1. Semantic-difference audit

This is the part that matters. Consolidation is dangerous precisely
because these implementations *look* interchangeable and are not.

### 1.1 Block bootstrap — 16 definitions across 11 files, 4 distinct estimators + 2 one-offs

| Shape | Implementations | Estimator |
|---|---|---|
| **A — two-group difference over day-aggregated sums/counts** | h15_21 `diff_ci`, h33_40 `diff_ci`, h13_h14 `diff_ci(col_a,col_b)`, h22_h23 `day_diff_ci(block)`, h44_50 `diff_ci`, h08 `pooled_diff_ci`, h10 `pooled_diff_ci`, h09 `bootstrap_diff` | mean(a) − mean(b), observation-weighted |
| **B — unweighted mean of a per-day series** | h15_21 `mean_ci`, h24_32 `mean_ci`, h11 `bootstrap_mean`, h22_h23 `block_mean_ci(block)` | mean of daily values |
| **C — event mean pooled by day** | h33_40 `event_mean_ci`, h44_50, h52_55_57, h53 | event-count-weighted mean |
| **D — flag-split raw resample** | v2_m1 `block_bootstrap_ci(values, flags)` | mean(flagged) − mean(unflagged) |
| **one-off** | h13_h14 `h14()` inline bootstrap | signed mean, no prefix arrays |

#### Differences that would silently change published numbers

**(1) The RNG draw sequence is part of the answer.** Every CI is a
deterministic function of `random.Random(seed)` plus the exact order and
count of `randint` calls. The contract in every implementation is
`n_blocks = n // BLOCK + 1`, one `randint` per block, per bootstrap
iteration, in that nesting. Vectorizing the draws, pre-generating index
arrays, or reordering the loops changes **every** published CI while
looking like a pure refactor. *Invariant: the RNG contract is frozen.*

**(2) The percentile index depends on how many draws were rejected.**
Shapes A and C append to `diffs`/`means` only when the denominators are
positive; the CI is then `sorted[int(0.025 * len(list))]`. Making the
guard unconditional — or adding one where none exists — shifts the
selected index and moves the bounds.

**(3) Shapes B and C are different estimators wearing similar names.**
- B: `cnt += BLOCK_DAYS` → **unweighted** mean over days; assumes exactly
  one value per day.
- C: `cnt += pn[e] - pn[s]` → **event-count-weighted** mean; handles many
  events per day.

  On any panel with a varying number of events per day these give
  different **point estimates**, not merely different CIs. They must stay
  separate functions. This is the single most dangerous merge available.

**(4) Block length is not a constant.** 30 days almost everywhere,
**60** in v2_m1 (chosen to cover a 30-day horizon's autocorrelation),
**10** in H22's held-day test. A canonical `BLOCK_DAYS = 30` would
silently change two published results. *Block must be an explicit
parameter at every call site.*

**(5) `max(denominator, 1.0)` guard is present in h10, absent in h08**,
in otherwise-identical functions. No numeric difference on real data
(counts are positive); different behavior on empty input
(ZeroDivisionError vs 0.0). Unifying changes failure modes only — but it
must be a deliberate, recorded choice.

**(6) `randint(0, n - BLOCK)` vs `randint(0, max(n - BLOCK, 0))`.**
Verified: `randint(0, -1)` raises ValueError; `randint(0, 0)` returns 0.
So short series either crash (h15_21, h24_32, h33_40, h11, h13_h14) or
silently degenerate to a single fixed block (h44_50, h52_55_57, h53). No
difference where n ≥ block, which holds for all current data.

**(7) NaN fallbacks differ.** h22_h23 returns NaN when `n <= block*2`;
h13_h14's inline returns NaN when `n <= BLOCK_DAYS`; the rest have none.

**(8) Point estimates are computed three ways** — prefix-array
subtraction, `sum(values)/n`, and `statistics.fmean` — which differ in
float summation order at ~1e-16. Displayed values are safe at 2–4
decimals, but CI bounds are chosen by integer index into a sorted list,
so in principle two adjacent bootstrap draws could reorder. *Do not
"improve" the summation method.* Golden tests will catch it if it moves.

**(9) Verified safe to unify:** `pl.col(v).count()` and
`pl.col(v).is_not_null().sum()` are equivalent in polars 1.42.1 (both
exclude nulls; `.len()` does not). Checked empirically, not assumed.

### 1.2 Panel builders — 6 variants

| Script | Universe | Distinctive columns | Terminal `drop_nulls` | Missing-symbol policy |
|---|---|---|---|---|
| h08 | legacy 8 | funding, pct, fwd1/7/30 | `["pct","fwd7"]` | n/a (join) |
| h10 | legacy 8 | perp_close, basis, pct, fwd1/7/30 | `["pct","fwd7"]` | n/a (join) |
| h13_h14 | legacy 8 | vol30, vol10, vol10_pct, fwd1/3/7 | `["ret","vol30","fwd7"]` | propagates FileNotFoundError |
| h15_21 | universe 40 | r7/r14/r30, vol10, ma90, peak365, v7, v30, fwd1/7/30 | none | skips on FileNotFoundError |
| h24_32 | universe 40 | r90, r90skip7, vol90, max365, maxret30, illiq30, vshock, upshare90, beta, resmom90, hi52, riskadj | none | skips |
| h33_40 | universe 40 | r30/r90/r180, hi30, tr, atr14, fwd7/30 | none | skips |

**(10) `vol` is defined two incompatible ways under near-identical names.**
- `ret.shift(1).rolling_std(w)` — **excludes** the current bar
  (h13_h14 vol10/vol30, h15_21 vol10, h22_h23 vol30, h52 sizing).
- `ret.rolling_std(90)` — **includes** the current bar (h24_32 `vol90`).

  Both are legitimate — day *t*'s return is known at *t*'s close, so
  neither is lookahead — but a single canonical `volatility(window)`
  would silently change H24 (`riskadj = r90/vol90`) and H27 (low-vol
  ranking). *They must remain two distinctly named features.*

**(11) `drop_nulls` placement changes `n` and therefore the bootstrap.**
Three builders drop inside; three leave it to each test. Because the
bootstrap aggregates by day, dropping earlier can remove whole days and
change the day-block resample, not just the sample size.

**(12) All `shift()` / `rolling_*()` run per-symbol *before* concat.**
This is what makes them correct, and it was verified across all six —
the only post-concat window use is h15_21's `vol10_ago`, which correctly
qualifies with `.over("symbol")`. *The canonical builder must keep the
per-symbol loop. Do not "optimize" it into `.over()` on a concatenated
frame.*

**(13) h24_32 alone joins BTC** to compute rolling beta and residual
momentum; its panel is not a superset or subset of the others.

### 1.3 Forward returns — 11 files, one formula, three conventions

**(14)** The formula is universally `close.shift(-h) / close - 1.0` — no
divergence found. What differs:
- **Horizon units are frame-dependent**: `h` counts days on 1d frames and
  15-minute bars on intraday frames (`fwd8` = 2h, `fwd1h` = 4 bars,
  `fwd15` = 1 bar).
- **v2_m1 uses a relative forward return** (`btc_fwd − alt_fwd`), not a
  plain one.
- **Signing by event direction** (`when(z>0).then(fwd).otherwise(-fwd)`)
  is hypothesis logic, not feature logic, and stays in the study.

*A canonical helper must be unit-agnostic — `(frame, horizon_bars,
price_col)` — and must not absorb the signing.*

---

## 1.4 Step 0 findings (added 2026-08-10, after freezing)

Freezing the baseline surfaced three things the plan above did not anticipate.
All three are recorded rather than fixed, per the no-opportunistic-cleanup rule.

### (a) The baseline scope was wrong: 13 scripts → 30

The plan covered only the scripts that use the duplicated machinery. The
integrity test `test_every_research_script_has_a_spec` failed on its first
run and exposed **17 further research scripts with no regression cover** —
including the five strategy-grade studies that produce the ledger's most
important numbers.

The baseline now covers the **entire research corpus (30 scripts)**, because
the acceptance criterion is "no ledger value changed" and those *are* the
ledger values. Verified reproductions include:

| Script | Reproduced exactly |
|---|---|
| h41_h42_fub1_studies | rotation+stop DSR **0.992**, Sharpe **1.47**, MDD **−29.0%**, prop@0.5x **73.0%**; V1+stop DSR 0.744 |
| h43_combo_study | 43a Sharpe **1.55**, CAGR **+79.0%**, DSR **1.000**; corr **0.118 / 0.521 / 0.821** |
| h53_killtest | **−0.0187%**, CI **[−0.0280%, −0.0080%]** |
| h33_40_killtests | H40 stop signal **−8.77%** |
| h11_rotation_killtest | **+0.823% / +1.021%** |

Excluded, deliberately and by name: `pull_frontier`, `pull_intraday`
(network fetchers), `dashboard_service`, `freeze_research_baseline`.

### (b) A genuine reproducibility defect in a published study

`scripts/adaptive_sizing_study.py:92` seeds its Monte Carlo with
`random.Random(hash(name) % 100_000)`. CPython randomises `hash(str)` per
process, so **this study has never been reproducible**. Three consecutive
runs gave static-0.85x pass rates of 61.5% / 62.4% / 61.7% — roughly ±0.5pp
drift on every figure it published.

Handling, per the standing rule:

1. **Preserved** — the script is not modified. (Note the rule's first clause
   cannot be honoured literally here: there is no stable historical behaviour
   to preserve.)
2. **Documented** — recorded in `REPRODUCIBILITY_DEFECTS` in
   `trading_bot.research.baseline`, and surfaced in the fingerprint of that
   script so it can never be quietly forgotten.
3. **Correction candidate** — take an explicit seed parameter. Requires its
   own pre-registration; it will change the published digits.
4. **Historical result untouched.**

The baseline runner pins `PYTHONHASHSEED=0`, which makes the script
deterministic **going forward**. This is an environment decision recorded in
the environment fingerprint, not a code change. Its golden is therefore a
*forward-looking* baseline, not a reproduction of history — the only golden
in the set with that caveat.

Scope of the damage: the qualitative conclusion this study supports
("adaptive sizing does not beat the static frontier") is stable across seeds
— the gap between adaptive up=1.25 (~52%) and static 0.85x (~62%) is ~20×
the observed drift. The exact digits are not reproducible. `hash()` is used
nowhere else in the repository (verified).

### (c) Derived caches are inputs

`data/tmp/h4x_streams/*.parquet` are equity streams **produced** by
`h41_h42_fub1_studies` and **consumed** by h43, h51, h52 and all five sprint
studies. They are gitignored computed artifacts sitting in the input path of
eight scripts. If they were deleted, the producers would recompute them —
but nothing verifies that a recomputed stream matches the one the consumers
were validated against. They are fingerprinted; the coupling is recorded as
a fragility, not fixed.

### (f) Baseline classification: 29 deterministic goldens + 1 time-dependent script

**The 30-script corpus contains 29 deterministic golden targets plus one
script containing a time-dependent external-data component.** That one
script is not a failed refactor and must never be counted as one.

Finding (e) below is a *baseline classification* problem, not a code
failure. The registry now declares, per script, what kind of
reproducibility it actually has:

| Class | Meaning | Scripts |
|---|---|---|
| `deterministic` | same inputs → same stdout, forever; the golden IS a historical reproduction | 28 |
| `non_deterministic_pinned` | the script itself is not reproducible; pinning the environment stabilises it GOING FORWARD; gated, but never described as reproducing history | 1 (`adaptive_sizing_study`) |
| `time_dependent` | output moves with wall-clock time and/or a live fetch; run and audited, inputs fingerprinted, but deliberately NOT stdout-gated | 1 (`phase3_studies`) |

`ScriptSpec` carries `reproducibility` and `external_dependencies`; the
fingerprint records both. Tests enforce the honesty rather than trusting
it: a `time_dependent` script must declare its dependencies and **must not
own a golden file**, and a `non_deterministic_pinned` script must appear in
`REPRODUCIBILITY_DEFECTS`.

The 2026-08-10 capture is preserved as evidence at
`tests/golden/archive/phase3_studies.2026-08-10.out`, with a README stating
exactly why it cannot serve as a permanent fixture. It was not deleted and
not regenerated.

The carry window was **not** pinned and the fetch was **not** switched to a
cache. Either would alter the methodology and could move published carry
figures; that requires its own pre-registration.

### (e) A second reproducibility defect, surfaced by the calendar (2026-08-11)

`scripts/phase3_studies.py:184` anchors the H05 carry sub-study's funding
fetch to `datetime.now(tz=UTC) - 4 years` **and** pulls live from Binance.
Its window therefore slides by one day every day.

The baseline was frozen 2026-08-10. On 2026-08-11 the golden failed:

- **5 of 100 lines changed**, all in the carry section (lines 92–96).
- The window `2022-08-11..2026-08-10` became `2022-08-12..2026-08-11`.
- One derived figure moved: DOGE annualized carry **7.87% → 7.86%**.
- **Lines 1–91 — Studies 2–7 (daily TSMOM, vol-filter, mean reversion,
  vol-target, Donchian) — are byte-identical.**

Not caused by Step 2: `git diff` for that file is empty, and it does not
use the panel builders. The golden suite caught a pre-existing defect on
its first calendar rollover, which is what it is for.

Handling, per the standing rules: **documented, not fixed, and the golden
was NOT regenerated.** Pinning the carry window to explicit dates and a
cache (as h08/h10 already do for funding) would change the published carry
figures, so it needs its own pre-registration. Recorded in
`REPRODUCIBILITY_DEFECTS`. The decision on how to treat this fixture is the
user's, not a refactor side effect.

### (d) The golden suite cannot run in CI

`.gitignore` excludes `/data/` entirely, so GitHub Actions has no market
data and **every golden test skips there**. The suite is a **local** gate.
The acceptance criterion "CI passes" therefore means "lint, format, mypy and
the 228 unit tests pass in CI" — the golden gate is verified locally and its
result reported. The skip fires only when inputs are *entirely absent*; data
that is present but *changed* is a hard failure, never a skip.

---

## 1.5 The metric for this layer is semantic equivalence, not line count

Step 1 replaced 454 lines of duplicated bootstrap code with a 335-line
canonical module. **That reduction is incidental and is not a success
metric for this project.** It is recorded here only to prevent it from
being read as one.

The metric is: every published number reproduces exactly, and every
historical semantic difference is visible in an explicit parameter. A
future layer that grows total line count while making semantics harder to
confuse is a better outcome than one that shrinks it by collapsing
distinctions. Never optimise a layer for line-count reduction at the
expense of explicit historical semantics.

---

## 2. Implementation plan

**Governing rule for the whole layer: parameterize, never normalize.**
Where implementations differ, the canonical function grows a parameter
and each call site passes its historical value. We do not decide which
variant was "right"; that would change history. Any judgement that one
variant is wrong becomes a separate, pre-registered correction.

### Step 0 — Freeze the baseline (no source changes)

1. Capture stdout of all 13 scripts to `tests/golden/<script>.txt`.
2. Record an input fingerprint (catalog hash + hashes of the funding /
   perp / intraday caches + universe.json) alongside them.
3. Add `tests/test_research_golden.py`: re-runs each script, asserts
   byte-identical stdout, and **fails loudly** (never skips silently) if
   the input fingerprint has changed.
4. Mark slow, run in CI. Budget ~40s.

**Committed before any refactor**, so the safety net predates the change.

### Step 1 — `src/trading_bot/stats/bootstrap.py`

Four public functions, one per estimator shape, all with explicit
`block`, `seed`, `n_boot` (no hidden defaults), plus one private
`_resample_blocks` that owns and documents the RNG contract:

- `day_diff_ci(...)` — Shape A
- `daily_mean_ci(...)` — Shape B (unweighted)
- `event_mean_ci(...)` — Shape C (count-weighted)
- `flag_split_ci(...)` — Shape D

Tests: determinism under fixed seed; an explicit **RNG-contract test**
asserting the exact number of draws consumed; degenerate-input behavior
for each variant; and a hand-computed fixture with a tiny series.

### Step 2 — Migrate scripts one at a time, golden test after each

Order: h11, h09, h53 (single-estimator, smallest) → Shape A family
(h08, h10, h13_h14, h15_21, h22_h23, h33_40, h44_50) → Shape C
(h52_55_57) → v2_m1 last (most divergent).

**A golden diff is a stop-and-investigate event, never an accepted
update.**

### Step 3 — `src/trading_bot/features/panel.py`

`daily_panel(store, symbols, *, features, drop_nulls=None)` — per-symbol
build then concat. Features are named, versioned, individually
requestable specs, so `vol_excl_current(90)` and `vol_incl_current(90)`
are distinct names and difference (10) can never recur. Scripts migrate
with their historical feature sets and null policies preserved verbatim.

### Step 4 — `forward_return(frame, horizon_bars, price_col)`

Unit-agnostic helper in `features/`; migrate the 11 sites. Signing stays
in the studies.

### Step 5 — Verify

Full suite (228 existing + new), all 13 goldens byte-identical, `ruff
check`, `ruff format --check`, `mypy` strict. Note: `mypy` is configured
with `packages = ["trading_bot"]`, so `scripts/` is not type-checked
today; logic moving into `src/` gains strict typing as a side benefit
(verified: scripts pass mypy when checked explicitly, so no surprises).

### Explicitly NOT in Layer 1

No FDR/multiple-testing code (that is Layer 2). No new data sources. No
changes to `decision.py`, `engine.py`, `multi.py`, `history.py`. No
changes to any hypothesis document, verdict, or ledger entry. No
"improvements" to any estimator.

---

## 3. Risks

| Risk | Mitigation |
|---|---|
| Golden tests silently invalidated by a future data refresh | Input fingerprint recorded; mismatch fails loudly with an explicit message, never skips |
| The refactoring instinct "fixes" a variant mid-migration | Governing rule: parameterize, never normalize. Golden diff = stop |
| Shapes B and C merged by accident | They are separate public functions with docstrings stating the weighting difference; a unit test asserts they disagree on a multi-event-per-day fixture |
| Float summation reordering moves a CI bound | Golden tests are byte-exact; summation method preserved per shape |
| Scope creep into Layer 2 | Layer 1 adds no new statistics — only extraction of existing ones |

---

## 4. Definition of done

1. `tests/golden/` holds 13 byte-exact baselines with an input fingerprint.
2. `stats/bootstrap.py` and `features/panel.py` + `forward_return` exist,
   unit-tested, strictly typed.
3. All 13 scripts import canonical implementations; **zero golden diffs**.
4. Full suite green; ruff, format, mypy clean.
5. Duplicate counts: 6 panel builders → 1; 16 bootstrap definitions → 4;
   11 forward-return definitions → 1.
6. No hypothesis document, verdict, or ledger entry modified.
