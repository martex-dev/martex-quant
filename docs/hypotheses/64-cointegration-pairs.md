# Hypothesis 64 — Cointegrated Pairs (family F4, stat-arb)

Status: **KILLED (2026-08-27) — Gate A failed on all four bars.** Trials:
**+12 → 141.** Verdict in §8. All 12 cells dead (best Sharpe 0.21). Gate B
PASSED — the book was genuinely market-neutral (corr −0.067 / −0.063), so
this is a validated machine finding no edge, not a broken one.

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

---

## 8. VERDICT (2026-08-27, scripts/h64_pairs_study.py, +12 → 141)

**KILLED. Gate A failed on all four bars.** Panel: 3,250 days
(2017-08-17 → 2026-07-10), 40 symbols, 365d formation → 180d trading,
hedge ratio frozen at formation.

### The declared 12-cell grid — all cells, as promised

| z_in | z_out | hold | Sharpe | CAGR | MDD | DSR |
|---|---|---|---|---|---|---|
| 1.5 | 0.0 | 30 | 0.00 | −1.02% | −29.10% | 0.1492 |
| 1.5 | 0.0 | 60 | **0.21** | **+1.92%** | −32.71% | 0.3371 |
| 1.5 | 0.5 | 30 | −0.06 | −1.89% | −36.98% | 0.1119 |
| 1.5 | 0.5 | 60 | 0.12 | +0.72% | −37.50% | 0.2542 |
| 2.0 | 0.0 | 30 | 0.02 | −0.66% | −35.33% | 0.1799 |
| 2.0 | 0.0 | 60 | −0.11 | −2.37% | −33.83% | 0.0958 |
| **2.0** | **0.5** | **30 (primary)** | **−0.15** | **−2.82%** | **−35.92%** | **0.0783** |
| 2.0 | 0.5 | 60 | −0.11 | −2.33% | −36.85% | 0.0970 |
| 2.5 | 0.0 | 30 | −0.16 | −2.74% | −32.29% | 0.0805 |
| 2.5 | 0.0 | 60 | −0.16 | −2.76% | −29.64% | 0.0801 |
| 2.5 | 0.5 | 30 | −0.32 | −4.71% | −38.33% | 0.0252 |
| 2.5 | 0.5 | 60 | −0.20 | −3.36% | −34.30% | 0.0587 |

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | mean > 0, CI excludes zero | −0.509 bp/day, CI low −3.429 bp | **FAIL** |
| A2 | CAGR ≥ 2%/yr | −2.82% | **FAIL** |
| A3 | Sharpe ≥ 1.0 | −0.15 | **FAIL** |
| A4 | DSR ≥ 0.95 @141 | 0.0783 | **FAIL** |
| B5 | \|corr\| rotation-stop < 0.30 | **−0.0674** (n=2,880) | PASS |
| B6 | \|corr\| H63 carry < 0.30 | **−0.0627** (n=2,124) | PASS |

### 8.1 The kill is not marginal, and the grid says so

`OBSERVATION` — **no cell reaches Sharpe 0.21.** The best cell
(1.5/0.0/60) earns +1.92%/yr against a 2% bar and a −32.71% drawdown. The
worst loses 4.71%/yr. Nine of twelve cells are negative.

`INTERPRETATION` — a grid this uniformly dead is a stronger result than a
single failing cell. There is no corner of the declared space where this
works, so the kill does not depend on the primary cell having been
nominated correctly.

### 8.2 The machinery worked; the edge was not there

Three things separate this from a botched implementation, and they matter
because they mean the negative result is trustworthy:

`OBSERVATION` — **cointegration was found, consistently.** An average of
**12.8 pairs** passed the Engle-Granger test at any moment. The strategy
was not starved of candidates; it traded 3.3 pairs on average at the
primary cell.

`OBSERVATION` — **the test is correctly calibrated.** Against 300
simulated independent random-walk pairs it admitted **4.0%** at
`alpha = 0.05`. A test that over-rejects would have manufactured pairs out
of noise; this one does not (`tests/test_cointegration.py`).

`OBSERVATION` — **the book was genuinely market-neutral.** Correlation
−0.067 with rotation-stop and −0.063 with carry: **Gate B passed
comfortably.** The construction did exactly what it was designed to do.

`INTERPRETATION` — this is the cleanest possible shape for a negative
result: the machinery is validated, the independence is real, and the edge
simply is not there. It is **independent and unprofitable**, which is
worth nothing on its own but does confirm the F4 family can be tested
properly.

### 8.3 The drawdowns are the mechanism

`OBSERVATION` — every cell carries a **−29% to −38% maximum drawdown** on
a book with no net directional exposure.

`INTERPRETATION` — that is the link-break failure named in §3 before the
run, and it is the whole story. Cointegration measured on 365 days does
not survive the next 180: pairs that reverted historically diverge
permanently, the position bleeds in the direction of the break, and the
z ≥ 4.0 stop crystallises the loss. Mean reversion in the spread was real
in the formation window and absent in the trading window.

### 8.4 What this confirms

`OBSERVATION` — the pre-registration (§2) recorded the prior: H04
mean-reversion was **REJECTED decisively** at the single-asset level, and
meta-finding 6 states *"frequency kills."*

`INTERPRETATION` — **this is the second independent confirmation that
crypto does not mean-revert at retail-reachable cost.** H04 killed it on
absolute prices; H64 kills it on relative prices with an economic link and
a walk-forward hedge ratio, which was the strongest remaining version of
the idea. Meta-finding 1 — *crypto is a continuation market* — now has a
sixth confirmation, and it is the one that cost the most to obtain.

**Proposed for PROJECT_MEMORY:** *reversion has now failed on absolute
price (H04), on intraday microstructure (H44/H45/H53/H57, real but
sub-cost), and on cointegrated relative value (H64). The reversion family
is CLOSED at retail cost structures.*

### 8.5 Specification gap that had to be filled

`OBSERVATION` — the pre-registration caps concurrent pairs at 10 but does
not say which 10 to prefer when more qualify. The implementation ranks by
**strongest formation-window cointegration evidence** (most negative ADF
statistic). It is a formation-time quantity, so it adds no look-ahead, and
**no alternative ranking was tested against results.**

`INTERPRETATION` — recorded because it is a degree of freedom the
pre-registration did not close. Given that all 12 cells fail and the best
is +1.92%, it is implausible that a different ranking rescues this, but
the gap is the reader's to judge, not this document's to wave away.

### 8.6 Limitations that did NOT save it

The §7 caveats all bias **toward** the strategy, which strengthens the
kill:

- Short borrow was modelled as a flat cost and never sourced; real borrow
  would be worse.
- Perp funding on a short leg was not modelled at all.
- The universe is survivorship-biased *against* observing link breaks —
  dead coins are absent, and link breaks are exactly what killed this.

**A strategy that fails under optimistic assumptions does not need
pessimistic ones re-run.**
