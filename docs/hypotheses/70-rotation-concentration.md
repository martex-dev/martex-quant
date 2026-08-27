# Hypothesis 70 — Rotation Concentration: was K=2 ever the right number?

Status: **KILLED — K=2 VINDICATED (2026-08-28).** Trials: **+3 → 170.**
Verdict in §8. Gate A fails on the primary and on **every** cell, so the
result does not depend on which cell was primary. All three §5.1
predictions were **wrong**: H66's carry finding does not transfer to
momentum rotation. The live-window diagnostic points the **opposite way**
to the backtest, and §8.6 says what that does and does not license.

This one is aimed at the **deployed spec**, not at a new family. It asks
whether the single number that was never tested — how many slots
rotation-stop holds — is costing risk-adjusted return.

**Committed before any study code exists.**

---

## 1. Claim

The deployed rotation-stop book holds the **top 2** of ~38 ranked coins.
Raising the slot count keeps most of the mean while materially cutting
drawdown, so a higher K is a better book by Sharpe and by max drawdown.

## 2. Why this is worth testing, and why it is not a re-test

`OBSERVATION` — **K was never searched.**
`docs/hypotheses/11-cross-sectional-rotation.md` line 60 reads
*"gated-out slots sit in cash. Long-only. **K=2 FIXED.**"* It was fixed by
fiat at the start of the rotation family and has been inherited unchanged
by every descendant since, including H42b, which is what runs on paper
today.

`OBSERVATION` — **the two adjacent hypotheses are not this one.**
- **H37 breadth dial** varied the *market-state* breadth of the universe,
  not the number of slots. KILLED (suggestive, not significant).
- **H39 pick-correlation** varied the *correlation between the two picks*
  while holding K=2 constant, and its verdict says in terms: *"Forcing
  diversified picks buys no return (**risk effects were not the claim**)."*
  Risk effects are exactly this hypothesis's claim.

`INTERPRETATION` — this is a genuine gap, not a reopened kill. No stated
reason for re-running a closed idea is required, because the idea was
never run.

`OBSERVATION` — **the cross-family prior is strong and recent.** H66
tested exactly this shape in the carry family and found concentration is
what destroys the ratio: *"carry's high Sharpe is a DIVERSIFICATION
property, not a premium-size one. K=10 keeps nearly the same mean (+3.93%
vs +4.36%) while MDD grows fivefold (−4.17% vs −0.76%); at K=3 MDD is
−7.65%, ten times the harvest book."* Monotone in K, in the direction
this hypothesis predicts.

`OBSERVATION` — **the live evidence, which is suggestive and not proof.**
Three paper accounts have run the same momentum idea since 2026-07-10 at
different concentrations:

| Account | Universe / slots | Equity 2026-08-27 |
|---|---|---|
| vol-target | 8 majors, all held, vol-scaled | **+5.84%** |
| rotation-stop | top **2** of ~38, stop overlay | **−7.44%** |
| rotation | top **2** of ~38, no stop | **−17.14%** |

`INTERPRETATION` — one window, n=1, and the three differ in universe as
well as in concentration, so this cannot separate the two. It is recorded
as the observation that **motivated** the hypothesis, and it is
explicitly **not** evidence for it. H59 already established that
rotation-stop's live drawdown sits at p=0.0081 of its own backtest
distribution; if concentration explains that, this test will show it, and
if it does not, that closes a lead.

## 3. When it should fail

- **If the edge IS the concentration.** Ranking 38 coins and taking the
  top 2 is designed to catch the parabolic winner. Diluting toward the
  universe mean may destroy the mean faster than it cuts the variance —
  and the wide universe's own return has been poor (H59b: the
  equal-weight 40-coin universe fell −9.77% over a month in which BTC
  rose +2.62%).
- **If costs eat it.** More slots means more rebalancing on thinner names.
- **If meta-finding 1 applies here too.** This project has confirmed six
  times that crypto continues; a spec that holds fewer, stronger names is
  the purest expression of that, and weakening it may simply be worse.

