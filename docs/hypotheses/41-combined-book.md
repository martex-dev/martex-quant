# Hypothesis 41 — Rotation + Crash-Bounce Combined Book

Status: **NOT ELIGIBLE (2026-07-12)** — fails the prop bar; verdict at
the bottom. Trial ledger: +1 -> 101 (with batches 24-32 and 33-40).

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

## Verdict (2026-07-12, scripts/h41_h42_fub1_studies.py, 2,880d OOS)

**NOT ELIGIBLE — fails bar 2 (prop pass).** The diversification thesis
was RIGHT: 317 bounce days, mean 77% idle cash deployed, overlay corr
to rotation only **0.188** (first genuinely low-corr sleeve found),
Sharpe 1.36 vs 1.10, CAGR +66.2% vs +31.2%, MDD -55.3% vs -58.0%
(bars 1 and 3 PASS), DSR 0.995. But prop pass @0.5x DROPS to 45.3%
from 62.8%: the overlay adds its variance on post-crash days — exactly
when daily moves are extreme — and trips the firm's 3% daily-loss rule.
Constraint geometry beats raw returns, third time now (Donchian, H41,
sizing scans).

Disposition per registration: rotation-alone stands as the runbook
engine. The combined book is archived as an OWN-CAPITAL candidate
(like carry): highest-CAGR validated-grade book we have, wrong shape
for the eval. Revisit post-funded with own capital; any resized/eval
variant (e.g. lower bounce sizing) would be a NEW registered spec.
