# Hypothesis 66 — Cross-Sectional Carry (top-K funding)

> **⚠ RE-STATED 2026-08-28 by H72 (`docs/hypotheses/72-point-in-time-carry.md`).**
> The figures below rank inside `config/universe.json`, selected by volume
> **as of 2026-07-12 — the end of the sample**. Re-run on a point-in-time
> universe the carry spec **survives**, retaining **86% of its Sharpe
> (5.61 → 4.83)** — but only **54% of its CAGR (+4.36% → +2.35%)**.
> **Use +2.35%, not +4.36%, in any sizing arithmetic.**
> The numbers below are NOT altered; read them as hindsight-universe
> figures. Carry remains **unpaid in the current regime** (~0%/yr in
> 2025-2026) and is **not deployed**.


Status: **STANDALONE-VIABLE (2026-08-27) — selection LOSES to harvesting.**
Trials: **+3 → 147.** Verdict in §8. Monotone in K: 2.27 / 2.99 / 4.06 vs
harvest-all 5.60. **H65 §8.1's select/harvest refinement is REFUTED.** An
implementation defect in the first run was found and corrected (§8.1).

Direct test of the refinement proposed in
`docs/hypotheses/65-wide-universe-carry.md` §8.1: **breadth feeds edges
that SELECT and dilutes edges that HARVEST.**

**Committed before any study code exists.** No result exists at the time of
writing.

---

## 1. Claim

H63 and H65 both **harvest**: they hold every symbol whose own trailing
funding is positive. H65 showed that widening the harvest from 8 to 34
symbols made it *worse* (Sharpe 5.91 → 5.60), because the marginal symbol
is a thin listing paying near zero.

If the H65 refinement is right, the fix is not fewer symbols — it is
**selection**. Rank all 34 symbols by trailing funding each day and
harvest carry on only the **richest K**. Breadth then works the way it
works for rotation: 34 candidates to choose 5 from is strictly better than
8 candidates to choose 5 from.

**Prediction, stated before the run:** top-K on 34 symbols beats
harvest-all on 34 symbols (H65), and should also beat the 8-symbol harvest
(H63).

## 2. Why the edge should exist

Funding is **dispersed**, not uniform. On any given day some perps are
heavily crowded long and pay richly; others sit near zero. A harvest book
earns the *average* of everything paying. A selection book earns the
*top* of the distribution, and dispersion is what makes that difference
large.

The economic story is unchanged from H62 — you are still selling insurance
to leveraged longs — but you are now selling it only where the premium is
highest, which is where crowding is most extreme.

## 3. When it should fail

- **If dispersion is small**, top-K earns roughly the average and the
  selection buys nothing while concentrating risk into fewer names.
- **If rich funding is a warning rather than a payment.** The most crowded
  coin is also the most squeeze-prone, and a squeeze damages the short
  perp leg exactly when funding is highest. Selecting *for* rich funding
  may be selecting *for* tail risk. This is the most plausible failure
  mode and it will show up as drawdown, not as mean.
- **If concentration undoes the diversification** that makes the carry
  book's Sharpe high in the first place — K=3 across 3 names is a much
  less diversified book than 20 names.

## 4. Specification

**Identical to H65** — same 34-symbol universe, union panel mode, 1×
collateralization, daily rebalance, the project's cost model on both legs,
funding accrued on real 8-hour stamps — with exactly one change:

> **The hold rule becomes cross-sectional.** On each day, rank every
> available symbol by its **trailing 30-day mean funding measured through
> t−1**. Hold delta-neutral carry on the **top K** by that rank, and only
> if that symbol's own trailing mean is also **positive**. Hold nothing
> else. Capital is split equally across the symbols actually held; unused
> capital sits in cash at zero.

The positive-funding condition is retained from H63 deliberately: without
it, a K-th ranked symbol with negative funding would be held and would pay
out, which is not the hypothesis.

**Grid: `K ∈ {3, 5, 10}`. Three cells, all reported. 3 trials.**
Primary cell nominated **now: K = 5.**

**`L` is fixed at 30 and is NOT re-tuned.** It is inherited from two
independent plateaus already measured — H63 (Sharpe 5.00 / 6.00 / 5.89
across L = 7/30/90) and H65 (4.23 / 5.60 / 5.71). Re-running the L grid
here would spend trials re-confirming a settled result.

