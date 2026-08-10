# TSLA CNN direction study — findings

**Status:** complete, negative result.
**Run:** 2026-08-10. Code: `src/trading_bot/research/tesla/`. Tests:
`tests/test_tesla_cnn.py`. Raw results: `data/Tesla/results_main.json`.

This is a standalone research study on a single US equity. It is **not**
part of the crypto hypothesis ledger, does not enter the DSR trial count
for the trading system, and no paper or live account is affected by it.

## Question

Given a window of daily TSLA bar features, can a 1D convolutional network
predict which volatility barrier — upper or lower — the price touches
first over the next 5 trading days?

## Data

`data/Tesla/Tasla_Stock_Updated_V2.csv`: 2,274 daily bars, 2015-01-02 to
2024-01-16, OHLCV. Validated on load: no duplicate or unsorted dates, no
gaps > 4 calendar days, no incoherent OHLC bars, no non-positive prices,
no zero-volume days, ~251 bars/year. Split-adjusted for both the 5:1
(Aug 2020) and 3:1 (Aug 2022) splits — verified by the absence of any
split-sized discontinuity; the largest single-day move is -21.1% on
2020-09-08, which is a real event.

`data/Tesla/TSLA.csv` (639 rows, 2019-09-30 to 2022-04-11) is a strict
subset period, adjusted for the 5:1 split only. Its daily returns match
V2 exactly on overlapping dates. Unused except as a consistency check.

## Method

**Features** (6 channels, all causal and stationary): volatility-scaled
log return, scaled high-low range, candle body, close location in range,
volatility-scaled overnight gap, volume z-score. Every scaling statistic
is computed over bars strictly *before* the bar being described, so no
sample can see its own normalisation constant. Raw prices never enter.

**Labels** (triple barrier): barriers at `close_t * exp(±1.0 * sigma_t)`
where sigma is 20-day trailing volatility; days t+1..t+5 scanned in order
using each day's high and low; first touch wins. A day whose range spans
both barriers resolves to NEUTRAL rather than guessing the intraday path.
Result: 1,072 UP / 992 DOWN / 115 NEUTRAL. NEUTRAL samples are dropped
from both training and scoring. Base rate UP = 0.519.

**Splits:** 5 purged walk-forward folds, expanding training window, 329
test samples each, embargo of 34 samples (`window + horizon - 1`) purged
around every test block. A further embargoed 20% tail of each training
block is held out for early stopping.

**Arms** (identical folds, inputs and scoring): majority-class floor,
L2 logistic regression, histogram gradient boosting, and the CNN —
two causal Conv1D layers (16 filters, kernel 3, dilations 1 and 2),
batch norm, global average pooling, dropout 0.4, L2 1e-3, **1,233
parameters**, early stopping with patience 20.

**Scoring:** ROC AUC; precision and coverage at a 0.55 confidence
threshold; and an economic test — long if p >= 0.55, short if p <= 0.45,
entry at the next day's open, exit at an open 5 days later, charged
10 bps round trip.

## Results

Pooled across 5 folds:

| arm | mean AUC | folds AUC > 0.5 | accuracy | base rate | trades | net bps/trade |
|---|---|---|---|---|---|---|
| majority | 0.5000 | 0/5 | 0.505 | 0.505 | 0 | — |
| logistic | 0.5019 | 3/5 | 0.493 | 0.505 | 1248 | −9.2 |
| gbm | 0.5117 | 4/5 | 0.503 | 0.505 | 522 | +46.2 |
| **cnn** | **0.4927** | **2/5** | 0.500 | 0.505 | 454 | −167.5 |

**No arm demonstrates exploitable skill.** The CNN sits *below*
coin-flipping. Gradient boosting is nominally best at 0.5117, which is
within noise of 0.5 and driven by one fold (2022-09 to 2024-01, AUC
0.566); its worst fold is 0.426. Fold-to-fold variation (0.43–0.57)
dwarfs any between-arm difference.

