# Hypothesis 42 — Chandelier Stop Overlay on the Deployed Specs

> **⚠ CORRECTED 2026-08-28 by H71 (`docs/hypotheses/71-point-in-time-universe.md`).**
> Every figure in this document ranks inside `config/universe.json`, which
> selects its 40 symbols by volume **as of 2026-07-12 — the end of the
> sample**. Re-run on a point-in-time universe, the deployed spec keeps
> **58% of its Sharpe (1.47 → 0.86)** and **49% of its CAGR (+42.91% →
> +21.06%)**, and clears neither the Sharpe ≥ 1.0 nor the DSR ≥ 0.95 bar.
> The point-in-time figure is itself an **upper bound** (coins delisted
> before today cannot enter it either).
> **The numbers below are NOT altered** — they are what was computed, and
> rewriting them would rewrite research history. Read them as
> hindsight-universe figures. **rotation-stop is off the evaluation path.**


Status: **BOTH CANDIDATE (2026-07-12)** — first strategy-grade result
to beat the champion on every metric. Trial ledger: +2 -> 104 (with
batches 24-41 and FU-B1). Verdicts at the bottom.

## Why this reopens the switch family (stated reason, per process)

H40's info test (two-sided, pre-registered) found that within uptrends
(r90 > 0), symbol-days where price sits >= 2xATR14 below the trailing
30d close-high are followed by fwd30 returns 8.77 points WORSE than
uptrend baseline (CI [-15.57, -2.17]). That is exactly the state the
deployed long specs can be caught holding: V1 stays long until r_L
flips; rotation until the coin drops out of the top-2 or its momentum
gate closes. A stop is a switch, and switches have died here before
(03, 14, 37, 38) — but none of those had a significant info-level
signal behind them. This one does; it earns one strategy-grade shot.

## Spec (zero free parameters, both taken from H40 as-tested)

Stop state per symbol: fires when close <= (trailing 30d close-high -
2 x ATR14); clears when close makes a NEW trailing 30d close-high.
While stopped, the symbol is treated as ineligible to hold.

- 42a — V1 + stop (+1 trial): VolTargetMomentum protocol unchanged
  (8 majors, walk-forward L, EW slots, vol targeting); a stopped
  symbol's slot goes to cash. Bars: OOS Sharpe > V1's on the identical
  protocol computed in the same run, AND prop pass @1.5x (real firm
  1-step static, 20k paths) > V1's computed in the same run.
- 42b — Rotation + stop (+1 trial): champion wide spec unchanged
  (K=2, L walk-forward {30,90}, abs gate, 30% vol budget); stopped
  symbols are excluded from the ranking pool at selection time. Bars:
  OOS Sharpe > champion's computed in the same run, AND prop pass
  @0.5x > champion's computed in the same run.

Both comparisons are same-window, same-engine, same-costs — the bar is
the DEPLOYED system, not zero (incremental rule). DSR reported against
the full ledger (104) for the record.

## Failure handling

Either variant failing its bars closes that variant. Both failing
closes the stop family entirely: the info signal then joins H16's
7d-ranking in the "real information, unusable inside the strategy"
archive (likely mechanism: the stop exits vol expansions that the vol
targeting already sizes down, and re-entry at fresh 30d highs pays
breakout premium the momentum gate already avoided).

## Verdicts (2026-07-12, scripts/h41_h42_fub1_studies.py)

- **42a V1+stop: CANDIDATE.** 1,710d common window: Sharpe 0.84 vs
  V1 0.53, CAGR +9.1% vs +7.5%, MDD **-13.3% vs -25.1%**, prop @1.5x
  31.1% vs 27.9% (both bars PASS). DSR 0.744. Slower passes (median
  53d vs 28d) — the stop trades speed for survival, the funded-stage
  profile.
- **42b rotation+stop: CANDIDATE — beats the champion on everything.**
  2,880d OOS window: Sharpe **1.47 vs 1.10**, CAGR +42.9% vs +31.2%,
  MDD **-29.0% vs -58.0%**, prop @0.5x **73.0% vs 62.8%** (median 106d
  vs 101d). **DSR 0.992 vs the full 104-trial ledger — above the 0.95
  absolute bar.** The mechanism is coherent with the H40 info signal:
  rotation's worst stretches were riding top-2 coins through 2xATR
  breakdowns that the momentum gate exits too slowly; the chandelier
  latch cuts exactly that tail.

## Honest caveats (recorded at validation time)

- The stop constants (2xATR14, 30d high) were fixed a priori, not
  tuned — but the FAMILY was selected on the same history the strategy
  test ran on (true of every hypothesis here; walk-forward guards
  params, not family selection). The paper record is the out-of-sample
  test that guards this.
- Sharpe 1.47 with halved MDD from one overlay is a large jump —
  treat with the standard young-result skepticism until it has a paper
  record. Champion status in the runbook is a GATE-DAY decision, not
  automatic.
- Same residual survivorship caveat as rotation (fully-delisted coins
  absent).

## Disposition

42b is eligible for a paper account (validated-grade by the ledger's
own standard). Whether it (a) gets a fourth paper account, (b) replaces
the rotation record (archive + fresh $5,000), or (c) waits for the
07-25 gate is a HUMAN decision — flagged in PROJECT_STATE next actions.
The eval-runbook engine choice at the gate should weigh: rotation has
the older paper record; rotation+stop has strictly better simulated
numbers but zero paper days.
