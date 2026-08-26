# Hypothesis 62 — Delta-Neutral Funding Carry (strategy-grade)

Status: **PRE-REGISTERED 2026-08-27, NOT RUN.** Trials: +1 → 126.

Builds on `docs/hypotheses/05-carry-funding.md` (FEASIBILITY CONFIRMED
2026-07-11: gross annualized premium BTC +6.86%, ETH +6.46%, XRP +5.81%,
DOGE +7.90%, SOL −5.91%; 4/5 majors cleared the pre-registered 5%/yr bar).
H05 approved the infrastructure build and deferred it "after Phase 4".
Phase 4 completed; this is that build and its real test.

**This document is committed before any carry backtest runs.** No result
exists at the time of writing.

---

## 1. Claim

Holding **long spot + short perpetual of equal notional** in the same
asset produces a position with ~zero directional exposure that collects
the perpetual funding payment. Net of all trading costs and fully
collateralized, this produces a positive return stream with a **higher
Sharpe than the deployed momentum book** and **low correlation to it**.

## 2. Why the edge should exist

Perpetual futures have no expiry, so exchanges tether them to spot with a
funding payment every 8 hours: when the perp trades above spot (more
leveraged longs than shorts, the normal crypto state) **longs pay shorts**.

The carry collector is **selling insurance**. Leveraged longs want exposure
and pay to hold it. The premium compensates for:

- **basis risk** — spot and perp can diverge and there is no expiry forcing
  convergence;
- **liquidation risk** — a violent upward squeeze damages the short leg
  fastest, exactly when funding spikes;
- **counterparty risk** — the position lives on an exchange (FTX).

## 3. When it should fail

- **Bear regimes / negative funding.** When shorts crowd, funding inverts
  and the collector pays. H05 already measured this: SOL's 4-year mean was
  **−5.91%**.
- **Thin-premium regimes.** H05 recorded explicitly that the *recent*
  funding regime is much thinner than the 4-year mean.
- **Squeezes.** The insurance-seller's tail: many small premiums, then one
  large claim.

## 4. Specification — ZERO tunable parameters

- **Universe (FIXED NOW, before running):** the 8 symbols with complete
  three-way data — ADAUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LTCUSDT,
  SOLUSDT, XRPUSDT. No symbol may be added or dropped after seeing results.
- **Position:** equal capital allocation across all 8, held **always-on**.
  No funding-sign filter, no timing rule, no regime switch. There is
  nothing to tune.
- **Collateralization: 1× (full).** Per symbol allocation `A`, spot
  notional `S = A/2` and perp margin `M = A/2`, short perp notional `= S`.
  Perp leg leverage is therefore **1.0**, and liquidation of the short
  requires a **+100%** adverse move. Carry is earned on `S`, i.e. half the
  deployed capital, so the expected net yield is roughly **half** H05's
  gross figures before costs.
- **Funding accrual:** the actual 8-hour `rate` from `data/funding/`,
  credited to the short leg on the real settlement stamps.
- **Rebalance:** daily to equal notional, with costs charged on turnover.
- **Costs:** the project's standard model on **both legs** —
  `fee_bps = 10.0` taker + `half_spread_bps = 1.0` per side. A pair
  entry/exit is therefore ~**44bp** round trip, double a spot-only trade.
- **Engine:** purpose-built two-leg daily backtest, strictly
  forward-marching, no look-ahead. Spot from the lake, perp from
  `data/perp/`, funding from `data/funding/`.

**Leverage is NOT part of this hypothesis.** Any leverage sweep afterwards
is a descriptive sizing study on a validated stream — the
`docs/research/owncap-sizing.md` precedent, 0 trials, publishes the whole
curve and selects nothing.

## 5. Pre-registered bars — ALL FIVE required

1. **Mean daily net return > 0**, with a 95% block-bootstrap CI (30-day
   blocks) **excluding zero**, costs already inside.
2. **Net annualized return ≥ 2%/yr** after all costs, fully collateralized.
3. **Sharpe ≥ 1.0.**
4. **|correlation| with rotation-stop < 0.30** on the timestamp-joined
   common window — the project's own screen threshold from H43. This is the
   bar that decides whether carry is a genuine diversifier or just another
   long-crypto book in disguise.
5. **`DSR_global` ≥ 0.95** at the post-run trial count (126).

**Passing four of five is not a pass.**

Bar 4 is the load-bearing one for the project's stated objective:
`owncap-sizing.md` §3 records that the route to higher sustainable returns
is a higher-Sharpe book via genuinely independent edges, and meta-finding 5
records that every long-crypto momentum book measured so far correlates
0.52–0.82 with every other one. If carry fails bar 4 it is not the
independent edge this was built for, whatever its Sharpe.

## 6. Disposition rules, declared in advance

- **All five bars pass** → strategy-grade, eligible for its own paper
  account (one spec per record, fresh $5,000).
- **Bars 1, 2, 3, 5 pass but bar 4 fails** → closed **STANDALONE-VIABLE**
  per `docs/research/standalone-viable-amendment.md`: a real edge that is
  not the diversifier it was built to be. Not deployed.
- **Bar 1 or 2 fails** → **KILLED**, and H05's feasibility verdict is
  recorded as not having survived contact with costs and collateralization.
- Whatever happens, the result is recorded. A negative here is a real
  result: it would mean the last untested family reachable from a retail
  spot+perp account does not pay after costs.

## 7. Known limitations, stated before results

- **Intraday liquidation is unmodelled.** Perp data is daily closes only,
  so a within-day squeeze that would liquidate the short leg is invisible.
  At 1× collateralization this is close to harmless (it needs +100%
  intraday), and it is the reason 1× is specified rather than something
  capital-efficient. **Any future levered version must treat this as an
  open risk, not an inherited safety.**
- **No exchange-failure model.** Counterparty risk is named in §2 and is
  not priced anywhere in the backtest.
- **Funding is taken as realized history**, not forecast. This is a carry
  harvest, not a funding-prediction strategy.