## 5. Pre-registered bars

**Gate A — is it an edge at all?**

1. Mean daily net > 0, 95% block-bootstrap CI (30-day blocks) excluding zero.
2. Net CAGR ≥ 2%/yr after all costs.
3. Sharpe ≥ 1.0.
4. `DSR_global` ≥ 0.95 at N = 147.

**Gate B — does selection beat harvesting?** Both incumbents recomputed in
the **same run on the same window**, per the FU-B1 rule:

5. **Sharpe > the 34-symbol harvest book (H65 spec).** This is the direct
   SELECT-vs-HARVEST test and the whole point of the hypothesis.
6. **Sharpe > the 8-symbol harvest book (H63 spec).** Beating the deployed
   carry spec is what would make this deployable.

**Gate C — is it still independent, and did concentration break it?**

7. **|correlation| with rotation-stop < 0.30.**
8. **MDD no worse than 3 percentage points** versus the 34-symbol harvest
   book on the same window. Concentration into the most-crowded names is
   the §3 failure mode; this bar is what detects it, and it is set now,
   before any drawdown is seen.

## 6. Disposition, declared in advance

- **A + B + C** → selection beats harvesting; replaces H63 as the carry
  spec, paper-eligible, and **meta-finding 3's refinement is confirmed**.
- **A + C, bar 5 fails** → **STANDALONE-VIABLE**, and the §8.1 refinement
  is **wrong**: selection does not beat harvesting for carry, so breadth's
  select/harvest distinction does not explain H65. That is a more
  interesting negative than a plain kill and must be recorded as such.
- **A + B, bar 8 fails** → **STANDALONE-VIABLE**. The return improved and
  the risk got worse; §3's squeeze story is the likely mechanism. Not
  deployed without a re-registered risk study.
- **A fails** → **KILLED.**

## 7. Known limitations, stated before results

- **Concentration is not modelled as a capacity constraint.** K = 3 on a
  small alt means a large notional in a thin book; the flat cost model
  does not charge for that, and the real fill would be worse.
- **The squeeze tail is under-modelled.** Perp data is daily closes, so an
  intraday squeeze on a crowded name — precisely what top-K selects for —
  is invisible. This limitation binds *harder* here than in H62/H63
  because the selection deliberately concentrates into crowded names.
- **Survivorship**, unchanged: delisted perps are absent, and delisting
  correlates with the collapses that would hurt a short-perp book most.
- **The recent regime is thin.** H62, H63 and H65 all measured ~0%/yr over
  the last 365 days. Selection may improve the full-sample figure without
  changing that, and the verdict must report the recent window separately.
- **1× only**; the H62 §7 intraday-liquidation caveat is inherited.

---

## 8. VERDICT (2026-08-27, scripts/h66_cross_sectional_carry_study.py, +3 → 147)

**STANDALONE-VIABLE.** Gate A passes, Gate B **fails**, Gate C bar 8
**fails**. Shared window 2019-09-11 → 2026-07-09, both incumbents
recomputed in the same run.

| Book | Sharpe | CAGR | MDD |
|---|---|---|---|
| K = 3 | 2.27 | +2.99% | **−7.65%** |
| **K = 5 (primary)** | **2.99** | **+3.50%** | **−5.52%** |
| K = 10 | 4.06 | +3.93% | −4.17% |
| harvest-all, 34 sym (H65) | **5.60** | +4.36% | −0.76% |
| harvest-all, 8 sym (H63) | **5.91** | **+4.64%** | −0.84% |

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | CI excludes zero | +0.263 bp low | **PASS** |
| A2 | CAGR ≥ 2%/yr | +3.50% | **PASS** |
| A3 | Sharpe ≥ 1.0 | 2.99 | **PASS** |
| A4 | DSR ≥ 0.95 @147 | 1.0000 | **PASS** |
| B5 | Sharpe > harvest-34 (5.60) | 2.99 | **FAIL** |
| B6 | Sharpe > harvest-8 (5.91) | 2.99 | **FAIL** |
| C7 | \|corr\| rot-stop < 0.30 | +0.0076 | **PASS** |
| C8 | MDD within 3pt of −0.76% | −5.52% | **FAIL** |

