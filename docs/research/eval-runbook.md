# Evaluation Runbook (1-step 5k, $51.80)

Pre-registered procedure — written before the eval is purchased so the
plan is followed, not improvised. Firm rules: +10% target, $300 STATIC
max loss, 3% daily loss, no time limit, 1:30, MT5.

## Gate (before buying)

- [ ] Paper shakedown >= 2 weeks with no operational failures
      (missed runs, data errors, crashed selections) in data/paper/.
- [ ] Intraday daily-loss guard built and tested.
- [ ] This runbook reviewed once more.

## Day 0 — after purchase, BEFORE any order

1. Log the firm's MT5 credentials into the terminal (GUI, human only).
2. `python -m trading_bot.live.trade --strategy vol-target` (DRY RUN).
3. List their crypto symbols; write config/symbol_map.json (their names
   for our 8 USDT pairs). Verify per symbol: contract size, volume_min/
   step (our slice sizes ~0.9 x 1.5 x $625 / price must clear volume_min),
   spread vs the 1bp modeled (note it in the journal).
4. Re-run dry run with --symbol-map; confirm 8 sensible orders, zero
   errors. If ANY symbol is missing at the firm: STOP, recompute the
   portfolio math for the reduced universe before going live.

## Day 1+ — live

- Scheduled daily run switches to live/trade.py --live (RISK_SCALE 1.5).
- Intraday guard runs continuously; flattens at -2.5% day loss (firm
  busts at -3%); a guard trigger ends trading for that UTC day.
- Static max loss self-enforced at -5% ($250) via latched kill: if
  equity hits $4,750, the system goes flat and STAYS flat (firm busts
  at $4,700 — we keep a $50 buffer and the account survives, wounded).
- NO parameter changes, NO sizing changes, NO manual trades during the
  eval. The sim priced THIS system; a modified system has no sim.

## Failure handling (decided now, calmly)

- Bust or latched kill -> stop. Review journal vs sim expectations.
  ONE immediate retry attempt is pre-approved (budgeted 2 x $51.80)
  IF AND ONLY IF the failure was within simulated behavior (a normal
  drawdown path), not an operational bug. Bug -> fix, re-shakedown.
- Two failures -> stop entirely, back to research. Re-entry requires
  new evidence (longer paper record or improved system), not hope.

## Success handling

- Passed -> funded account. Sizing DROPS to 1.0x (funded stage is
  survival, not sprint — phase5-realfirm.md analysis). Payout policy:
  withdraw at every threshold the firm allows; never let the funded
  account balance become the emotional yardstick.
