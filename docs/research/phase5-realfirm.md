# Phase 5 — Real Prop-Firm Options & Paper Trading (2026-07-11)

Inputs: the user's actual firm menu. Both 5k accounts, no time limits.
- **Option 1 (1-step)**: target +10%, max loss $300 (6%), daily loss 3%, 1:30.
- **Option 2 (2-step)**: +10% then +5%, max loss $500 (10%) per stage,
  daily loss 5%, 1:100. Cheaper fee.

Fees ASSUMED ($65 / $45) — breakevens reported below make the conclusion
robust to the real numbers. "Max loss" static-vs-trailing is UNKNOWN —
both simulated. Reproducible: scripts/phase5_realfirm.py (20k paths/cell).

## Headline finding: the daily-loss rule flips the engine choice

Under the earlier GENERIC futures-style rules, Donchian was the eval
engine. **This firm's 3% daily loss limit inverts that**: the Donchian
portfolio (16.4% ann. vol) trips daily-loss busts constantly, while the
vol-target portfolio (9.4% ann. vol) sails under the limit and can run at
1.5x. Constraint geometry, not raw returns, picks the strategy — again.

## Best configurations (vol-target momentum engine, EW 8 symbols)

| Option | Loss model | Best size | Pass (95% CI) | Median days | Breakeven funded value | EV @ $500 |
|---|---|---|---|---|---|---|
| 1-step | static | **1.5x** | **50.0% (49.3-50.7)** | **80** | $130 | **+$185** |
| 1-step | trailing | 1.0x | 39.1% (38.5-39.8) | 126 | $166 | +$131 |
| 2-step | static | 1.5x | 47.8% (47.1-48.5) | 178 | $94 | +$194 |
| 2-step | trailing | 1.5x | 40.2% (39.5-40.9) | 158 | $112 | +$156 |

## Recommendation

**Ask the firm ONE question first: is the max loss static or trailing?**
- **Static → Option 1** at 1.5x sizing: 50% pass, ~80 days median,
  EV/day ~2.3x better than Option 2 (the higher fee is irrelevant next
  to the time saved). This is the aggressive-but-compliant configuration.
- **Trailing → Option 2** at 1.25-1.5x: its wider $500 buffer matters
  much more when the buffer chases your peak; better breakeven too.
- Under EVERY variant, sizing beyond ~1.5x LOWERS the pass rate. 1:30
  leverage permits 30x; using more than ~1.5x is donating the fee.

Also verify: automation/bot policy (can kill the whole plan), weekend
holding rules (crypto trades 24/7 — a firm that flattens weekends
mutilates daily strategies), and whether their spreads differ materially
from the 1bp+impact modeled here (Donchian/vol-target trade a few times
a month per symbol, so moderate spread differences are tolerable).

## Futures vs crypto — resolved for this path

The 1:30/1:100 leverage menu means this is a CFD-style crypto firm, so
the validated crypto system maps directly; no futures build is needed
now. If a futures path (Topstep-style) opens later: the architecture is
instrument-agnostic by design — it needs a futures data collector
(Databento), contract-roll handling in the store, and session-aware
validation. Deferred until a futures firm is actually on the table.

## Paper trading is LIVE (Phase 5 core)

`python -m trading_bot.live.paper --strategy vol-target` — run daily,
shortly after 00:00 UTC. First real run (2026-07-11): parameters
selected per symbol, exposures all 0.0 — trailing momentum is currently
negative, so the system's first live decision was to hold no position.
State/journal/equity in data/paper/vol-target/. The paper record is the
input to the Phase 5 exit gate: live results statistically consistent
with backtest expectations over 2-3 months, and fill-price drift within
the cost model. No evaluation fee should be paid before that gate, and
no real capital decision happens on paper results alone.
