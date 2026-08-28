# Hypothesis 72 — Point-in-Time Carry: does the last validated edge survive?

Status: **CONFIRMED — carry survives (2026-08-28).** Trials: **+2 → 174.**
Verdict in §8.

**Gate A passes and Gate B passes.** On a point-in-time universe the H63
spec retains **86% of its Sharpe** (5.61 → **4.83**) against momentum's
58%, and all three §5.1 predictions were right. The universe bias in the
*list* is just as large as momentum's — 28-32% overlap in the key years —
and it **matters far less to a harvest edge**, which is now the strongest
evidence for the select/harvest distinction.

**Two things this does not mean.** CAGR retention is only **54%**
(+4.36% → **+2.35%**), so the income halves even though the ratio holds.
And carry still earns **approximately nothing in 2025-2026**, exactly as
§7 said a pass must not be allowed to obscure.

H71 removed the deployed momentum spec from the evaluation path: on a
point-in-time universe it keeps 58% of its Sharpe and clears neither the
Sharpe nor the DSR bar. **Carry is the only other validated edge in the
ledger, and it ranks inside the same hindsight universe.** This applies
the same test to it.

**Committed before any study code exists.** The perp pool was collected
first (`scripts/pull_perp_pool.py`, 2026-08-28), which runs no study and
decides nothing.

**If this fails too, the project has zero validated edges, and that will
be said plainly rather than softened.**

---

## 1. Claim

Carry's measured performance is **not** materially inflated by its
hindsight universe. Re-run with a point-in-time universe, H63's
funding-conditional carry retains most of its Sharpe and still clears the
project's absolute bars.

Note the direction: **this hypothesis predicts survival.** §2 says why,
and §5.1 commits to it before the run.

## 2. Why carry should be far less exposed than momentum was

`OBSERVATION` — **H70 established the distinction, and it was earned the
hard way.** H65 proposed that breadth feeds edges that HARVEST and starves
edges that SELECT; H66 refuted it; H70 supplied the missing half and
found the mechanism is mechanical. Rotation *selects* — it ranks 38 coins
and takes the top 2 — so a universe stuffed with later-famous names hands
it winners it could not have known to pick. Carry *harvests* — it holds
every symbol whose funding is paying, subject only to a trailing filter.

`OBSERVATION` — the supporting measurements. H65: widening carry from 8
to 34 symbols **barely moved it** (Sharpe 5.91 → 5.60). H66: concentrating
carry *hurts* monotonically (K=3 → 2.27, K=5 → 2.99, K=10 → 4.06,
harvest-all → 5.60). A book whose performance is nearly invariant to
*which* symbols it holds should be nearly invariant to a biased list of
them.

`INTERPRETATION` — momentum's bias had an obvious sign: ranking among
known survivors flatters you. **Carry's does not.** Its exposure is that
the funding streams it harvests are *survivor* streams, and the sign of
that is genuinely unclear (§3). That asymmetry is what makes this worth
running rather than assuming.

## 3. When it should fail — and why the direction is not obvious

- **The delisted-perp problem may bite harder here than it did for
  momentum.** Binance delists a perp after the underlying collapses, and
  a delta-neutral carry book is **short the perp**. Through a collapse a
  short perp *gains*; through the squeeze that often precedes delisting
  it loses violently. The missing streams could therefore flatter or
  damn the incumbent, and this study cannot see them either way.
- **Funding on thin new listings is extreme.** A point-in-time selector
  ranking on perp turnover will admit recently-listed contracts whose
  funding swings far more than a major's. That could *raise* measured
  carry — and would be the least trustworthy way to pass.
- **Costs on thin perps.** The flat 10bp + 1bp model is defensible for
  BTC and optimistic for a 2025 listing, on both legs.
- **If carry's Sharpe was itself a diversification artifact** (H66's
  finding), then changing which ~40 streams are averaged should barely
  matter — which is the null this hypothesis predicts.

## 4. Specification

### 4.1 The pool

Every **active USDT-margined Binance perp** (698 at collection), with
daily OHLCV plus quote turnover in `data/perp_pool/` and full 8-hour
funding history in `data/funding_pool/`. Spot legs come from
`data/pool/` — the 469-pair spot pool H71 already collected.

A symbol is **eligible** only if it has all three of spot, perp and
funding. The intersection is reported in §8 before anything is
interpreted.

**These are new directories.** `data/perp/` and `data/funding/` are
fingerprinted byte-for-byte by the frozen goldens for H62–H66 and are not
touched.

