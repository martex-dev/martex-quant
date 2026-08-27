# Hypothesis 72 — Point-in-Time Carry: does the last validated edge survive?

Status: **PRE-REGISTERED 2026-08-28. NO RESULT EXISTS.** Trials declared:
**+2 → 174.** Verdict will be written into §8 and nowhere else.

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

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
