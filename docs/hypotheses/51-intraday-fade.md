# Hypothesis 51 — Intraday Fade Strategies (from H44/H45 inversions)

Status: **BOTH KILLED at the registered taker-floor bars (2026-07-12).**
Trial ledger: +2 -> 114. Verdicts at the bottom; one honest loose end
(true maker-fill model) noted for a possible H52.

## Stated reason (per process)

H44/H45 (pre-registered, two-sided-reported) found the two most
popular retail intraday entries are SIGNIFICANTLY inverted in crypto:
fading the opening-range break earns +0.16%/event (CI clear), fading
the first-hour move +0.20%/event — 4-5x the maker toll, the first
intraday effects in 112 trials that clear costs with margin. Info
signal != strategy: these must survive an event-driven build with an
honest fill model, portfolio construction, and the full cost stack.

## Specs (both on the 12-symbol Bybit 15m panel, 2021+)

- **51a — Fade-ORB** (+1 trial): day = 00:00 UTC; range = first hour.
  On the FIRST 15m close beyond the range within hours 1-5, enter
  OPPOSITE to the break at the next bar's open (taker floor case);
  exit at the day's last bar close (taker). Cost floor: 0.055% x 2 =
  0.11% RT vs +0.16% gross edge. A maker-entry variant (limit at the
  signal close, filled only if the next bar's range crosses it;
  missed fills = missed trades) is reported alongside.
- **51b — Fade first hour** (+1 trial): at 01:00 UTC enter opposite
  to the 00:00-01:00 direction at the 01:00 bar open (taker floor);
  exit at day close. Same maker variant reported.

Portfolio: equal-weight across symbols with an active signal that day,
sized to the 30% annual vol target on the trailing 30d of strategy
returns (hyp-06 dial), gross capped at 1.0.

## Verdict bars (each variant)

1. Net Sharpe (taker-floor case) > 0.7 on the full panel, AND
2. timestamp-joined corr vs rotation-stop OOS daily returns < 0.30
   (diversifier bar), OR net Sharpe > 1.10 standalone (champion bar).
3. Prop-sim (real firm rules, 20k paths) reported at 0.5x/1x/2x/4x —
   informational, not a bar, since the sprint account already has its
   engine; H51's role is the DIVERSIFYING SLEEVE (its returns come
   from different hours and the opposite sign of trend).

Pass -> eligible for paper (5th account) and for joining the funded
account book per runbook after the sprint resolves. Fail -> the
inversion joins H16's archive (real info, unusable as strategy).

## Honest caveats up front

- Fade strategies SELL volatility spikes: tail risk on trend days is
  real (a true breakout day loses all day). The vol-target dial and
  per-day one-shot entry cap it; the backtest measures it.
- Effect discovered and strategy tested on the same history (family-
  selection caveat, same as H42); a paper record guards deployment.
- Bybit perp data starts 2021 — no 2017-2020 regimes in this panel.

## Verdicts (2026-07-12, scripts/h51_fade_study.py, 1,989 days)

- **51a fade-ORB: KILLED.** Taker floor Sharpe 0.14 (CAGR -0.8%).
  The 0.16%/event info edge dies against the ~0.13% real round trip.
  Maker-proxy sensitivity: Sharpe 0.59 — still under the bar.
- **51b fade-first-hour: KILLED as registered.** Taker floor Sharpe
  0.44 < 0.7 (bar 1 explicitly named the taker-floor case). The
  maker-proxy run printed Sharpe 0.90, corr +0.01 and the script's
  generic bar labeled it CANDIDATE — that label is NOT a verdict: the
  proxy discounts fees but still assumes every entry fills. The doc's
  true maker variant (limit fills that can be MISSED — and fades miss
  their best entries) was not actually modeled; the truth lies between
  0.44 and 0.90.

## Loose end (possible H52, NOT yet registered)

corr +0.01 to rotation-stop makes 51b the most independent return
stream ever measured here — IF the edge survives honest maker-fill
modeling. Graduating requires: engine limit-order support with
crossed-range fill logic, then a new pre-registered trial. Queued
BEHIND the sprint build; register only with the engine extension in
hand. Everything else in the intraday family is closed.
