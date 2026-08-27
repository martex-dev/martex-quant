# Hypothesis 66 — Cross-Sectional Carry (top-K funding)

Status: **PRE-REGISTERED 2026-08-27, NOT RUN.** Trials: **+3 → 147.**

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
