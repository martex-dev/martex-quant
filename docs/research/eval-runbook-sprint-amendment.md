# Eval Runbook — July Sprint Amendment (pre-registered 2026-07-12)

Amends docs/research/eval-runbook.md for the July sprint ONLY.
Committed BEFORE any purchase, per the live-gating rule. Numbers and
firm facts: docs/research/july-sprint.md.

## Firm & product

HyroTrader 1-step 5,000 USDT challenge, $119 (refunded at first
payout). Rules as published 2026-07-12: target +10%, daily drawdown
4%, max loss 6%, minimum 10 trading days, unlimited time, mandatory
stop-loss per position, max risk 3%/trade, payout >= $100 net profit
1 calendar day after first funded trade, split 70%.

## Sprint configuration

- Engine: **43a book** — StopVolTargetRotation (K=2, L walk-forward
  {30,90}, wide universe) + crash-bounce overlay from idle cash
  (BTC day < -3% -> EW alts one day). live/decision.py sprint_weights.
- Sizing: RISK_SCALE **4.0** during the sprint window (deadline
  physics, scripts/july_sprint_study.py). Expected: fast pass or fast
  bust; busts are retries.
- Retry budget: up to **3 attempts** (~$357 max fees, refundable on
  eventual success). A 4th attempt requires a new human decision.
- Guard: daily trip at -3.5% (inside the firm's 4%), static latch at
  $4,750 equivalent; KILLED latch cleared only by human (unchanged).
- Execution: Bybit API via ccxt adapter (live/bybit_broker.py, to be
  built), DRY-RUN default, --live flag, same shared decision core.

## Firm-rule adjustments (support answers 2026-07-12, AI agent)

1. **Per-trade loss cap 3% of initial balance ($150)**: every position
   carries a resting stop at min(chandelier level, the price where the
   position's loss = $150). SL itself is no longer mandatory, but the
   loss cap is a hard rule; the stop enforces it mechanically. Extra
   whipsaw risk vs the validated chandelier accepted and monitored.
2. **Low-cap rule (max 5% of initial balance across assets with
   <$100M mcap / $500K-5M 24h vol / Innovation Zone)**: day-0 task
   classifies every universe symbol; non-compliant symbols are
   EXCLUDED from the eval account's universe
   (config/universe_hyro.json). If >8 of 40 are excluded, re-run the
   wf validation on the reduced universe before first order (+1
   pre-registered trial).
3. **Gross exposure clamp**: open notional hard-capped at 1.8x initial
   balance (firm caps at 2x). Effective sizing = min(4.0 x weights,
   1.8 gross). Margin use stays far under the 25% funded cap at 100x
   available leverage.
4. **Consistency-rule residual risk** (counting undefined in docs):
   accepted. Mitigation: near-daily rebalances spread realized P&L
   across many closed trades over the >=10-day minimum; if the largest
   single trade approaches 40% of total profit at target, keep trading
   (unlimited time) to dilute before the pass is claimed. Dashboard
   monitors the ratio.

## Switch-down rule (non-negotiable, automated)

The LATER of (funded account activated) or (Aug 1): RISK_SCALE drops
to 1.0 and the engine reverts to rotation-stop alone (the validated
patient spec, prop pass 73.0% @0.5x-equivalents; final funded sizing
decision re-simulated then). 4x is sprint physics only; long-run 4x
is ruin (docs/research/owncap-sizing.md).

## Abort conditions

- Support answers invalidate a load-bearing assumption (consistency
  rule blocks 2-position books; bots not actually allowed in writing;
  low-cap 5% exposure rule blocks the universe) -> sprint OFF,
  fall back to the Jul 25 gate plan.
- 3 attempts busted -> sprint OFF, post-mortem, gate plan resumes.
- Any automation failure during an attempt -> flatten via guard,
  human review before the next order.
