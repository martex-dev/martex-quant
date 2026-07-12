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
- Mandatory-SL compliance: resting stop order per position at the
  chandelier level (2xATR14 below entry-side 30d high), which is the
  strategy's own exit anyway. Verify with support that a resting stop
  order satisfies the rule (pre-purchase question).
- Execution: Bybit API via ccxt adapter (live/bybit_broker.py, to be
  built), DRY-RUN default, --live flag, same shared decision core.

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