### 4.2 Point-in-time selection

Identical in shape to H71 §4.2, ranked on the instrument the book
actually trades:

At each **reselection date**, rank every eligible symbol with at least
`MIN_HISTORY = 90` days of perp bars by **mean daily perp quote volume
over the trailing 30 days**, and take the **top 40**.

- Ranked on **perp** turnover, not spot: a carry book's liquidity
  constraint is the leg it shorts.
- **No legacy-8 union**, for the same reason as H71: unioning a set
  chosen today re-imports the bias under test.
- Size 40 matches H71 and `config/universe.json`, so the two corrections
  are comparable.

### 4.3 The book

**The H63 spec, unchanged** — the deployed carry specification:
delta-neutral (long spot, short perp), **1× collateralized**, always-on
subject to the **trailing-funding filter at L = 30**, daily rebalance,
the project's cost model charged on **both legs**, funding accrued on
real 8-hour settlement stamps, union panel mode (a symbol participates on
the days it exists).

**Nothing about the strategy is varied. Only which symbols it may hold.**

**Incumbents, both recomputed in the same run over the identical window,
never imported:**
- **H65's wide book** — the ~34 hindsight-universe symbols.
- **H63's 8 majors** — the deployed carry spec's own universe.

Two incumbents because H65 and H63 disagree about breadth and the
comparison should not quietly pick the flattering one.

### 4.4 The declared cells — 2 trials, no more

| # | Cell | Purpose |
|---|---|---|
| **1** | **Point-in-time top-40, reselect every 90 days — PRIMARY** | matches H71 |
| 2 | Point-in-time top-40, reselect every 365 days | robustness: churn vs honesty |

Both reported regardless of outcome. **No other parameter is searched** —
not L, not the universe size, not the volume window, not `MIN_HISTORY`,
not the collateralization.

## 5. Pre-registered bars

Judged on the **primary cell**.

**Gate A — does carry survive an honest universe at all?**

1. Sharpe ≥ **1.0**.
2. Mean daily net > 0 with a 95% block-bootstrap CI (30-day blocks)
   excluding zero.
3. `DSR_global` ≥ **0.95** at **N = 174**.

**Gate B — how much of the measured edge was the hindsight universe?**

4. **Point-in-time Sharpe ≥ 70% of the H65 wide book's**, recomputed in
   the same run on the identical window.

> The 70% is the **same tolerance H71 used**, deliberately, so the two
> corrections can be read side by side. It is a judgment call, not a
> statistical threshold.

### 5.1 Predictions recorded in advance

**This hypothesis predicts carry survives**, which is the opposite of
what H71 found for momentum, and the prediction is committed here so a
pass cannot later be dismissed as unsurprising and a failure cannot be
narrated as expected:

- **Gate A passes** — Sharpe stays above 1.0.
- **Gate B passes** — retention above 70%, and materially better than
  momentum's 58%.
- **Overlap between the point-in-time top-40 and the hindsight universe
  is low in early years, similar to H71's 26%** — the bias in the *list*
  is just as large; the claim is that it matters less to a harvest edge.

If retention lands near momentum's 58%, the select/harvest distinction
(meta-finding 14) is wrong or much weaker than H70 concluded, and that
must be recorded as such.

### 5.2 Reported, explicitly NOT gated

Per-year returns for every book; the overlap with the hindsight universe
by year; eligible-symbol counts; the funding-vs-basis-vs-cost
decomposition H62 established; both incumbents' figures; and — carried
forward because it is load-bearing — **the recent-regime result**, since
H62, H63 and H65 each independently found carry earning approximately
nothing in 2025–2026.

## 6. Disposition, declared in advance

- **A + B** → **carry survives.** It becomes the project's only edge
  standing after H71, and meta-finding 14's select/harvest distinction
  gains its strongest evidence. **This still does not make carry
  deployable**: the recent-regime finding stands and is unaffected by
  this test.
- **A passes, B fails** → carry is real but its published figures are
  inflated. Re-state them as H71's were, annotate H62/H63/H65/H66 in
  place, and record that the select/harvest distinction is weaker than
  H70 claimed.
- **A fails** → **the project has no validated edge left.** Carry comes
  off the bench, PROJECT_STATE says so at the top, and the honest
  position becomes that 174 trials have produced infrastructure and
  negative results but nothing deployable. That sentence is written here,
  before the run, so it cannot be softened afterwards.

**No outcome deploys anything.** The paper accounts continue unchanged in
every branch.

## 7. Known limitations, stated before results

