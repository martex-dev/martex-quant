# Hypothesis 61 — Does winning persist, and is anything left after latency?

Status: **REGISTERED 2026-08-12, NOT YET RUN.** No wallet ranking has been
computed, no period-2 outcome has been looked at, no decay curve has been
measured. Bitquery access was verified with a two-row connectivity query
against `DEXTradeByTokens` (USDC trades, no wallet data) and nothing else.
Git history is the proof of ordering, not this line.

---

## Why this hypothesis and not another

The meme program (`docs/research/meme-alpha-program.md`) found that three of the
four mechanisms behind public meme-coin winners are structurally closed to us:
latency, reflexivity from a following, and private launch information. The
fourth — portfolio structure — is open, and H60 tests it directly on launch
features.

But there is a *fifth* possibility the program flagged and could not test
without wallet data: **riding mechanism (b) from behind.** The winners' trades
are public. If their edge persists, and if enough of the move survives the delay
between their fill and ours, then their reflexivity becomes our signal without
us needing an audience of our own.

That is the single highest-value untested claim available, and it decomposes
into two questions that must *both* be answered yes. Either one alone is
worthless:

- **Persistence without surviving decay** → we identify real skill and cannot
  act on it. We become exit liquidity for the people we are copying.
- **Surviving decay without persistence** → we follow noise cheaply. The
  leaderboard was survivorship and we are betting on coin flips that already
  landed.

---

## H61a — Persistence

> **Does a wallet's realized performance in period 1 predict its realized
> performance in period 2?**

This is the mutual-fund-persistence question applied to meme-coin wallets, and
the prior from that literature is strongly negative: past performance mostly
does not persist once you correct for selection. Meme-coin leaderboards are a
more extreme version of the same setup — millions of wallets, a heavy-tailed
payoff, and a ranking computed *on the outcome*. Out of that population, some
wallets show 400x by variance alone and are then labelled "Smart Money."

### Selection rule — fixed here, before any ranking is computed

Wallets are ranked **by our own computation from raw Bitquery trade data**, not
by any third party's leaderboard. This matters: GMGN, Kolscan and Axiom all rank
on realized past PnL, so adopting their list would import their selection rule
into our test and make the result uninterpretable.

- **Universe:** wallets with ≥ 20 distinct token round-trips inside period 1.
  The threshold exists so that "top performer" cannot mean one lucky trade.
- **Period 1 and period 2:** two adjacent, non-overlapping, equal-length windows
  ending at the most recent full UTC day available. Length set by whatever
  Bitquery's free tier actually returns; recorded before ranking.
- **Metric:** realized USD PnL per wallet, computed as
  `sum(sell notional) - sum(buy notional)` over tokens the wallet both entered
  and exited within the window. Unclosed positions are **excluded**, not
  marked-to-market — marking them would import current price into a historical
  ranking.
- **Ranking is computed on period 1 only.** Period 2 outcomes are not queried
  until the period-1 deciles are written to disk.

### Verdict bars — committed before the run

**VALIDATED** requires all of:

1. Spearman rank correlation between period-1 and period-2 PnL is **> 0.15**
   with **p < 0.01**.
2. Top-decile-by-period-1 wallets beat the median wallet in period 2 by a
   margin that survives a bootstrap over wallets at **p < 0.01**.
3. The top decile contains **≥ 50 wallets**, so the result is not six accounts.
4. The effect survives excluding the single best period-2 wallet — i.e. it is
   not one outcome wearing a distribution's clothes.

**KILLED** if the rank correlation is ≤ 0.15, is not significant, or reverses.

**INCONCLUSIVE** if fewer than 200 wallets clear the round-trip threshold.

---

## H61b — Decay

> **After a tracked wallet buys, how much of the subsequent move is still
> available at +5s, +30s, +2min, +10min?**

Descriptive, not a strategy test. Measured on trades made by the period-1 top
decile, using the token's own trade sequence around each buy.

For each qualifying buy at time `t` and each lag `d`, the captured fraction is:

```
capture(d) = (P_peak_10m - P_entry(d)) / (P_peak_10m - P_wallet_fill)
```

where `P_entry(d)` is the first trade price at or after `t + d`. A capture of
1.0 means the delay cost nothing; 0.0 means the move was entirely gone.

**No verdict bar** — this produces a curve, and the curve is the input to any
future copy-trading spec. It is registered so the numbers cannot be quietly
reframed after the fact. It is counted as **1 descriptive trial**.

---

## Trial accounting

| Item | Trials |
|---|---|
| H61a persistence (primary) | 1 |
| H61a robustness: drop-best-wallet, alternative round-trip threshold | 2 |
| H61b decay curve (descriptive) | 1 |
| **Total** | **4** |

Ledger moves **135 → 139**. Every future edge claim is deflated against 139.

---

## Pre-committed expectation

Stated so hindsight cannot rewrite it: I expect **H61a KILLED and H61b to show
severe decay.**

Most likely outcome: rank correlation near zero or weakly positive but
economically meaningless, because the leaderboard population is dominated by
variance, and because the wallets that *do* persist are persisting via latency
(mechanism a) — which is precisely the thing we cannot copy. On decay, I expect
capture at +30s to be well under half, because the wallets worth copying are
fast and the tokens they buy are thin.

The outcome that would genuinely change the plan is the narrow one: **moderate
persistence combined with slow decay**, which would mean the wallets worth
following are followed by *humans* rather than raced by bots — reflexivity, not
latency. That is the only configuration in which copy-trading is a business for
a small account, and it is worth spending 4 trials to find out.

---

## What a KILLED verdict closes

It would close copy-trading as a strategy family for this project — not
"needs a better model", closed. If past wallet performance does not predict
future wallet performance, then no amount of feature engineering on top of a
wallet list recovers an edge that is not there, and the program falls back to
H60's cohort-structure question plus the rug-filter work.

That is a genuinely useful thing to know in an afternoon rather than after a
lost account.