## 4. Specification

**The deployed spec in every respect, with exactly one thing varied.**

- Strategy: `StopVolTargetRotation(lookback=L, top_k=K, target_vol_annual=0.30,
  vol_window=30)` — the H42b spec that is running on paper.
- Protocol: the champion walk-forward (`rotation_wf_stream`), L re-selected
  each test window from `ROT_GRID = {30, 90}` by training Sharpe, the same
  `TRAIN`/`TEST` windows H41/H42 used.
- Universe: the wide 40-coin universe, unchanged.
- Data: the **frozen research lake** (`data/lake`, through 2026-07-09), so
  the result is comparable to the published DSR 0.9909 and to every other
  trial in the ledger.
- Execution: the same engine, same `CONFIG`, decisions at the close, fills
  at the next bar's open, costs charged.

**L is re-selected by the walk-forward protocol within each cell** rather
than pinned to the deployed L path. That is deliberate: the protocol is
part of the spec, and pinning L would measure a book we do not run. The
consequence — each K gets its own L path, so cells differ in more than K —
is a limitation and is recorded in §7. The chosen L path per K is reported.

### 4.1 The declared cells — 3 trials, no more

| # | Cell | Role |
|---|---|---|
| — | **K = 2** | the **incumbent**, recomputed in the same run on the identical window. Not a new trial: it is the deployed spec. |
| 1 | K = 3 | |
| 2 | **K = 5 — PRIMARY** | |
| 3 | K = 8 | |

All reported regardless of outcome. **No other parameter is searched** —
not the vol target, not the vol window, not the stop, not the universe,
not `ROT_GRID`.

> The incumbent's figures **will differ from the published +42.9% / 1.47**
> if the window differs at all; it is recomputed in the same run so the
> comparison is like-for-like. Importing a published number and comparing
> it to a differently-computed one is the FU-B1 defect
> (`docs/research/graveyard-audit.md` §2.1) and will not be repeated.

## 5. Pre-registered bars

Judged on the **primary cell (K=5)**; all cells reported.

**Gate A — does it beat the deployed spec on risk-adjusted terms?**

1. **Sharpe > K=2's**, identical window, same run.
2. **Max drawdown less severe than K=2's**, same run.

**Gate B — is it still validated?**

3. `DSR_global` ≥ **0.95** at **N = 170**.

**Gate C — does it keep enough of the income?**

4. **CAGR ≥ 75% of K=2's CAGR**, same run.

> The 75% is a judgment call fixed in advance, and the reason is the
> project's stated goal: this is an **income** project, so surrendering a
> quarter of the return for a better ratio is the most this hypothesis may
> spend without the owner deciding. It is not a statistical threshold and
> is not presented as one.

### 5.1 Predictions recorded in advance

- **Sharpe rises and CAGR falls, both monotone in K**, mirroring H66.
- **MDD improves materially** — this is where H66 saw the whole effect.
- Recording these now means a *non-monotone* result would be a genuine
  surprise rather than something to narrate after the fact.

### 5.2 Reported, explicitly NOT gated

Per-year returns, time in market, turnover and fill counts, the chosen L
path per K, and — the reason this hypothesis is worth running now — a
**replay of every cell over the live paper window (2026-07-10 →
2026-08-26) on `data/lake-current`**.

That replay is a **diagnostic on the declared cells, not a new cell and
not a new trial**: same spec, same parameters, different reporting window,
in the same category as H68's per-year table and H67's tail table. It is
**48 days**, which is far too short to support any conclusion, and it is
reported as context for the divergence hunt rather than as evidence. If a
reader judges it should count as trials, the difference between N=170 and
N=174 moves `DSR_global` by less than 0.001 and changes no verdict here.

## 6. Disposition, declared in advance

- **A + B + C** → **candidate to replace K in the deployed spec.** A spec
  change means the paper record is archived and a fresh $5,000 record
  starts (standing rule). The arithmetic goes to the owner; **deployment
  is their decision, not this document's.**