**Seed stability.** The CNN was re-run at seeds 7, 13, 29 and 41:
mean AUC 0.4927 / 0.4725 / 0.4821 / 0.4957. All four below 0.5. The
result is stable, not an unlucky draw.

## Why this null result is trustworthy

A broken pipeline and an efficient market produce identical output, so
the harness is verified in both directions:

- **Positive control** (`test_positive_control_harness_finds_a_planted_signal`):
  a label-correlated channel with heavy noise is planted into the input
  and must be recovered at AUC > 0.65 through the same purged folds. It
  passes. The harness *can* find signal when signal exists.
- **Causality tests**: perturbing bar t+1 must leave every feature row
  <= t bit-identical; trailing volatility at t must not move when bar t
  changes. Both asserted directly.
- **Split hygiene tests**: training indices strictly precede test indices
  with a full embargo gap; test blocks are disjoint.
- **Metric test**: a constant predictor must score AUC exactly 0.5
  (tie-aware ranking), so a degenerate model cannot look skilful.

17 tests, all passing. ruff clean, strict mypy clean.

## Honest reading

Five years of TSLA daily OHLCV contain, at this horizon and resolution,
no directional structure that any of these models can extract. Three
things bound the result rather than refute it:

1. **Sample size.** ~2,060 tradable samples; folds train on 343–1,332
   rows after the embargo and validation tail. That is very little for a
   neural network, even a 1,233-parameter one. Fold 0 is especially thin.
2. **One instrument.** No cross-sectional pooling was possible, unlike
   the crypto lake where 40 symbols can be pooled into ~80k samples.
3. **One data dimension.** Daily OHLCV only. No order flow, no options
   surface, no earnings calendar, no fundamentals.

What would change the answer is more data *dimensions*, not more model
capacity or more hyper-parameter search. Tuning the architecture against
this dataset would be fitting noise, and each variant tried makes any
eventual "success" less believable.

## Sensitivity — and the most instructive result in the study

Window/horizon combinations of (20, 3), (30, 5) and (60, 10) were run as
a robustness check. All at seed 7:

| window / horizon | cnn AUC | folds > 0.5 | cnn net bps | gbm AUC | gbm net bps |
|---|---|---|---|---|---|
| 20 / 3 | 0.5100 | 3/5 | +22.6 | 0.4992 | +12.2 |
| 30 / 5 | 0.4927 | 2/5 | −167.5 | 0.5117 | +46.2 |
| 60 / 10 | **0.5507** | **5/5** | −40.2 | 0.4808 | +28.2 |

The rank order of CNN vs GBM **flips** between configurations — the
signature of noise, not of one model being better.

The (60, 10) cell is the one worth dwelling on. Mean AUC 0.5507, above
0.5 on every single fold, minimum 0.501. Under a coin-flip null, 5/5
folds above 0.5 has probability 1/32 ≈ 3%. This is precisely the result
that gets written up as "CNN predicts TSLA direction with 55% AUC."

It does not survive a change of random seed:

| seed | mean AUC | folds > 0.5 | net bps/trade |
|---|---|---|---|
| 7 | 0.5507 | 5/5 | −40.2 |
| 13 | 0.5077 | 2/5 | −105.4 |
| 29 | 0.4767 | 1/5 | −181.7 |
| 41 | 0.5064 | 3/5 | −105.1 |
| 55 | 0.4942 | 2/5 | −107.5 |

Mean across the five seeds: **0.4991** — a coin flip. Seed 7 was a lucky
initialisation, and every seed loses money net of costs.

Two lessons, both worth more than a positive result would have been:

1. **A model can rank outcomes above chance and still lose money.** At
   (60, 10) seed 7 the CNN discriminated barrier touches at AUC 0.55 and
   still returned −40 bps per trade, because ranking which barrier gets
   touched is not the same as capturing the size of the move that pays.
   Reporting AUC without the economic test would have hidden this.
2. **Single-seed deep-learning results on ~2,000 samples are not
   evidence.** The spread across seeds (0.477 to 0.551) is wider than any
   effect being claimed. Any study of this kind that reports one seed and
   one train/test split should be assumed to be reporting its best draw.
