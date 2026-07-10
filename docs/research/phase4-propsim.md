# Phase 4 — Prop-Firm Evaluation EV (2026-07-11)

Input: the Phase 3 candidate's out-of-sample daily returns (1,080 days,
mean +0.086%/day, 36.1% annualized vol — costs included). Block bootstrap
(10-day blocks), 20,000 paths per cell. Reproducible:
`scripts/phase4_propsim.py`.

## The numbers (Phase 4 exit criterion)

**GENERIC-A** (50k, +6% target, 4% EOD-trailing, 2% daily loss, no time
limit, $170 fee):
- Best sizing: **0.25x notional → 37.3% pass probability
  (95% CI 36.7–38.0%)**, 62.6% bust, median 64 days to pass.
- **EV per attempt: +$576 / +$1,696 / +$3,563** at assumed funded-account
  values of $2k / $5k / $10k. Breakeven funded value: ~$456.

**GENERIC-B** (50k, +8% target, 3% trailing, 2% daily, 90-day limit,
$100 fee):
- Best sizing: 1.0x → 23.6% pass (CI 23.0–24.2%), EV +$371 to +$2,256
  over the same assumed-value range. Breakeven: ~$424.

The sizing curve is the real lesson: at 0.1x the strategy can't reach the
target (46% timeouts on A, 95% on B); at 1x+ the trailing drawdown eats
~70% of paths. The optimum is a narrow band, and it is nowhere near
full sizing — the constraint set, not the return stream, dictates size.

## Why these numbers must not be taken at face value

1. **The candidate itself is unvalidated** (DSR 0.828 < 0.95): if the
   edge is selection luck, true pass rates converge to the no-skill rate
   and every EV above turns negative after repeated attempts.
2. **EOD trailing approximation**: real trailing drawdowns bite intraday;
   all pass rates here are upper bounds.
3. **GENERIC rulesets**: real firms' current rules are unverified, several
   prohibit automation outright, and evals are on FUTURES while the
   candidate trades crypto spot — this simulation prices the constraint
   geometry, not a specific firm's product.
4. Funded-account value is the caller's assumption, not an output.

## Verdict

The machinery works end to end and the answer is genuinely useful: under
these constraint sets, the candidate-as-is is an EV-positive evaluation
bet only if the edge is real, and optimal sizing is ~0.25x. The blocking
items before any real fee: validate the edge (extend history — queued),
verify actual firm rules and automation policy, and decide the
futures-vs-crypto instrument question.

Phase 4 core exit criteria: MET (policies + latched kill switch + this EV
analysis with confidence intervals).
