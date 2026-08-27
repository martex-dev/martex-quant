# Hypothesis 71 — Point-in-Time Universe: is the rotation edge hindsight?

Status: **CONFIRMED — the defect is real and large (2026-08-28).** Trials:
**+2 → 172.** Verdict in §8.

**Gate A fails and Gate B fails.** On a point-in-time universe the
deployed spec keeps **58% of its Sharpe** (1.47 → **0.86**) and **49% of
its CAGR** (+42.91% → **+21.06%**), on the identical window with the same
strategy, engine and costs, and with **zero parameters changed**. All
three §5.1 predictions were right. Per §6 this is the disposition written
in advance: **rotation-stop comes off the evaluation path**, and the
published rotation-family figures must be re-stated. The result is still
an **upper bound** — see §8.6.

This hypothesis is aimed at the **measuring instrument**, not at a new
edge. It asks whether the deployed spec's published figures survive when
the universe it ranks inside is chosen with information that was actually
available at the time.

**Committed before any study code exists.** The broad pool was collected
first (`scripts/pull_pool.py`, 2026-08-28), which runs no study and
decides nothing.

**This is the test most likely to damage existing results in this
ledger, and that is the argument for running it.**

---

## 1. Claim

The rotation family's backtested performance is materially inflated by
the fact that its universe was selected at the end of the sample. Re-run
with a point-in-time universe, the deployed spec's Sharpe falls
substantially.

## 2. The defect, stated precisely

`OBSERVATION` — `config/universe.json` carries its own provenance:

```
"rule": "top40 by 24h quote volume, 2026-07-12, union legacy 8,
         stables/leveraged excluded"
```

The selection date, **2026-07-12**, is the end of the research sample.
The rotation family backtests **2018 → 2026** by ranking inside that set.

`OBSERVATION` — how much of the universe is hindsight, counted from the
frozen lake's listing dates:

| | count |
|---|---|
| Universe symbols | 40 |
| **Existed for the whole 2018-2026 backtest** | **8** |
| Listed 2024 or later | 13 |

The thirteen recent entrants are ENA, TAO, HMSTR, PARTI, VIRTUAL, SXT,
TREE, XPL, MMT, U, OPN, SPCXB, GRAM.

`INTERPRETATION` — for most of the backtest the strategy ranks among
coins that are in the pool **because they later became prominent**. Live,
it ranks among coins that may not. That is look-ahead in universe
construction, and it is a different defect from the one the project has
already recorded.

`OBSERVATION` — the recorded caveat covers only half of it.
PROJECT_MEMORY says survivorship is *"mitigated (wide universe incl. 90%+
crashers), not eliminated (fully-delisted coins unmeasurable without paid
data)"*. That is the **delisting** half, and it is correctly described as
unfixable for free. The **hindsight-inclusion** half is separable and is
testable with free data. It has never been measured.

`OBSERVATION` — the live evidence that made this urgent. H59 put
rotation-stop's live drawdown at p=0.0081 of its own backtest
distribution. H70 found concentration accounts for roughly five of the
six points lost. A hindsight universe is the natural candidate for the
rest, and it points the right way: the backtest ranks among known
survivors, the live account ranks among unknowns.

## 3. When it should fail — i.e. when the deployed spec is fine

- **If momentum ranking is robust to the pool.** Taking the strongest 2
  of 40 may work on any reasonable 40, in which case which 40 barely
  matters and the published figures stand.
- **If the recent entrants contribute little.** Thirteen coins listed in
  2024+ cannot affect 2018-2023 at all; if the edge is spread evenly
  across years, the bias is confined to the tail of the sample.
- **If the point-in-time pool is simply noisier.** Reselecting every 90
  days adds turnover and admits thinner names, which costs return for
  reasons that have nothing to do with hindsight. §5 Gate B is set with
  a tolerance for exactly this.

## 4. Specification

### 4.1 The pool

Every **active Binance USDT spot pair** (468 at collection), excluding
stablecoins and leveraged tokens by the same rule
`config/universe.json` applies, with daily OHLCV from 2017 in
`data/pool/`. This is the candidate set a point-in-time selector chooses
from.

### 4.2 Point-in-time selection

At each **reselection date**, rank every pool symbol with at least
`MIN_HISTORY = 90` days of bars by **mean daily quote volume over the
trailing 30 days**, and take the **top 40**.

- **Trailing 30-day mean, not 24h**, because a single day's volume is
  noisy and a spot check would make the universe churn on nothing. The
  universe rule's own "24h quote volume" is a snapshot convention that
  does not survive being applied 30 times.
