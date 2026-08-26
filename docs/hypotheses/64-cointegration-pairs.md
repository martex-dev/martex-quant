# Hypothesis 64 — Cointegrated Pairs (family F4, stat-arb)

Status: **PRE-REGISTERED 2026-08-27, NOT RUN.** Trials: **+12 → 141.**

First hypothesis of family **F4 (statistical arbitrage)** from
`docs/research/family-expansion-program.md`. Chosen first because it needs
**no new data** — the existing 40-coin daily lake supports it — and because
it is **market-neutral by construction**, so it attacks the correlation bar
structurally rather than hoping to clear it.

**Committed before any code for it exists.** No result exists at the time
of writing.

---

## 1. Claim

Some crypto pairs are **mechanically linked** — a layer-1 and its
ecosystem tokens, two exchange tokens, two assets tracking the same
narrative. Their price *ratio* should be mean-reverting even when neither
price is. Trading the spread — long the cheap leg, short the rich leg,
sized to equal notional — should produce a return stream that is **positive
after costs** and **uncorrelated with the direction of crypto**.

## 2. Why the edge should exist

Two mechanically-linked assets are substitutes. When one runs ahead, the
relative-value trade is to sell it and buy the laggard; capital doing that
pushes the ratio back. The premium compensates for:

- **divergence risk** — "mechanically linked" is a belief, not a contract,
  and links break (a chain dies, a token is delisted, a protocol forks);
- **funding and borrow cost** on the short leg;
- **the trade being crowded** exactly when it is most obvious.

`OBSERVATION` — a prior from this ledger, recorded before the run:
**H04 mean-reversion was REJECTED decisively** at the single-asset level,
and meta-finding 6 states *"frequency kills — everything at 1h or faster
dies after costs."* This hypothesis is mean reversion. It differs in that
it reverts a **relative** price with an economic link, at **daily**
frequency, not an absolute price intraday. If it dies, it is the second
confirmation that crypto does not revert.

## 3. When it should fail

- **Cointegration is unstable.** A relationship fitted on history can break
  permanently, and the trade then bleeds forever in the direction of the
  break. This is the classic stat-arb failure and it is not hypothetical.
- **Costs double.** Two legs, both traded, both paying the full cost model.
- **Shorting is not free.** Modelled here as a cost; see §7.

## 4. Specification

**Universe (FIXED NOW):** the 40 symbols in `config/universe.json`, daily
bars from the lake. No symbol may be added or dropped after seeing results.

**Pair formation — no look-ahead, and this is the whole game:**

- Pairs are selected on a **formation window** and traded **only on the
  subsequent window**, walk-forward. A pair's eligibility on day *t* may
  use data through *t−1* only.
- Formation: 365 days. Trading: the next 180 days. Roll forward, no
  overlap between a pair's formation data and its trading data.
- Eligibility: both legs must have complete data across the formation
  window, and the log-price spread must pass an **Engle-Granger
  cointegration test at p < 0.05**, with the hedge ratio taken from that
  regression and **frozen for the trading window**.

**Entry / exit — declared grid, 12 cells:**

- Signal: the spread's z-score against its formation-window mean and
  standard deviation.
- Enter when |z| ≥ `Z_IN`, exit when |z| ≤ `Z_OUT`, hard-stop the pair when
  |z| ≥ 4.0 (a break, not a wider opportunity).
- **`Z_IN` ∈ {1.5, 2.0, 2.5}** × **`Z_OUT` ∈ {0.0, 0.5}** ×
  **holding cap ∈ {30, 60} days** = **12 declared cells.**
- **All 12 cells are reported regardless of outcome. This hypothesis costs
  12 trials, not 1.** Primary cell nominated **now**: `Z_IN = 2.0`,
  `Z_OUT = 0.5`, cap 30 days.
- Position: equal notional per leg, equal capital across concurrently open
  pairs, cap of 10 open pairs. Capital not deployed sits in cash at zero.

**Costs:** the project's standard model on **both legs**
(`fee_bps = 10.0` + `half_spread_bps = 1.0` per side), i.e. ~44bp for a
full round trip of a pair — identical treatment to H62/H63.

**Engine:** the two-leg machinery added for carry
(`backtesting/carry.py`) generalized to two *different* symbols. Strictly
forward-marching, every quantity known at *t−1*.

## 5. Pre-registered bars

**Gate A — is it an edge at all?**

1. Mean daily net > 0, 95% block-bootstrap CI (30-day blocks) excluding zero.
2. Net CAGR ≥ 2%/yr after all costs.
3. Sharpe ≥ 1.0.
4. `DSR_global` ≥ 0.95 at N = 141.

**Gate B — is it the independent edge F4 was chosen for?**

5. **|correlation| with rotation-stop < 0.30**, timestamp-joined on the
   common window.
6. **|correlation| with the H63 carry stream < 0.30**, same method. A third
   edge is only worth adding if it is independent of *both* existing ones —
   quadrature only rewards genuine independence.

## 6. Disposition, declared in advance

- **Gate A + Gate B** → strategy-grade, third independent edge, eligible
  for a paper account and for the combined book.
- **Gate A only** → **STANDALONE-VIABLE**. Real, but correlated with
  something already run; not deployed, and it does **not** count toward the
  eight-edge target in the program document.
- **Gate A fails** → **KILLED**, and recorded as the second confirmation
  that crypto does not mean-revert at retail-reachable cost.

## 7. Known limitations, stated before results

- **Short borrow is modelled as a flat cost, not sourced.** Real
  availability and borrow rates for the short leg are not in the lake.
  Where a short leg is a perp, funding applies and is not modelled here
  either. **This makes the backtest optimistic by an unknown amount** and
  is the single largest caveat on any positive result.
- **Survivorship.** `config/universe.json` is the top 40 by volume as of
  2026-07-12. Coins that died are absent, which biases *against* observing
  the link-break failure mode this strategy is most exposed to.
- **Daily closes only.** No intraday spread dynamics; entries and exits
  occur at the next daily open with the standard one-bar latency.
- **The lake ends 2026-07-10.** Any run today uses data to that date.
