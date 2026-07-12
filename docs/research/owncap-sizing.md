# Own-Capital Growth-Optimal Sizing (2026-07-12)

Descriptive sizing-policy analysis on VALIDATED streams — 0 new ledger
trials (same category as the phase-4 prop sims). Reproducible:
scripts/owncap_sizing_study.py. Context: the user's stated goal
(CLAUDE.md) is income-scale returns, aspiration >= 20%/month.

Model: daily-rebalanced leverage k on the 43a own-capital book
(rotation-stop + crash-bounce overlay, 7.9y OOS stream) with financing
drag 0.05%/day (~18%/yr) on the borrowed fraction. Ruin = 90% drawdown.

## Results — 43a book

| Leverage | CAGR | MDD | Mean 30d | 30d >= +20% | 30d <= -20% | Worst 30d |
|---|---|---|---|---|---|---|
| 1.0x | +79% | -38% | +5.7% | 11% | 0% | -20% |
| 1.5x | +104% | -54% | +7.8% | 20% | 3% | -30% |
| **2.0x** | **+122%** | **-69%** | **+10.0%** | **28%** | **10%** | **-39%** |
| 3.0x | +127% | -88% | +14.6% | 35% | 20% | -56% |
| 4.0x+ | RUINED | -90%+ | — | — | — | — |

## What this says (the honest version)

1. **The Kelly cliff is between 2x and 3x.** 3x adds almost no CAGR
   over 2x (+127 vs +122) while drawdown goes from -69% to -88% — one
   bad stretch from dead. 4x is ruin on the historical path, full stop.
   Maximum survivable aggression on this book: **~2x**.
2. **A sustained 20%/month average is NOT available from this book at
   any surviving leverage.** The best survivable mean is ~+10%/month
   at 2x (+14.6% at near-ruin 3x). What IS available at 2x: 28% of all
   months exceed +20% — but 10% of months are worse than -20%, and the
   worst is -39%.
3. **The route to higher sustainable monthly returns is a higher-Sharpe
   book, not more leverage.** Sharpe caps survivable growth; leverage
   only moves you along the curve until the cliff. Every genuinely
   independent edge added (carry, VRP backlog, future low-corr finds)
   raises the ceiling itself. This is now a primary research objective.
4. Financing assumption matters at high k: real CFD swap rates on
   crypto are often WORSE than the 18%/yr modeled — verify before any
   live leverage decision.

## Income ladder implied (if edges hold; conditional numbers, not promises)

- Funded 5k (firm rules cap ~1.5x eval-style sizing): realistic
  ~4-6%/mo average -> $200-300/mo, scaling via bigger/multiple
  accounts — the firm's capital is the cheap leverage.
- Own capital at 2x on the 43a book: ~10%/mo AVERAGE with brutal
  variance; $5k -> ~$11k over a year on the mean path. Reaches a
  $1k/mo run-rate when the account is ~$10k, not at $5k.
- Both paths compound; neither pays 20%/mo on month one. Anyone
  promising that from a Sharpe-1.5 book is describing leverage they
  have not survived.
