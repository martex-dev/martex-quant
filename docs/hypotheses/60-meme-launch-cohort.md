# Hypothesis 60 — Does any entry filter beat the raw Solana launch cohort, after costs?

Status: **REGISTERED 2026-08-11, NOT YET RUN.** The dataset is being recorded
now; no filter has been evaluated. Git history is the proof of ordering, not
this line.

---

## Preliminary: the descriptive run that precedes this

Before this hypothesis can be tested, the cohort's **base rate** has to exist:
what an unselected new Solana launch does, from a realistically timed entry,
gross and net of AMM costs. That descriptive run
(`scripts/meme_cohort_report.py`) produces no strategy claim and has no verdict
bar — it establishes the baseline that H60 must beat.

Per the standing rule that descriptive horizons are counted, it is logged as
**1 descriptive trial**. H60 itself registers the trials below.

---

## The question

The meme-coin program (`docs/research/meme-alpha-program.md`) concludes that
only one of the four mechanisms behind public meme-coin winners is reachable
from here: **portfolio structure** — many small tickets, ruthless exits, and a
tail that pays for the losers. Latency, reflexivity and private information are
structurally closed.

That reframes the problem. It is not "predict the 100x." It is:

> **Given features knowable at entry, can we select a subset of new launches
> whose net expectancy exceeds that of the whole cohort by more than the
> friction of trading it?**

If no filter beats the cohort, the honest conclusion is that meme-coin launch
selection with public, free, non-wallet-level data does not work, and the
program either moves to wallet-level data (needs an RPC key) or stops.

---

## Why the cost floor is part of the hypothesis, not a footnote

At a $50 ticket the round trip costs roughly 5–15% of the position, dominated
by flat priority fees. A filter that raises the mean 1h return from +2% to +6%
is a real statistical finding and a **worthless** trading result, because
breakeven sits above both. The verdict bars below are therefore stated in net
terms only. Gross improvements are not evidence for this hypothesis.

---

## Features under test (all knowable at entry, none forward-looking)

Recorded at first sighting, before any outcome exists:

1. `reserve_usd` — pool depth
2. `buys_m5 / sells_m5` — buy/sell imbalance
3. `buyers_m5` — unique buyer count, and buyers-per-buy (a crude fake-volume proxy)
4. `volume_m5 / reserve_usd` — turnover relative to depth
5. `fdv_usd` — implied valuation
6. `age_s` at discovery — how early we caught it
7. `dex` — launch venue
8. hour-of-day (UTC)

**Trial count: 8 single-feature screens + 1 composite = 9 trials.** Registered
before any is evaluated. Ledger moves 125 → 134 (+1 descriptive = 135).

---

## Verdict bars — committed before the run

Let the cohort baseline be buy-every-launch held to horizon, net of the
`economics.CostModel` at $50 per position.

**VALIDATED** requires all of:

1. Net mean return of the filtered cohort exceeds the unfiltered cohort by
   **≥ 5 percentage points** at some horizon in {1h, 4h, 24h}.
2. Filtered net mean return is **> 0** in absolute terms.
3. The filtered subset retains **≥ 200 launches**, so the result is not three
   lucky tokens.
4. Survives a block bootstrap over launch-hour blocks at **p < 0.01**
   (tighter than the usual 0.05 because 9 trials are being run).
5. Holds in a **walk-forward split**: fit the threshold on the first half of
   the recording window, evaluate on the second, with no re-tuning.

**KILLED** if the best filter fails any of 1–3, or if the walk-forward
out-of-sample net mean is negative.

**INCONCLUSIVE** if the dataset ends up with fewer than 5,000 measurable
launches, in which case nothing is claimed in either direction.

---

## Pre-committed expectation

Stated so that hindsight cannot rewrite it: I expect this to be **KILLED**.
The most likely outcome is that the cohort's net expectancy is strongly
negative at every horizon (costs plus the fact that most launches are designed
to extract), and that no single-feature filter lifts it above zero. Depth and
buyer-count filters are the two most likely to show something, and the most
likely reason they *appear* to work is that they select for tokens the fast
snipers already bought — which is a survivorship effect wearing a feature's
clothes, and which the walk-forward split will not remove.

Recording that here means a KILLED verdict costs nothing to admit.

---

## What a KILLED verdict does NOT mean

It would not mean meme-coin trading is impossible — the public winners are
evidence against that. It would mean that *this data layer* is insufficient,
and the program's next move is wallet- and holder-level features via a Solana
RPC/indexer, which is where the rug-detection literature finds its signal.
That is a different hypothesis with a different data source, not a re-run of
this one.