- **A + B, C fails** → the trade-off is real and is the owner's to make.
  **Not auto-deployed.** Both books' CAGR, Sharpe, MDD and prop-sim
  geometry are presented side by side, per the charter's instruction to
  *present the aggressive option's real numbers instead of defaulting to
  the conservative recommendation*.
- **A fails** → **K=2 vindicated.** Concentration is **not** what makes
  the live drawdown exceed backtest expectations, and the H59 divergence
  hunt must look elsewhere. That is a real result: it closes a lead that
  currently looks obvious, and closing it is worth the three trials.

## 7. Known limitations, stated before results

- **L is re-selected per cell**, so cells differ in the L path as well as
  in K. This is faithful to the deployed protocol and unfaithful to a
  clean single-variable experiment; both cannot be had at once, and the
  spec was chosen over the cleanliness.
- **The live-window replay is 48 days.** It cannot establish anything. It
  is included because the H59 hunt has no other out-of-sample data and
  because refusing to look would be worse than looking carefully.
- **`data/lake-current` is not the frozen lake.** The bars are judged on
  the frozen lake only; the current lake appears solely in the §5.2
  diagnostic. It was refreshed 2026-08-28 to 2026-08-26 and the frozen
  lake was verified byte-identical on all 3,249 shared days afterwards.
- **Survivorship is unchanged** from the rotation family: the universe is
  the top 40 by volume as of 2026-07-12, and fully delisted coins are
  absent. Raising K pulls in more of the small names where that bias
  bites hardest, so a K>2 improvement is, if anything, flattered.
- **Costs on thin names.** The project charges a flat 10bp + 1bp with a
  25bp participation-impact term. Higher K means more names and more
  turnover in exactly the coins where that model is most optimistic.
- **This does not test the universe.** vol-target's +5.84% may be about
  holding 8 majors rather than about holding 8 *slots*; §2 says so and
  this hypothesis cannot separate them. A universe test would be its own
  registration.

---

## 8. VERDICT (2026-08-28, scripts/h70_rotation_concentration.py, +3 → 170)

**KILLED. K=2 is vindicated.** Gate A fails on the primary K=5, and — the
part that matters — on **every** declared cell. Common window 2,880 days,
2018-08-17 → 2026-07-05, all four books run in one process.

### 8.1 The incumbent reproduces exactly, which is what makes the rest usable

`OBSERVATION` — the K=2 recomputation lands on **CAGR +42.91%, Sharpe
1.47, MDD −29.01%**. The published deployed-spec figures are **+42.9% /
1.47 / −29.0%**.

`INTERPRETATION` — the walk-forward protocol in this script reproduces
the deployed spec to the published digits. Every comparison below is
therefore against the real incumbent, not an approximation of it. Had
this not reproduced, no cell figure would have been reportable.

### 8.2 The declared cells — all reported

| Book | CAGR | Sharpe | MDD | mean bp/day | 95% CI (bp) | DSR@170 | L path |
|---|---|---|---|---|---|---|---|
| **K=2 (incumbent)** | +42.91% | **1.47** | **−29.01%** | +10.737 | [+4.882, +16.536] | 0.9994 | 30:15 90:17 |
| **K=3** | **+46.23%** | **1.61** | −32.40% | +11.290 | [+5.514, +17.046] | 0.9998 | 30:13 90:19 |
| **K=5 (primary)** | +34.53% | 1.40 | −31.46% | +8.850 | [+3.698, +14.043] | 0.9979 | 30:17 90:15 |
| K=8 | +27.13% | 1.27 | −31.82% | +7.151 | [+2.605, +11.832] | 0.9931 | 30:19 90:13 |

### 8.3 The four bars

| Gate | Bar | Measured (K=5) | Result |
|---|---|---|---|
| A1 | Sharpe > incumbent's | 1.40 vs **1.47** | **FAIL** |
| A2 | MDD less severe than incumbent's | −31.46% vs **−29.01%** | **FAIL** |
| B3 | DSR ≥ 0.95 @170 | 0.9979 | PASS |
| C4 | CAGR ≥ 75% of incumbent's | +34.53% vs +32.18% needed | PASS |