- **STILL AN UPPER BOUND, and possibly a more generous one than H71's.**
  Binance lists only perps active today. Contracts delisted after a
  collapse are absent, and a delta-neutral book is short exactly those
  perps through exactly those events. Whether their absence flatters or
  damns the measurement is unknown, which is worse than knowing the sign.
- **Spot and perp pools were collected on different days** (spot
  2026-08-28 for H71, perp 2026-08-28 for this) and both post-date the
  frozen lake. The study window is bounded to the frozen research window
  so figures stay comparable to H62–H66.
- **Funding history depth varies wildly** across a 698-contract pool, and
  new listings enter with the most extreme funding. `MIN_HISTORY = 90`
  blunts this; it does not remove it.
- **The cost model is most optimistic exactly where this hypothesis adds
  symbols** — thin recent perps, on both legs. Inherited verbatim from
  H65 §7 and unchanged.
- **1× only.** No leverage claim is made, and the intraday-liquidation
  limitation from H62 §7 is inherited unchanged.
- **This tests the universe, not carry's economics.** A failure here
  would be about the evidence base, not proof that funding carry does not
  exist.
- **Even a clean pass leaves carry unprofitable today.** H62, H63 and H65
  all found ~0%/yr in the current regime; nothing in this hypothesis
  addresses that, and a Gate A + B pass must not be reported as though it
  did.

---

## 8. VERDICT (2026-08-28, scripts/h72_point_in_time_carry.py, +2 → 174)

**Carry survives the correction that killed momentum.** Gate A passes,
Gate B passes. Pool: 698 perps collected, **342 eligible** (spot + perp +
funding). Common window 2,494 days, 2019-09-11 → 2026-07-09.

### 8.1 Both incumbents reproduce exactly — and so does the filter

`OBSERVATION` — before any pool result existed, the trailing-funding
filter used here was run against H63's own caches and returned **Sharpe
6.00, CAGR +4.51%, MDD −0.51%** on 2,124 days — H63's published figures
to the digit. The reproduce-first guard passed first.

`OBSERVATION` — in this run, on pool data:

| Book | this run | published |
|---|---|---|
| hindsight wide (H65) | 5.61 / +4.36% | **5.60 / +4.36%** |
| hindsight 8 majors (H63 incumbent) | 5.91 / +4.64% | **5.91 / +4.64%** |

`INTERPRETATION` — the broad pool reproduces the original caches, and the
filter reproduces the published spec. The only thing that differs between
arms is which symbols may be held.

### 8.2 The cells

| Book | CAGR | Sharpe | MDD | mean bp/day | 95% CI (bp) | DSR@174 |
|---|---|---|---|---|---|---|
| hindsight wide (H65) | +4.36% | **5.61** | −0.78% | +1.170 | [+0.689, +1.761] | 1.0000 |
| hindsight 8 majors (H63) | +4.64% | 5.91 | −0.84% | +1.242 | [+0.792, +1.787] | 1.0000 |
| **point-in-time 90d — PRIMARY** | **+2.35%** | **4.83** | **−0.35%** | **+0.637** | **[+0.309, +1.048]** | **1.0000** |
| point-in-time 365d | +1.82% | 4.02 | −0.33% | +0.495 | [+0.202, +0.871] | 1.0000 |

### 8.3 The bars

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | Sharpe ≥ 1.0 | **4.83** | **PASS** |
| A2 | mean > 0, CI excludes zero | +0.637bp, low +0.309bp | **PASS** |
| A3 | DSR ≥ 0.95 @174 | 1.0000 | **PASS** |
| B4 | Sharpe ≥ 70% of H65 wide's | 4.83 vs 3.93 needed | **PASS** |

**Sharpe retained: 86%. Momentum retained 58% (H71).**

### 8.4 The prediction was right, and that is the finding

`OBSERVATION` — §5.1 committed, before the run, to carry surviving where
momentum did not, with retention "materially above momentum's 58%". All
three predictions hold: Gate A passes, Gate B passes, retention **86%**.

`OBSERVATION` — **the bias in the list is just as large.** Overlap between
the point-in-time top-40 and the hindsight universe:

| Reselection | overlap |
|---|---|
| 2020-12-04 | 11 / 40 (28%) |
| **2021-11-29** | **13 / 40 (32%)** |
| 2022-11-24 | 13 / 40 (32%) |
| 2023-11-19 | 14 / 40 (35%) |
| 2024-11-13 | 17 / 40 (42%) |
| 2025-11-08 | 21 / 40 (52%) |

