# Hypothesis 51 — Intraday Fade Strategies (from H44/H45 inversions)

Status: **PRE-REGISTERED (2026-07-12)** — no test has run yet.
Trial ledger: +2 -> 114.

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
