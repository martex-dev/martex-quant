# Hypothesis 09 — Calendar Effects

Status: UNDER TEST (pre-registered before results).

## Rationale

Flow-driven periodicity: institutional rebalancing clusters at month
boundaries (turn-of-month premium is documented in equities for decades);
weekend crypto trades without TradFi flow; perp funding settles at fixed
UTC times (00/08/16) creating potential hedging-flow ripples. All three
are timing claims, testable on data already in the lake.

## Specification (three FIXED sub-claims; no other slices may be examined)

Pooled 8-symbol panel, full lake depth (2017+), block bootstrap (30-day
date blocks, cross-section intact), 95% CIs.

- **09a Turn-of-month** (daily): mean return on ToM days (last 2 + first
  2 calendar days of each month) minus all other days. Directional claim:
  POSITIVE (equity literature). PASS: CI > 0.
- **09b Weekend** (daily): mean return Sat+Sun minus weekdays. No
  directional prior — two-sided. PASS: CI excludes 0.
- **09c Funding-settlement hour** (hourly): mean return of the 1h bars
  opening at 00/08/16 UTC minus all other hours. Two-sided. PASS: CI
  excludes 0.

Trial ledger: +3 -> 47. Any PASS graduates that sub-claim to a
strategy-grade hypothesis (costs, walk-forward) — a timing overlay is
only tradable if it survives fees, which for 09c is doubtful a priori
(hourly costs killed hypothesis 01).

## Verdict

(after the run)
