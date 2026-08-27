# Family Expansion Program — where the untested edges actually are

Date: 2026-08-27. Status: **PROGRAM PLAN.** No trials registered by this
document; each family below requires its own numbered hypothesis before
anything runs.

Commissioned by the owner: *"test 60 more from a new family, then 60 more
from another."* The instinct is correct and this document says why, says
what the real constraint is, and lays out the families in the order their
expected value justifies.

---

## 0. The instinct is right, and it has already been proven right once

`OBSERVATION` — `docs/research/graveyard-audit.md` §5 found the ledger was
almost entirely **one family**: directional timing on daily bars, spot
only, top-40 coins. `docs/hypotheses/62-delta-neutral-carry.md` was the
first hypothesis tested **outside** that family. It **passed all five
bars on its first run**, with the highest Sharpe in the ledger (2.29) and
a correlation to the deployed book of **+0.0041**.

`INTERPRETATION` — one data point, but it is the data point that matters:
the ~3% survival rate was a property of the family, not of the market.
Expanding families is the correct move.

---

## 1. What the constraint actually is (it is not the trial count)

The multiple-testing cost of a large program is **smaller than previously
implied in this project's own conversations**, and the correction is
recorded here because it points in the owner's favour.

`OBSERVATION` — computed with `expected_max_sharpe` at the deployed book's
measured trial-Sharpe variance (0.000183):

| Trials run | Best-of-N Sharpe expected from **pure noise** (annualized) |
|---|---|
| 126 (today) | **0.68** |
| 1,000 | 0.84 |
| 5,000 | 0.95 |
| 10,000 | **1.00** |

`INTERPRETATION` — running **10,000** trials raises the noise floor from
Sharpe 0.68 to 1.00. That is a real cost and it is not catastrophic. Carry
(2.29) and rotation-stop (1.47) both remain above it. **A 10,000-trial
program is statistically affordable.**

The two costs that *are* real:

1. **The deployed book loses its 95% confidence.** rotation-stop's
   `DSR_global` falls from 0.9909 today to **0.9188 at N = 10,000** —
   below the 0.95 bar. It would need re-validation on fresh data, not
   re-argument.
2. **Data, not trials, is the binding constraint.** The lake holds ~2,880
   daily bars across 40 coins. Ten thousand hypotheses against ~2,880
   observations is not a search, it is a guarantee of finding shapes in
   noise. **Every family below is ranked partly by how much NEW data it
   brings**, because new data is what buys statistical power. More
   hypotheses on the same data buys none.

**Program rule:** a family that adds no new data may register at most 20
trials. A family that brings a genuinely new dataset may register more.

---

## 2. The return arithmetic, stated once

The owner's target is 85–110%/month. What that requires, computed:

| Target | Annualized | At Sharpe 2.29 (today's best) | At Sharpe 4.58 | At Sharpe 6.48 |
|---|---|---|---|---|
| 20%/mo | 792%/yr | 96% vol | 48% vol | 34% vol |
| 85%/mo | 160,617%/yr | **322% vol** | 161% vol | **114% vol** |

Crypto alt annualized volatility is roughly 60–150%.

`INTERPRETATION` — 85%/month is **not arithmetically impossible**, and the
reason is exactly the one the owner gave: crypto's volatility is high
enough to support returns equities cannot. What it requires is **Sharpe,
not leverage**. At today's best Sharpe it needs 322% volatility, which
means leverage that `owncap-sizing.md` already measured as ruin. At Sharpe
6.5 it needs 114% volatility — inside crypto's natural range, no ruinous
leverage required.

**Uncorrelated edges add in quadrature:** `Sharpe_total = √(Σ Sharpe_i²)`.

| Independent edges at Sharpe 2.29 each | Combined Sharpe | Vol needed for 20%/mo | for 85%/mo |
|---|---|---|---|
| 1 | 2.29 | 96% | 322% |
| 2 | 3.24 | 68% | 228% |
| 4 | 4.58 | 48% | 161% |
| **8** | **6.48** | **34%** | **114%** |

**This is the whole strategy.** The goal is not "test 10,000 things and
deploy the best one" — the best of 10,000 is the most likely thing to be
luck. The goal is **eight genuinely uncorrelated edges run together.**
H62 proved edge #1 outside the momentum family and proved independence is
achievable (+0.0041). Seven more of those beats any single strategy that
will ever be found.

**Every family below is therefore judged on two axes: does it pay, and is
it uncorrelated with what we already run.** The correlation bar (<0.30) is
not a formality; it is the objective.

---

## 3. The families, in priority order

Each needs its own pre-registered hypothesis document. Estimated trial
counts are budgets to declare, not promises to spend.

### Tier 1 — new data, structurally independent, retail-reachable

**F1. Funding-conditional and cross-sectional carry** *(~20 trials)*
H63 is registered. Beyond it: cross-sectional funding (long the cheapest
funding, short the richest), carry across the full perp universe rather
than 8 majors, term structure where quarterly futures exist. **Data
needed:** funding + perp for 40+ symbols (have 8).

**F2. Cross-exchange basis and price dislocation** *(~30 trials)*
The same asset trades at different prices on Binance, Bybit, OKX, Kraken.
Persistent basis is a real, measurable premium. **Structurally
uncorrelated with everything in the ledger.** **Data needed:** synchronized
order-book or trade data from 2+ venues — the single most valuable dataset
this project does not have.

**F3. Options / variance risk premium** — **CLOSED 2026-08-27, 5 of ~25
trials spent.** `docs/hypotheses/67-variance-risk-premium.md` killed it at
the kill-test stage, so the option-chain collector and Greeks layer named
below were never built. The premium is real and large gross (BTC IV−RV
+8.72 vol points, IV>RV on 72.3% of days) and unreachable after a derived
3.0 vol-point cost; it also decays monotonically to −17.59%/yr by 2026.
Two findings survive: the correlation bar cannot see tail dependence
(§8.4 of that document), and an `IV − RV` screen overstates the
harvestable premium by a third because a variance position pays
`(K²−RV²)/(2K)`. **Structural limit found:** only BTC and ETH publish
DVOL, so this family could never have been broad. Reopening needs a new
pre-registration and a stated reason.

### Tier 2 — new structure, existing or cheap data

**F4. Statistical arbitrage / pairs and cointegration** *(~40 trials)*
Market-neutral by construction, so it clears the correlation bar
structurally. Crypto is full of mechanically-linked pairs (L1s vs their
ecosystem tokens, staked vs unstaked, wrapped vs native).
**Data needed:** none new — the existing 40-coin daily lake supports the
first pass.

**F5. On-chain / flow** *(~30 trials)*
Exchange in/outflows, stablecoin supply changes, whale wallet movement.
Genuinely different information, not a price transform. The meme layer
already touched this. **Data needed:** on-chain APIs.

**F6. Cross-asset and macro conditioning** *(~20 trials)*
Crypto vs DXY, real yields, equity vol, gold. Tests whether crypto's
regime is conditionable on information outside crypto. **Data needed:**
free macro series.

### Tier 3 — high theoretical value, infrastructure-gated

**F7. Market making / liquidity provision** *(~30 trials)*
Where professional crypto money is actually made. Requires order-book
data, latency infrastructure, and rebate-tier fees. The ledger's own
intraday finding — four confirmations that the reversion premium is
2–4bp/event, real but below retail cost — **is evidence this family pays
someone**, just not at 10bp taker fees.

**F8. Liquidation cascades and forced-flow** *(~20 trials)*
Liquidation events are mechanically forced selling with a known trigger.
**Data needed:** liquidation feeds.

---

## 4. Sequencing

1. **H63** — registered, runs next.
2. **F4 stat-arb** — needs no new data, tests immediately, market-neutral
   by construction. Best effort-to-information ratio available today.
3. **F1 carry expansion** — extend funding/perp collection from 8 to 40+
   symbols. Mostly a data-collection task.
4. ~~**F3 options/VRP**~~ — **done and closed 2026-08-27 (H67), no build.**
   It was run ahead of F1's data-collection tail because its kill test was
   cheap (a free index, no chain needed) and it gated the largest build in
   Tier 1. That gate is now shut.
5. **F2 cross-exchange** — highest structural independence, needs the
   multi-venue dataset. **Now the top unstarted Tier-1 family.**

Tier 3 waits until Tier 1–2 is exhausted; it is gated on infrastructure,
not on ideas.

---

## 5. Standing rules for the program

These do not bend, and they are the reason a result from this program will
be worth acting on:

- **Pre-register every family and every cell before it runs.** A 10,000-
  trial program with honest bookkeeping is worth something; the same
  program without it is worth nothing at all, no matter what it finds.
- **Declare the cell count up front** (`mi-trial-accounting-design.md`:
  declaring a 20×10 grid and running 50 still costs 200).
- **Report every cell**, including the unflattering ones.
- **The correlation bar is the objective, not a checkbox.** A high-Sharpe
  edge correlated 0.8 with rotation-stop adds almost nothing to the
  combined book. A modest edge at correlation 0.0 adds a lot.
- **Re-validate the deployed book as N grows.** Track rotation-stop's
  `DSR_global` at every milestone. When it drops below 0.95, that is a
  finding to act on, not to route around.
