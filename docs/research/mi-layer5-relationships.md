# MI Lab Layer 5 — Relationship research engine

Date: 2026-08-11. First layer that can GENERATE trials, so it is built to
make dredging awkward rather than convenient.

## What it does

Answers "does condition X predict outcome Y?" using **exactly the
measurement the corpus already used**: split a panel by a condition, compare
mean forward outcomes, get a day-block bootstrap confidence interval with the
cross-section held intact.

## Validation: it reproduces a published result exactly

The engine re-derives H40's trailing-stop finding to the last digit:

```
published:  n=10247  diff -8.77%  CI [-15.57%, -2.17%]  SIGNAL
engine:     n=10247  diff -8.77%  CI [-15.57%, -2.17%]
```

Same panel, same condition, same seed (4010) and block (30). This is the
evidence that findings from this engine are comparable with the existing
ledger rather than measuring something subtly different.

## Anti-dredging design

* **A test cannot run outside a declared family.** `run_family` raises if
  more cells are supplied than the family declared.
* **Declared, not run, is the FDR denominator.** Declaring 50 and running 2
  is corrected for 50 — a test asserts the per-cell bar is identical whether
  a family declares 2 or 50, so declaring broadly buys no discount.
* **Every cell goes through Benjamini-Yekutieli** at the family's allocated
  share of the global budget. The raw CI decision is reported alongside for
  continuity with the corpus, but the FDR verdict is the operative one.
* **Pure noise yields no discoveries** — asserted directly on a random panel.
* **Horizon profiles.** An effect that appears at exactly one horizon and
  vanishes either side is far weaker evidence than one that decays smoothly.
  The profile makes that visible instead of leaving it to a lucky cell.

## New machinery: the bootstrap p-value

FDR needs p-values; the corpus only ever used "does the 95% CI exclude
zero". `two_group_diff_pvalue` adds a two-sided bootstrap p-value, floored at
`1 / n_boot` because a bootstrap cannot resolve finer than one draw — always
reported as a bound, never as "p = 0".

This changes no historical decision. It shares one implementation of the RNG
contract with `two_group_diff_ci` via an extracted private draw loop, and the
29 goldens verify the extraction changed nothing.

A test checks the new statistic against the old decision: a CI excluding zero
must carry p < 0.05, and one including it must not.

## Not included, deliberately

Conditional (regime-split) analysis is supported mechanically — a condition
is just an expression — but the accounting design caps strategy × market-state
work at research-level observation until minimum episode-count rules are
pre-registered. That limit is unchanged here.
