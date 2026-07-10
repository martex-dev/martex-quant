# Hypothesis 05 — Carry (Perpetual Funding Rates)

Status: DATA FEASIBILITY ONLY in Phase 3. Full test structurally blocked.

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

## Results

(filled by scripts/phase3_studies.py --study carry)
