# Meme-coin program — mechanism, constraints, and what we build

Opened 2026-08-11. This is a plan document, not a verdict. No trial in the
ledger yet; H60 (registered separately) is the first.

The premise is not in dispute: a small number of Solana meme-coin traders have
made tens of millions of dollars, their wallets are public, and the money is
real. Nothing below argues with that. What follows is an attempt to answer the
only question that matters for us — *by what mechanism*, and which of those
mechanisms are reachable from a Windows laptop with a few hundred dollars.

Getting that decomposition right is worth more than any model. Copying an
outcome without copying its mechanism is how people lose money confidently.

---

## 1. How the public winners actually make money

Four distinct mechanisms hide behind the same screenshots. They have very
different transferability.

### (a) Latency — being first into a launch

On-chain analyses of the highest-frequency winning wallets show entries in the
first seconds, often the first block, of a token's life, across thousands of
tokens, from many wallets in parallel. That is not discretionary trading. It is
an automated sniper: buy tiny amounts of nearly everything at birth, exit most
within minutes, and let the tail pay for the rest.

*Requirements:* co-located or premium RPC, Jito bundle submission, sub-100ms
reaction, and enough capital that a $0.50 tip is a rounding error.
*Transferable to us:* *no*, not in its pure form. We would be the exit liquidity
for exactly this wallet class. Any strategy of ours that buys at t+30s into a
token this cohort bought at t+0.5s is on the wrong side of the same trade.

### (b) Reflexivity — being followed

A trader with a large public following buys, wallet trackers surface it within
seconds, followers buy, price rises, the trader sells into the followers. This
is a genuine, repeatable, mechanically-explainable edge, and it is the one that
most cleanly explains the very largest single-coin outcomes.

*Requirements:* an audience.
*Transferable to us:* **no.** This is the honest answer to "if they can do it
why can't I" — for this mechanism specifically, the edge *is* the audience, and
it is not a skill that can be substituted with compute. An anonymous wallet
running the identical trade sequence captures none of it.

### (c) Information — knowing about the launch beforehand

Private groups, team allocations, coordination with launchers. Some of this is
legal networking and some of it is not, and from the outside they look the same.

*Transferable to us:* no, and the paid-access version of it is overwhelmingly
sold by people whose business is selling access, not trading.

### (d) Portfolio structure — many tickets, ruthless exits

Underneath all three of the above sits an unglamorous fact: the winners take an
enormous number of small positions and cut almost all of them fast. The
distribution does the work. A wallet with 2,000 trades where 1,950 are small
losses and 3 are 50x is a wildly profitable wallet, and it looks nothing like
"predicted the next 100x."

*Transferable to us:* **yes — this one is pure engineering.** It is a sizing and
exit-discipline problem, and it is the only one of the four that a laptop and a
research framework can execute as well as a $10M desk. It is also the mechanism
the "AI predicts the winner" framing completely misses.

**Conclusion.** Three of the four mechanisms are structurally closed to us. One
is fully open, and it happens to be the one that actually generates the
distribution. So the program is built around (d), and the interesting question
becomes: **can we buy a portfolio of launch lottery tickets whose tail pays for
its losers, after costs?**

That is a real, testable, mathematical question with a number at the end of it.

---

## 2. The constraint that decides everything: cost per ticket

Mechanism (d) needs many tickets. Costs decide how many we can afford.

A Solana AMM round trip costs, per position:

| Component | Typical | Notes |
|---|---|---|
| Priority fee + tip | ~$0.40 × 2 legs | flat, independent of size |
| Venue swap fee | 0.25%–1% × 2 | pump.fun bonding curve is 1% |
| AMM price impact | ≈ 2 × notional / reserve, × 2 | explodes on thin pools |
| Failed attempts | ~5% | pays the fee, gets no position |
| Block-time drift | ~1% × 2 | modelled as extra slippage |

Implemented in `src/trading_bot/meme/economics.py`. The consequence:

- At **$500,000 a position**, the flat fee is 0.00016%. Costs are pure impact,
  and impact is manageable because you can pick deep pools.
- At **$50 a position**, the flat fee alone is ~1.7% round trip *before any
  other cost*, and the total lands in the 5–15% range.

So the two accounts are not running the same strategy at different scales. They
are running different strategies. **A $50 ticket must clear roughly a 10% move
just to break even, and $500 of capital buys ten tickets, not five hundred.**

That single fact rules out most of what gets proposed for meme coins:
high-frequency sniping (fees eat it), scalping small moves (breakeven is above
the move), and anything needing hundreds of concurrent positions. It leaves a
narrow, specific shape:

> **Few tickets. Each one needs a plausible path to a multiple, not to +20%.
> Losers cut at a level that keeps the flat fee from dominating. Winners held
> long enough for the tail to actually arrive.**