- **No legacy-8 union.** `config/universe.json` unions a fixed set chosen
  today; carrying that into a point-in-time universe would re-import the
  exact bias under test.
- **Reselection cadence is the one declared variable** (§4.4).

### 4.3 The book

The **deployed spec, unchanged**: `StopVolTargetRotation(L, top_k=2,
target_vol_annual=0.30, vol_window=30)` under the champion walk-forward
(L re-selected each 90d from `{30, 90}`, `TRAIN=365`, `TEST=90`), the
same engine, decisions at the close, fills at the next bar's open, the
project's cost model. **Nothing about the strategy is varied.** The only
change is which symbols it may rank.

**Incumbent:** the identical spec on the **hindsight universe**,
recomputed in the same run over the same window, never imported.

Data window: the pool's full extent, restricted to the frozen research
window ending **2026-07-09** so the comparison is like-for-like with
every published rotation figure.

### 4.4 The declared cells — 2 trials, no more

| # | Cell | Purpose |
|---|---|---|
| **1** | **Point-in-time, reselect every 90 days — PRIMARY** | matches the walk-forward test cadence |
| 2 | Point-in-time, reselect every 365 days | robustness: is any degradation caused by churn rather than by honesty? |

Both reported regardless of outcome. **No other parameter is searched** —
not the universe size, not the volume window, not `MIN_HISTORY`, not the
strategy.

## 5. Pre-registered bars

Judged on the **primary cell**.

**Gate A — does the deployed spec survive an honest universe at all?**

1. Sharpe ≥ **1.0**.
2. Mean daily net > 0 with a 95% block-bootstrap CI (30-day blocks)
   excluding zero.
3. `DSR_global` ≥ **0.95** at **N = 172**.

**Gate B — how much of the published edge was the hindsight universe?**

4. **Point-in-time Sharpe ≥ 70% of the hindsight-universe Sharpe**,
   recomputed in the same run on the identical window.

> The 70% is a judgment call fixed in advance, and the reason is §3's
> third bullet: some degradation is expected from churn and thinner names
> and is not evidence of hindsight. Losing **more than 30%** of the ratio
> is more than that tolerance can absorb, and at that point the published
> figures are substantially an artifact of the selection date. It is not
> a statistical threshold and is not presented as one.

### 5.1 Predictions recorded in advance

- **Sharpe falls materially.** Best guess **1.47 → 0.7-1.2**.
- **The overlap between the point-in-time top-40 and the hindsight 40 is
  low in early years — under 40% in 2019-2020** — and rises toward 2026
  by construction.
- **The degradation is concentrated in the biggest backtest years**
  (2021 +98%, 2026 +92.8%), which are exactly when parabolic names
  dominate the ranking.

Recording these means a null result is a genuine surprise rather than
something narrated afterwards.

### 5.2 Reported, explicitly NOT gated

Per-year returns for both universes; **the overlap between the
point-in-time universe and the hindsight 40, by year**; universe turnover
per reselection; how many pool symbols are rankable each year; time in
market; and the identity of the names the point-in-time selector actually
held in the live-adjacent period.

## 6. Disposition, declared in advance

- **A + B** → **the deployed spec survives.** The hindsight universe was
  not doing the work, and confidence in the entire momentum block rises.
  This is the best available outcome and it would be earned.
- **A passes, B fails** → the spec is still an edge, but **the published
  rotation-family figures are materially inflated.** The point-in-time
  number becomes the honest one, and PROJECT_MEMORY, PROJECT_STATE and
  the affected hypothesis documents must be **re-stated, not annotated**.
  That is a large documentation debt and it is accepted in advance as the
  price of having asked.
- **A fails** → **the deployed spec does not survive an honest universe.**
  It must come off the evaluation path, and the paper record continues
  only as a measurement rather than as a candidate. This would be the
  most consequential negative result in the project's history, and the
  disposition is written down now so that it cannot be softened later.

**No outcome here deploys anything.** The paper accounts continue
unchanged in every branch; what changes is what may be claimed about them.

## 7. Known limitations, stated before results

- **THE RESULT IS STILL AN UPPER BOUND, and this is the most important
  line in the document.** Binance's API lists only pairs active today, so
  a coin that was a top-40 name in 2019 and has since been delisted
  cannot enter the point-in-time universe either. This hypothesis removes
  the *hindsight-inclusion* half of the bias and leaves the *delisting*
  half untouched. A pass is a pass on a universe that is still
  survivor-biased.
- **Quote volume is approximated** as `close x base volume`, because
  Binance's OHLCV carries base volume only. Fine for ranking, not exact.
- **Volume is not comparable across eras.** A 2019 top-40 by USDT volume
  and a 2026 top-40 are different animals; the selector is consistent
  within itself but the pool's composition shifts underneath it.
