# Hypothesis 41 — Rotation + Crash-Bounce Combined Book

Status: **PRE-REGISTERED (2026-07-12)** — no test has run yet.
Trial ledger: +1 -> 101 (with batches 24-32 and 33-40).

## The claim

CrashBounce was validated as an OVERLAY shape (H22: 78% flat, +0.441%
per held day net). Rotation-wide is the champion (Sharpe 1.10, DSR
0.990, prop 62.9% @0.5x) but holds concentrated top-2 positions and
often has idle cash after the vol scaler. The combined book deploys
CrashBounce's one-day EW-alts trade out of the ROTATION account's idle
cash on BTC-crash triggers (BTC day < -3%), leaving rotation positions
untouched. If the two return streams are as independent as their
mechanisms suggest (slow momentum vs one-day reactive bounce), the
combination should raise Sharpe without raising drawdown materially.

## Protocol

Common OOS window replay (h12/h22 machinery): rotation walk-forward
stream per the champion spec; on trigger days, idle cash (1 - rotation
gross, floor 0) goes EW into the alt universe for one day at engine
costs. Timestamp-joined correlation of the two component streams
reported (H12 lesson: no tail-count alignment).

## Verdict bars (all must pass on the SAME common window)

1. Combined OOS Sharpe > rotation-alone OOS Sharpe on that window.
2. Combined prop pass @0.5x (real firm 1-step static rules, 20k
   paths) > rotation-alone on that window.
3. Combined MDD no worse than rotation-alone by more than 5 points.

Pass -> combined book becomes the ELIGIBLE eval-engine candidate
(replacing rotation-alone in the runbook decision, gate unchanged).
Fail -> rotation-alone stands; the overlay stays a separate paper
account.

## What is deliberately NOT registered

Further 50/50 sleeve blends (V1 + rotation etc.): H12 measured true
sleeve correlation 0.77 — averaging correlated books insures nothing.
No new blend gets registered until a component with timestamp-joined
corr < 0.3 vs the champion exists (candidates: H35 pairs sleeve,
post-eval carry).