These are the same numbers H71 found for momentum (28% in 2020, 32% in
2021, rising monotonically to the snapshot date). **The universes are
equally contaminated. The edges are not equally damaged.**

`INTERPRETATION` — this is the **strongest evidence yet for the
select/harvest distinction** (meta-finding 14), and it arrives as a
prediction confirmed rather than a pattern noticed afterwards. Rotation
*ranks* and takes the top 2, so a pool stuffed with later-famous names
hands it winners it could not have known to pick — 42% of its Sharpe.
Carry *holds everything paying*, so a biased list changes which ~40
streams get averaged and little else — 14% of its Sharpe.

The distinction has now been proposed (H65), refuted (H66), rebuilt from
the opposite direction (H70), and used to make a correct out-of-sample
prediction (here). **It is no longer a speculation.**

### 8.5 What the pass costs: the income halves

`OBSERVATION` — retention is **not** uniform across metrics:

| | hindsight wide | point-in-time | retained |
|---|---|---|---|
| Sharpe | 5.61 | 4.83 | **86%** |
| CAGR | +4.36% | **+2.35%** | **54%** |
| MDD | −0.78% | **−0.35%** | **better** |

`INTERPRETATION` — Gate B was declared on Sharpe and it passes cleanly,
but **the CAGR nearly halves and that is what an income project actually
spends.** The ratio survived; the money did not survive as well. Reported
here rather than buried because the Sharpe headline alone would mislead.

`OBSERVATION` — drawdown **improves**, −0.78% → −0.35%.

`INTERPRETATION` — consistent with H66: carry's Sharpe is a
diversification property. The point-in-time book rotates through a wider
set of streams over time, and averaging more near-independent funding
streams cuts variance. The same mechanism that made carry robust to the
universe correction also makes it shallower.

### 8.6 Per-year, and the caveat §7 insisted on

| Year | hindsight wide | 8 majors | **point-in-time 90d** |
|---|---|---|---|
| 2019 | +1.49% | +1.49% | −0.26% |
| 2020 | +6.17% | +6.90% | +3.94% |
| **2021** | **+16.72%** | +15.95% | **+10.64%** |
| 2022 | −0.14% | −0.01% | −0.20% |
| 2023 | +1.96% | +2.49% | +0.56% |
| 2024 | +4.48% | +4.89% | +1.09% |
| **2025** | −0.07% | +0.63% | **−0.05%** |
| **2026** | −0.80% | −0.64% | **−0.07%** |

`OBSERVATION` — **2025 and 2026 are approximately zero in every arm.**
That is the fourth and fifth independent confirmation, after H62, H63 and
H65, that carry earns nothing in the current regime.

`INTERPRETATION` — §7's last limitation was written precisely to stop a
Gate A + B pass being read as good news about income. **It is not.** What
this hypothesis establishes is that carry's *historical* edge is real and
survives an honest universe. It establishes nothing whatever about
whether that edge is being paid today, and the evidence on that question
remains uniformly negative.

### 8.7 Still an upper bound, and here the sign is unknown

`OBSERVATION` — §7's first limitation stands: Binance lists only perps
active today, so contracts delisted after a collapse are absent.

`INTERPRETATION` — for momentum, H71 could at least say the missing
streams were probably *unfavourable* to the honest book, so the
correction was conservative. **Here the sign is genuinely unknown.** A
delta-neutral book is short the perp: through a collapse it gains,
through the squeeze that often precedes delisting it loses violently.
Whether the missing contracts would raise or lower 4.83 cannot be
determined from this data, and no claim is made either way. That is the
weakest part of this verdict and it is not fixable without paid
point-in-time data.

### 8.8 Where this leaves the project

`OBSERVATION` — after H71 and H72, the ledger has **exactly one validated
edge that survives an honest universe**: carry, at Sharpe 4.83 / CAGR
+2.35% point-in-time, DSR 1.0000 at 174 trials.

`INTERPRETATION` — the §6 branch that would have said *"the project has
no validated edge left"* is **not** the one that fired, and that matters.
But the position is narrow and should be stated without decoration:

- **One edge, not eight.** `family-expansion-program.md` §2's arithmetic
  needs eight uncorrelated edges; there is one.
- **It is real, robust, and currently unpaid.** ~0%/yr in 2025-2026.
- **It is not deployed and this hypothesis does not deploy it.** Paper
  accounts continue unchanged.
- **The correction cost half the CAGR**, so any future sizing arithmetic
  must use +2.35%, not +4.36%.
