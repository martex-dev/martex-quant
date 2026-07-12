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

## HARD BLOCKERS — verify with the firm BEFORE any purchase (user action)

1. **Payout terms**: minimum trading days before first payout, payout
   cycle, profit split. If the first payout cannot physically land
   before Jul 31, the cash goal is impossible regardless of trading —
   the sprint then targets "funded + profit banked on-platform".
2. **CFD symbol list**: the rotation family needs ~40 alt symbols.
   Without coverage, fallback engine = V1 @ high scale (worse sprint
   numbers). This was already the gate's day-0 check; it moves up.
3. Activation delay between eval pass and funded account (1-3 days at
   many firms) — directly shrinks the deadline.
4. Whether 3 sequential attempts are allowed (retry policy).

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
