# Hypothesis 71 — Point-in-Time Universe: is the rotation edge hindsight?

Status: **PRE-REGISTERED 2026-08-28. NO RESULT EXISTS.** Trials declared:
**+2 → 172.** Verdict will be written into §8 and nowhere else.

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

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
