# July Sprint Plan (written 2026-07-12)

Goal (user): ~$400 banked by Jul 31 ($200 Claude Max + $200 account
scaling), via eval pass + funded profit. Deadline-constrained policy
analysis on validated streams: scripts/july_sprint_study.py (0 ledger
trials). All probabilities are UPPER bounds (EOD rule checks, instant
retry and instant funded activation assumed).

## Finding 1 — a deadline flips the sizing rule

Every no-deadline study said sizing beyond 1.5x lowers pass rates.
With a July-31 deadline and a retry budget (fees are cheap, ~$52),
TIMEOUT becomes the enemy, busts become retries, and **4x sizing
maximizes P(success) at every deadline tested**. The old rule stands
for the patient path; the sprint has its own physics.

## Finding 2 — the deadline also flips the engine

The 43a book (rotation-stop + crash-bounce), KILLED for the patient
eval because bounce variance trips the daily rule, is the BEST sprint
engine — the bounce bursts are exactly what a deadline wants. Third
demonstration that the constraint set, not the return stream, picks
the strategy.

## The menu (chain = eval pass -> +$500 gross funded profit, by Jul 31)

| Buy date | Days left | Best config | P(chain by Jul 31) | P(funded by Aug 1) | Expected fees |
|---|---|---|---|---|---|
| ~Jul 14 (now) | 17 | 43a @ 4x | **22.6%** | **70.3%** | ~$105 (2 fees) |
| ~Jul 19 (1wk shakedown) | 12 | 43a @ 4x | 18.1% | 63.8% | ~$102 |
| Jul 25 (the gate) | 6 | 43a @ 4x | 7.6% | 43.8% | ~$88 |

Read the second column honestly: the sprint goal itself is a ~1-in-5
shot at best. But P(funded account by August) is ~64-70% on the early
options — and a funded account in August is the income engine the
larger goal actually needs. The fees are not bets on July; they are
bets on August with a July lottery ticket attached.

## FIRM ANSWERS (2026-07-12) — The5ers is OUT for our system

1. Payout: first payout **14 days after funded activation** -> the
   July cash goal is mathematically impossible at The5ers.
2. Symbol list: crypto CFDs = **BTCUSD + ETHUSD only** -> none of the
   validated engines can run there (rotation needs ~40 alts, V1 needs
   8 majors, crash-bounce needs the alt basket).
3. Activation 24-72 BUSINESS hours + KYC + risk review.
4. Immediate purchase allowed (moot).

## Firm search (user authorized, 2026-07-12) — sprint sim on real rules

scripts/firm_choice_study.py, 17d deadline, 43a engine, retry budget 3:

| Firm | 5k fee | Rules | P($400 by Jul 31) | P(funded by Aug) | Fit |
|---|---|---|---|---|---|
| **HyroTrader** | $119 (refunded at 1st payout) | +10%, daily 4%, static 6%, **min 10 trading days**, payout 1d after 1st funded trade (min $100, 70% split), 700+ Bybit pairs | 16.4% @4x | **60.4%** | **FULL API (Bybit/OKX) — our stack connects natively; exact validated universe runs as-is** |
| Breakout (Kraken) | $45 | +10%, daily 4%, static 6% (1-step; verify — one source says trailing), NO min days, on-demand payout, 80% split, ~50 major pairs | 24.1% @4x | 71.5% | **NO API — proprietary terminal only.** Best math, unusable for automation. Viable ONLY as manual-execution hybrid (user keys in the bot's ~2-4 daily orders) |
| The5ers | $51.80 | 14d payout wait, 2 crypto symbols | ~0% | n/a | OUT |

Caveats: Breakout/Hyro numbers assume our full 40-coin stream; Breakout's
~50-major list would trim rotation breadth (re-validation = +1
pre-registered trial on the real symbol list). HyroTrader's eval-phase
consistency rule (no single trade >40% of total profit) is a risk for
2-position books — verify how a "trade" is counted (daily vol-scaling
rebalances may naturally split profits). Velotrade (full API on funded
crypto accounts since May 2026, per their blog) is an unverified
runner-up worth a support ping.

## RECOMMENDATION

**HyroTrader 1-step 5k ($119)** — the only firm found where the
validated system runs EXACTLY as validated (700+ Bybit perps) with a
real API. The sprint math is second-best (16% July goal, 60% funded by
August, fee refunded on success), but Breakout's better math is
unreachable for an automated system without manual execution. If the
user is willing to hand-enter orders daily for ~3 weeks, Breakout at
$45 is the aggressive-math option with execution-drift risk.

Pre-purchase verifications at HyroTrader (support ticket): consistency
rule counting, bot policy confirmation in writing, low-cap altcoin 5%
exposure rule vs our universe, mandatory stop-loss mechanics (our
chandelier stop maps naturally — confirm a resting SL order satisfies
it), Bulgaria/EU KYC, USDT payout to user's wallet.

## Build queue (GO, in order)

1. Bybit execution adapter (ccxt) + symbol map for the wide universe —
   replaces MT5 path for this firm. DRY-RUN default like live/trade.py.
2. 43a combined live engine in live/decision.py (rotation-stop weights
   + bounce overlay from idle cash) + runbook amendment pre-registered
   BEFORE purchase.
3. Guard scheduled at sprint sizing (daily trip 4%, static latch 6%).
4. Switch-down rule automated: after funded + July ends -> 0.5-1.5x.

## Execution requirements before purchase (engineering)

- Runbook amendment (pre-registered, committed BEFORE purchase):
  sprint engine + sizing + retry budget + the switch-down rule.
- 43a as a LIVE engine: combined rotation-stop + bounce logic in
  live/decision.py + MT5 runner (paper runs them separately today).
- Guard settings at 4x: daily trip and KILLED latch as in runbook;
  the guard is not optional at sprint sizing.
- **Switch-down rule (non-negotiable)**: the moment the funded account
  exists AND July ends (whichever later), sizing drops to the
  sustainable band (0.5-1.5x). 4x long-run = ruin (owncap-sizing.md).

## The trader-list reality check (recorded)

CZ / Armstrong / Winklevoss / Silbert built exchanges — their edge was
equity in infrastructure, not trades. Saylor is leveraged conviction
beta (our vol-targeted momentum beats leveraged B&H risk-adjusted on
our own data). Novogratz / Dixon are VC (capital-gated, illiquid).
The influencer scalpers (TJR, Cupsey, Orangie) trade intraday
order-flow styles that daily/1h OHLCV cannot validate and that our
cost model killed at 1h — with ONE honest exception worth a future
spec: perp-futures MAKER fees (~0.02%) are 5-10x cheaper than the
cost regime our intraday kills assumed. Reopening intraday momentum
under a maker-fee model on perps is a legitimate new hypothesis —
August track, own pre-registration, needs new data (1h/15m perp) and
a maker-fill model.

## August track (after the sprint resolves)

1. Funded-account income at sustainable sizing (~4-6%/mo realistic).
2. Scale: second/bigger eval from payouts (10k at $98 doubles income
   per unit of edge).
3. Raise the book's Sharpe (the real ceiling-lifter): carry sleeve
   (own capital), VRP/Deribit backlog, perp maker-fee intraday spec.
4. Own-capital 43a @ ~2x once capital >= ~$1k (executability floor).