`OBSERVATION` — **A2 fails for every cell.** K=3 (−32.40%), K=5 (−31.46%)
and K=8 (−31.82%) all draw down worse than K=2's −29.01%. A1 additionally
fails for K=5 and K=8.

`INTERPRETATION` — the verdict does not rest on the choice of primary. Had
any other cell been declared primary, Gate A would still have failed.
That is a stronger result than a single-cell failure and it is the reason
this reads as *vindication* rather than *inconclusive*.

### 8.4 Every prediction was wrong: H66 does not transfer

| K | 2 | 3 | 5 | 8 |
|---|---|---|---|---|
| Sharpe | 1.47 | **1.61** | 1.40 | 1.27 |
| CAGR | 42.91 | **46.23** | 34.53 | 27.13 |
| MDD | **−29.01** | −32.40 | −31.46 | −31.82 |

`OBSERVATION` — §5.1 predicted Sharpe rising monotonically in K, CAGR
falling monotonically, and MDD improving. **None of the three holds.**
Sharpe and CAGR both peak at K=3 and then fall; MDD is worst-in-class at
K=3 and never beats K=2.

`INTERPRETATION` — **H66's carry result does not generalize to momentum
rotation, and the reason is mechanical.** Carry harvests a premium paid
by ~20 near-independent funding streams, so averaging more of them cuts
variance without cutting the mean. Rotation *selects*: its whole return
comes from concentrating in the few strongest names, and the 4th through
8th ranked coins are simply worse assets, not additional independent
draws of the same edge. Diluting a selection edge with weaker picks
lowers the mean faster than it lowers the variance.

That is the same select-versus-harvest distinction H65 §8.1 proposed and
H66 §8.3 withdrew — and this is the first evidence that the distinction
is real, arriving from the opposite direction. **Recorded as a
hypothesis, not a rule:** it is now one measurement in each of two
families, which is exactly the evidential state that produced the
withdrawn refinement last time. It should not be quoted as established.

`OBSERVATION` — MDD gets **worse** at every K above 2, which no one
predicted. More names did not mean more diversification here; it meant
more simultaneous exposure to the same alt-beta in a drawdown.

### 8.5 K=3 beats the incumbent on return and is NOT being acted on

`OBSERVATION` — K=3 posts **Sharpe 1.61 vs 1.47** and **CAGR +46.23% vs
+42.91%**. It loses only on drawdown, −32.40% vs −29.01%, which is the
bar it fails.

`INTERPRETATION` — three reasons this is recorded and not adopted:

1. **It was not the primary.** K=5 was declared primary in §4.1 before any
   number existed. Promoting the best of a four-point grid after seeing
   all four is the failure pre-registration exists to prevent — the same
   call made in H67 §8.6 when BTC-only was the best cell.
2. **It fails the registered bar anyway.** A2 is not a technicality here:
   meta-finding 8 records that constraint geometry, not the return
   stream, decides prop-firm outcomes, and a 3.4pp worse drawdown lands
   directly on the rule that matters for an evaluation.
3. **The grid is four points on one universe.** A Sharpe difference of
   0.14 across adjacent K values on a single 2,880-day path is not a
   measurement of the K surface.

**Per the charter, the numbers go to the owner rather than being
suppressed or acted on:** K=3 offers +3.3pp of CAGR and +0.14 of Sharpe
for 3.4pp more drawdown. If that trade is wanted it needs its own
pre-registration with a stated reason, and it should carry a prop-sim
pass-rate comparison, because that is the objective the funded path is
actually judged against.

### 8.6 The live window says the opposite — and what that does NOT license

`OBSERVATION` — replaying every cell over the live paper window
(2026-07-10 → 2026-08-26, `data/lake-current`, L=90 as the paper account
actually runs):