- **Reselection churn is charged but not otherwise modelled.** Real
  universe turnover also means operational work — new symbols to
  onboard — which no backtest here represents.
- **`MIN_HISTORY = 90` excludes brand-new listings** from selection, which
  is realistic but also means the selector cannot buy a coin in its first
  three months, whereas the hindsight universe effectively could.
- **This tests the universe, not the strategy.** If the spec fails here,
  the failure is about the evidence base for it, not proof that momentum
  ranking is worthless.
- **The frozen lake and the pool are different stores.** The incumbent is
  run on the pool's copies of the universe symbols so both arms share one
  data source; any difference from the published figures caused by that
  is reported in §8 before anything else is interpreted.

---

## 8. VERDICT (2026-08-28, scripts/h71_point_in_time_universe.py, +2 → 172)

**The hindsight universe was doing roughly 40% of the work.** Gate A
fails, Gate B fails. Pool: 469 collected, **393 usable** inside the
window. Common window 2,880 days, 2018-08-17 → 2026-07-05.

### 8.1 The incumbent arm is faithful, which is what licenses the comparison

`OBSERVATION` — the hindsight-universe arm returns **CAGR +42.91%, Sharpe
1.47, MDD −29.01%** — the published deployed-spec figures (+42.9% / 1.47
/ −29.0%) and identical to H70's independent recomputation yesterday.

`INTERPRETATION` — the only thing that differs between the arms is which
symbols the strategy may rank. Same code, same engine, same costs, same
window, same walk-forward. A degradation cannot be blamed on the harness.

### 8.2 The cells

| Book | CAGR | Sharpe | MDD | mean bp/day | 95% CI (bp) | DSR* |
|---|---|---|---|---|---|---|
| **hindsight 40 (incumbent)** | **+42.91%** | **1.47** | −29.01% | +10.737 | [+4.882, +16.536] | 0.8844 |
| **point-in-time, 90d — PRIMARY** | **+21.06%** | **0.86** | −33.23% | +6.165 | [+0.765, +12.243] | 0.2759 |
| point-in-time, 365d | +17.15% | 0.73 | −35.85% | +5.268 | [+0.018, +10.794] | 0.1733 |

**\*** These DSR figures deflate against the variance of **this study's
three books**, which is a narrower benchmark than the deployed spec's
published estimator. **The incumbent's 0.8844 here is NOT a revision of
the published 0.9909 and must not be quoted as one.** It is included only
so the three cells are deflated identically, which is what the comparison
needs.

### 8.3 The bars

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | Sharpe ≥ 1.0 | **0.86** | **FAIL** |
| A2 | mean > 0, CI excludes zero | +6.165bp, low +0.765bp | **PASS** |
| A3 | DSR ≥ 0.95 @172 | 0.2759 | **FAIL** |
| B4 | Sharpe ≥ 70% of hindsight's | 0.86 vs **1.03 needed** | **FAIL** |

**Sharpe retained: 58%. CAGR retained: 49%. Drawdown worse by 4.2pp.**

### 8.4 All three pre-registered predictions were right

| §5.1 prediction | measured | |
|---|---|---|
| 2019-2020 overlap with the hindsight 40 under 40% | **26%** | RIGHT |
| Sharpe falls to 0.7-1.2 | **0.86** | RIGHT |
| Degradation concentrates in 2021 and 2026 | **−65pp and −111pp** | RIGHT |

`INTERPRETATION` — being right in advance is what separates this from a
post-hoc story. The mechanism was named before the run and the data
matched it on all three counts.

### 8.5 It is not churn — the robustness cell settles that

`OBSERVATION` — §3's third bullet said some degradation should be
expected from reselection turnover and thinner names, and Gate B's 70%
tolerance was set for it. The 365-day cell tests it directly: reselecting
once a year is the **low-churn** arm.

`OBSERVATION` — the low-churn arm is **worse**, not better: Sharpe 0.73
against 90d's 0.86, CAGR +17.15% against +21.06%.

`INTERPRETATION` — if churn were paying for the gap, slowing reselection
would recover it. It does the opposite. **The gap is not a turnover
artifact; it is the universe.** Turnover averaged 9.3 new names per
90-day reselection (max 18), which is the honest cost of not knowing the
future, and it is already inside these numbers.

### 8.6 How much of the universe was hindsight, and why this is still an upper bound

