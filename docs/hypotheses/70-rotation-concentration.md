# Hypothesis 70 — Rotation Concentration: was K=2 ever the right number?

Status: **PRE-REGISTERED 2026-08-28. NO RESULT EXISTS.** Trials declared:
**+3 → 170.** Verdict will be written into §8 and nowhere else.

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

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