| Book | live return | worst day | MDD |
|---|---|---|---|
| K=2 (incumbent) | **−6.06%** | −3.05% | **−15.48%** |
| K=3 | −7.54% | −3.38% | −15.50% |
| K=5 | −3.85% | −2.03% | −11.16% |
| **K=8** | **−0.85%** | −1.58% | **−7.09%** |

Live paper accounts over the same period: rotation-stop −7.44%, rotation
−17.14%, vol-target (8 majors, all held) +5.84%.

`OBSERVATION` — over these 48 days, return and drawdown both improve
**monotonically with K** above K=3. K=8 lost 0.85% where K=2 lost 6.06%.
This is the exact opposite of the eight-year backtest.

`INTERPRETATION` — **this is a real answer to part of the H59 divergence
question, and it is not a licence to change K.** In this window,
concentration accounts for roughly five of the six points rotation-stop
gave up: a more diversified version of the identical spec would have been
close to flat. So the live drawdown is not purely bad luck in stock
selection; it has a structural component, and that component is K.

And yet **48 days cannot overturn 2,880.** Switching K because the last
seven weeks favoured a different setting is textbook recency-chasing, and
it is precisely how a validated spec gets destroyed. The backtest says K=8
earns 27% a year against K=2's 43% with a worse drawdown; the live window
says K=8 would have been flat instead of −6%. **Both are true, and the
second is 1.7% of the evidence of the first.**

`OBSERVATION` — **§6's pre-declared inference was too strong and is
corrected here.** It said a Gate A failure would mean *"concentration is
not what makes the live drawdown exceed backtest expectations, and the
H59 divergence hunt must look elsewhere."* That inference does not follow:
the bars are computed on the frozen backtest and cannot answer a question
about the live window. The bars say concentration is not a defect **in
sample**; the diagnostic says concentration **did** hurt in this
out-of-sample window. Writing the inference into the disposition was a
drafting error — it assumed one measurement could answer two questions.
The verdict stands on the bars; the further claim is withdrawn.

**What the divergence hunt should take from this:** concentration is a
live contributor, the deployed setting is still the best one on the
evidence we have, and the open question is now sharper — *is the live
period an unrepresentative sample, or has the K surface actually moved?*
That needs forward time, not another slice of the same history.

### 8.7 Per-year, incumbent vs primary

| Year | n | K=2 | K=5 |
|---|---|---|---|
| 2018 | 137 | −29.19% | −9.44% |
| 2019 | 365 | +32.39% | +25.91% |
| 2020 | 366 | +58.67% | +62.76% |
| 2021 | 365 | +98.09% | +89.36% |
| 2022 | 365 | −1.66% | −16.62% |
| 2023 | 365 | +27.25% | +35.54% |
| 2024 | 366 | +60.91% | +59.74% |
| 2025 | 365 | −2.86% | −9.73% |
| 2026 | 186 | **+92.80%** | +22.14% |

`OBSERVATION` — K=5 beats K=2 in three of nine years and loses badly in
2022 (−16.62% vs −1.66%) and 2026 (+22.14% vs +92.80%).

`INTERPRETATION` — the incumbent's advantage is concentrated in the years
when one or two names ran hard, which is the mechanism §8.4 describes.
Note 2026 is the frozen lake's partial year ending 2026-07-05, and its
+92.80% is exactly the kind of single-window figure that should not be
annualized in the reader's head.

### 8.8 What this closes and what it costs

- **The obvious explanation for the live drawdown is now measured rather
  than assumed.** It is a real contributor and it is not a reason to act.
- **K=2 keeps its place in the deployed spec**, and for the first time on
  evidence rather than by the inheritance recorded in §2.
- **Nothing is deployed, changed, or made paper-eligible by this
  hypothesis.** The paper records continue unchanged, which is the
  correct outcome of a vindication.
- **Cost: three trials**, moving `DSR_global` for the deployed book from
  0.9889 at N=167 to essentially the same figure at N=170 — the re-check
  run alongside this hypothesis put rotation-stop at **0.9889** and
  rotation at **0.9870**, both clearing 0.95.