| Reselection | rankable | overlap with the hindsight 40 |
|---|---|---|
| 2018-11-10 | 15 | 8 / 40 (20%) |
| 2019-11-05 | 36 | 11 / 40 (28%) |
| **2020-10-30** | 40 | **11 / 40 (28%)** |
| **2021-10-25** | 40 | **13 / 40 (32%)** |
| 2022-10-20 | 40 | 13 / 40 (32%) |
| 2023-10-15 | 40 | 14 / 40 (35%) |
| 2024-10-09 | 40 | 17 / 40 (42%) |
| 2025-10-04 | 40 | 22 / 40 (55%) |

`OBSERVATION` — in 2021, the year the incumbent posts **+98.09%**, only
**13 of the 40 coins the strategy was allowed to rank** were actually
top-40 by volume at the time. The overlap rises monotonically toward the
snapshot date, which is exactly the shape hindsight selection produces.

`OBSERVATION` — **four universe symbols have been delisted from Binance
since the 2026-07-12 snapshot**: GRAM, PYR, SPCXB, VANRY. They fell back
to the frozen lake so the incumbent stayed faithful. **PYR and VANRY are
two of the five worst performers H59b identified in the live window.**

`INTERPRETATION` — that is the survivorship mechanism operating inside
six weeks, and it is the half this study **cannot** fix. Binance lists
only pairs active today, so a coin that was genuinely top-40 in 2019 and
has since been delisted cannot enter the point-in-time universe either.
**Every figure in §8.2 is therefore an upper bound: the honest Sharpe is
at most 0.86, and plausibly lower.** §7's first limitation is not a
formality; it is the reason a Gate A failure here is decisive while a
pass would not have been.

### 8.7 Per-year: where the hindsight lived

| Year | hindsight | point-in-time | gap |
|---|---|---|---|
| 2018 | −29.19% | −18.89% | +10.29 |
| 2019 | +32.39% | +21.19% | −11.20 |
| 2020 | +58.67% | **+90.10%** | **+31.43** |
| **2021** | **+98.09%** | +33.05% | **−65.04** |
| 2022 | −1.66% | −25.89% | −24.23 |
| 2023 | +27.25% | +45.93% | +18.68 |
| **2024** | +60.91% | +20.33% | **−40.58** |
| 2025 | −2.86% | +9.23% | +12.08 |
| **2026** | **+92.80%** | **−18.61%** | **−111.41** |

`OBSERVATION` — the point-in-time book **beats** the incumbent in four of
nine years (2018, 2020, 2023, 2025) and loses catastrophically in the
three biggest incumbent years.

`INTERPRETATION` — this is the signature of hindsight rather than of a
weaker strategy. A uniformly worse book would lose everywhere. This one
loses precisely where the incumbent's headline came from: the years when
a coin that later became famous was mid-parabola. **2026 flips from
+92.80% to −18.61%** — the incumbent's best year is almost entirely a
selection artifact.

### 8.8 What follows, per §6, and what does not

**What follows — and this was written before the run so it cannot be
softened now:**

1. **rotation-stop comes off the evaluation path.** No funded-account
   attempt on this spec. It does not clear the project's own bars once
   the universe is honest.
2. **The paper records continue as measurement, not as candidacy.** They
   are still the only forward data the project has and they keep
   accruing.
3. **The published rotation-family figures must be re-stated.**
   PROJECT_MEMORY and PROJECT_STATE lead with the corrected number;
   historical verdicts are **annotated in place, never rewritten** —
   the H65/H66 precedent. Affected: H11, H41, H42a/b, H43a, H70.

**What does NOT follow:**

- **This is not "momentum is worthless."** A2 **passed**: mean +6.165
  bp/day with a CI excluding zero. There is still a real, positive,
  weak edge — roughly a Sharpe 0.86 book before the delisting half is
  accounted for. What died is the *claimed size* of it.
- **This does not automatically transfer to carry.** H63/H65 also rank
  inside `config/universe.json`, but H70 established that carry
  *harvests* while rotation *selects*, and hindsight inclusion should
  hurt a selection edge far more. **Should** is not **does**: the carry
  family has not been re-run on a point-in-time universe and no claim is
  made here about it. That is the obvious next registration.
- **This is not a data-quality failure.** §8.1 shows the incumbent arm
  reproduces the published figures exactly. The harness was right; the
  universe was wrong.

### 8.9 The honest summary

The project asked, at 170 trials, whether its most-cited result was real.
The answer is that **roughly 40% of the deployed spec's measured Sharpe
and half of its CAGR came from being allowed to rank coins that were only
in the universe because of what happened later** — and that the remaining
edge, while genuinely positive, does not clear the bars the project set
for itself.

That is the most consequential negative result in this ledger. It cost
two trials and it was found by asking a question about the measuring
instrument rather than searching for a fifth family.
