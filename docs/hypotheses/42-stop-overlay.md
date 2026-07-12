# Hypothesis 42 — Chandelier Stop Overlay on the Deployed Specs

Status: **PRE-REGISTERED (2026-07-12)** — no test has run yet.
Trial ledger: +2 -> 104 (with batches 24-41 and FU-B1).

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