### 8.1 An implementation defect was found and corrected before recording

`OBSERVATION` — the first run of this study produced K=5 CAGR **+1.29%**
and failed Gate A. That run was **wrong** and its numbers are void.

The engine divided capital by the symbols *present* that day, which is
correct for a harvest rule (§4 of H63: a gated-off symbol leaves its share
in cash) but **contradicts this hypothesis's own specification**, which
says *"capital is split equally across the symbols actually held."* Under
the defect a K=5 book deployed 5/34 of capital and was measured mostly on
idle cash.

Fixed by adding an explicit `allocate_over` setting to `CarryConfig`,
defaulting to the harvest behaviour so **no existing result moves** —
verified: `test_carry.py` and the h62 / h63 / h65 goldens all re-run
byte-identical. The figures above are from the corrected run.

`INTERPRETATION` — recorded rather than quietly fixed because the defect
would have produced a *kill* on a hypothesis that actually clears Gate A.
A specification that the implementation silently contradicts is the
failure mode pre-registration exists to catch, and here the registration
caught the code, which is the right way round.

### 8.2 The finding: the H65 refinement is REFUTED

`OBSERVATION` — `docs/hypotheses/65-wide-universe-carry.md` §8.1 proposed,
one hypothesis ago, that *"breadth feeds edges that SELECT and dilutes
edges that HARVEST."* This hypothesis was registered to test exactly that,
with the prediction written down in §1: **top-K on 34 would beat
harvest-all on 34.**

**It does not.** Bar 5 fails, and it fails monotonically:

> **K = 3 → 2.27, K = 5 → 2.99, K = 10 → 4.06, harvest-all → 5.60.**
> The less you select, the better it gets, without exception.

`INTERPRETATION` — the select/harvest story is **wrong for carry**, and the
prediction made in its name was wrong in the direction it predicted. This
is recorded as a refutation of a claim this project made 24 hours earlier,
not softened into a partial result.

### 8.3 What actually explains it

`OBSERVATION` — comparing K=10 to harvest-all: **CAGR barely moves**
(+3.93% vs +4.36%) while **MDD grows more than fivefold** (−4.17% vs
−0.76%) and Sharpe falls 4.06 → 5.60. At K=3, MDD is **−7.65%**, ten times
the harvest book's.

`INTERPRETATION` — **carry's high Sharpe is a diversification property, not
a premium-size property.** The per-name premium is small everywhere;
Sharpe 5.9 comes from averaging ~20 near-independent small funding streams,
not from any of them being large. Selecting the richest few keeps
approximately the same mean and multiplies the variance, because the
averaging is what was doing the work.

`INTERPRETATION` (flagged) — this also undercuts H65's *dilution*
explanation. If the extra 26 symbols were dilution, concentrating should
have helped; it hurt, monotonically. The 5.91 → 5.60 drop in H65 is
therefore more likely the ragged-history/timing confound that H65 §8.3
already flagged than dilution. **H65's verdict stands as recorded — its
proposed refinement does not.**

### 8.4 §3's squeeze story is visible in the drawdowns

`OBSERVATION` — §3 named, before the run, the risk that *"the most crowded
coin is also the most squeeze-prone... selecting for rich funding may be
selecting for tail risk,"* and predicted it would *"show up as drawdown,
not as mean."*

That is precisely the shape observed: mean roughly preserved, drawdown
multiplied, worsening monotonically as K tightens. Bar 8 was set at 3
points before any drawdown was seen and fails at 4.76 points.

### 8.5 Disposition

Per §6, Gate A passing with bars 5 and 8 failing → **STANDALONE-VIABLE.**
A real edge — mean +0.944 bp/day, CI excluding zero, DSR 1.0000, CAGR
+3.50%, correlation +0.0076 with the deployed momentum book — that is
**worse than the incumbent on both return and risk.**

**Not deployed.** H63's 8-symbol harvest remains the carry spec. It does
**not** count toward the eight-edge target: same premium, selected
differently, not an independent edge.

`OBSERVATION` — the recent window is worse here than in any prior carry
hypothesis: **last 365 days −2.04%/yr at K=5**, against ~0% for the
harvest books. Concentration makes the dead regime actively costly.
