# Hypothesis 05 — Carry (Perpetual Funding Rates)

Status: **FEASIBILITY CONFIRMED** (2026-07-11) — premium clears the bar;
infrastructure build approved for a future phase, after Phase 4.

## Hypothesis and rationale

Perpetual futures pay funding from the crowded side to the other side —
historically longs pay shorts in crypto. A delta-neutral position (long
spot + short perp) collects that funding as a carry premium. The risk
story: the collector is selling insurance against squeezes/dislocations;
the premium is compensation for basis risk, liquidation risk during
spikes, and exchange counterparty risk.

## Why only a feasibility study now

A real backtest needs (a) funding-rate history as a first-class dataset,
(b) a two-leg (spot + perp) portfolio in the engine, (c) margin/liquidation
modeling. The engine is single-instrument spot by explicit Phase 2 MVP
decision. Faking it would violate the backtesting rules, so Phase 3
delivers: measure the gross premium from real Binance funding history and
decide whether building the infrastructure is justified.

## Pre-registered decision standard

Build the full infrastructure (new phase-3.5 scope) only if the measured
gross annualized funding premium on majors over the last ~3-4 years
exceeds ~5%/yr — below that, fees, basis bleed, and tail risk almost
certainly consume it.

## Results (2026-07-11, 4y of Binance USDT-perp funding history)

Gross annualized funding premium, 2022-07 .. 2026-07 (~4,380 8h records
per symbol): BTC +6.86%, ETH +6.46%, XRP +5.81%, DOGE +7.90%, SOL -5.91%.

4/5 majors clear the pre-registered 5%/yr gross bar. SOL's negative mean
is a reminder the premium is regime- and symbol-dependent, not free money.
Note: an earlier run of this study read only the most recent 500 records
(pagination bug, fixed same day) and showed ~0-1% — the recent regime is
much thinner than the 4y mean, which itself tempers enthusiasm.

Decision per the pre-registered standard: the premium justifies building
the real test — funding-rate dataset in the lake, two-leg (spot+perp)
portfolio support, margin/liquidation modeling. Scheduled AFTER Phase 4:
the risk engine matters more than a second strategy family, and the
current candidate (hypothesis 02) needs it too.