This is not a conservatism argument. It is the aggressive-growth answer, derived
from the cost structure rather than from taste — and it is the shape the public
winners' own trade distributions have.

---

## 3. What we need to know before sizing anything

Three numbers, in order. None of them require a model.

**N1 — the base rate.** Of unselected new Solana launches, what fraction reach
+100%, +400%, +1000% within 1h / 4h / 24h of a *realistically timed* entry, and
what does the loss distribution look like? Without this there is no baseline and
every later claim is unfalsifiable. If 1 in 40 launches does 5x, then "our model
found a 5x" means nothing; if it is 1 in 4,000, a 20-ticket portfolio is a
lottery and needs a filter before it is a strategy.

**N2 — does any filter move it?** Given features knowable at entry (pool depth,
buy/sell imbalance, unique buyer count, launch venue, time of day), does any of
them shift the tail probability enough to matter after costs? Not "is it
statistically significant" — *does the net expectancy of the filtered cohort
beat the unfiltered one by more than the friction*.

**N3 — the decay curve.** For the copy-trading variant: after a tracked wallet
buys, how much of the move remains at +5s, +30s, +2min, +10min? This is directly
measurable from minute bars and it is a hard go/no-go. If the move is over
before a laptop can react, mechanism (a) has eaten it and copy-trading is dead
on arrival — worth knowing in an afternoon rather than after a lost account.

N1 is being measured now. N2 follows from the same dataset. N3 needs wallet-level
data, which GeckoTerminal does not expose and which requires a Solana RPC or
indexer key (Helius/Bitquery free tiers are sufficient).

---

## 4. What is built (2026-08-11)

| Component | File | Status |
|---|---|---|
| Rate-limited HTTP client | `src/trading_bot/meme/http.py` | done |
| GeckoTerminal adapter | `src/trading_bot/meme/sources/geckoterminal.py` | done |
| Launch registry (first-sighting, append-only) | `src/trading_bot/meme/registry.py` | done, recording |
| Forward outcome measurement | `src/trading_bot/meme/outcomes.py` | done |
| AMM cost model | `src/trading_bot/meme/economics.py` | done |
| Recorder daemon | `scripts/meme_record.py` | running |
| Base-rate report | `scripts/meme_cohort_report.py` | done |

**On the dataset's integrity.** Every browsable endpoint these APIs offer —
trending, top-by-volume, boosted — lists survivors. A cohort built from one and
then found to contain lots of winners has discovered its own sampling frame.
So membership is fixed at first sighting from the new-pool stream, before any
outcome exists, and registry rows are never revised. A token that dies in nine
minutes sits in the file with exactly the same standing as one that runs 100x.
That property is the dataset's whole value, and it is the reason this cannot be
shortcut by downloading someone's "top meme coins" CSV.

Entries are priced at the open of the first minute bar *after* our observation,
never at the price in the registry row — that price was already stale when the
feed printed it, and pretending we could have had it is the single easiest way
to manufacture an edge that does not exist.

---

## 5. Ranked candidates, after the decomposition

1. **Cohort lottery with a cost-aware filter** (mechanism d). Buy a small number
   of launches passing an entry filter, hard-cut losers, hold winners for the
   tail. Directly testable with the data now accruing. This is the program.
2. **Rug / bundle screen.** Not alpha — a loss-tail reducer. Top-holder
   concentration, creator-wallet history, LP status, bundled first buys. Needs
   RPC access. Cheap, and it multiplies whatever (1) produces.
3. **Smart-wallet mirror** (riding mechanism b from behind). Gated entirely on
   N3. Measure the decay curve before writing a line of trading logic.
4. **Migration / graduation events.** Bonding-curve completion is a scheduled,
   observable, structural liquidity change. Small clean universe. Worth a look
   after (1).

Explicitly not doing: LSTM price prediction on meme coins, Twitter sentiment
scoring as a primary signal, or anything requiring us to win a latency race.
The first two are noise-fitting at this sample size and the third is a fight
against people with better hardware and a head start.

---

## 6. Execution boundary

The research layer produces signals, sizes and alerts. It does not place orders,
hold keys, or move funds, and I do not execute trades — that step is the user's,
deliberately and manually, and the code is structured so that it stays that way.
This is not a technical limitation to be engineered around later; it is where
the line sits.

---

## 7. Immediate next steps

1. Let the recorder accumulate ≥12 hours (~30,000 launches).
2. Run the base-rate report at 24h maturity → **N1**.
3. Register H60 with verdict bars *before* looking at filter results → **N2**.
4. Obtain a free Helius/Bitquery key to unlock holder- and wallet-level features,
   then measure **N3**.
