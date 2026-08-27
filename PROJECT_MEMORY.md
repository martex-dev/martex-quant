# PROJECT_MEMORY.md — everything learned (through 2026-07-12)

The knowledge file: ledger, results, meta-findings, lessons, open
assumptions. PROJECT_STATE.md = what runs now; this = why and what we know.

## Trial ledger: 170 registered (169 run, 1 data-blocked: H54). Every new
## spec raises the DSR bar. Do not test without a numbered doc FIRST.
##
## SOURCE OF TRUTH for the ledger is docs/research/ledger/trials.toml, not
## this file. H60-H67 are recorded there in full; the table below stops at
## H59 and is kept as written rather than back-filled. Recent verdicts:
## H62 carry ELIGIBLE (Sharpe 2.29, corr +0.004 -- first edge outside the
## momentum family), H63 conditional carry ELIGIBLE (Sharpe 6.00, replaces
## H62 as the carry spec), H64 cointegration KILLED, H65 wide-universe
## carry STANDALONE-VIABLE, H66 cross-sectional carry STANDALONE-VIABLE,
## H67 variance risk premium KILLED, H68 cross-venue dislocation SIGNAL,
## H69 the strategy built on H68 KILLED, H70 K=2 VINDICATED.

## Hypothesis ledger (docs/hypotheses/, docs/research/)

| # | Hypothesis | Verdict | Key numbers |
|---|---|---|---|
| 01 | TSMOM 1h | REJECTED | median DSR 0.39 (9y: 0.95 but 3/8 vs B&H, -90% MDDs) |
| 02 | TSMOM daily | positive, superseded | 9y per-symbol median DSR 0.911 |
| 03 | Vol-gated momentum | REJECTED | filter cuts returns more than DD |
| 04 | Mean reversion 1h | REJECTED decisively | 0/8, DSR 0.036 on 9y |
| 05 | Carry (funding) | premium CONFIRMED, infra deferred | 5.8-7.9%/yr gross, SOL negative; needs 2 legs -> own-capital, post-eval |
| 06 | Vol-target sizing | SURVIVED -> deployed (V1) | the cure for MDD; prop-fit maker |
| 07 | Donchian breakout | strong but superseded | per-symbol median DSR 0.947; loses to vol-target under 3% daily-loss rules |
| V2 | BTC dominance rotation | KILLED at info stage | 0/3 lookbacks; quadrants contradict own logic |
| 08 | Funding extremes contrarian | KILLED — backwards | high funding -> HIGHER fwd returns |
| 09 | Calendar (ToM/weekend/funding-hrs) | 1/3 marginal | ToM +0.39%/d CI grazes 0 (low-priority); others dead |
| 10 | Spot-perp basis contrarian | KILLED — significantly backwards | premium -> +14.8% vs +6.1% fwd30 |
| 11 | Cross-sectional rotation | **VALIDATED (wide)** | kill +0.8-1.0%/wk spread; sized 8-coin Sharpe 0.90; WIDE: Sharpe 1.10, prop 62.9%@0.5x, **DSR 0.990 > 0.95 bar — first absolute validation** |
| 12 | 50/50 combined book | NOT eligible | true sleeve corr 0.77 (0.35 was an alignment bug — corrected); blend averages, doesn't insure |
| 13 | Shock persistence | extreme UP continues (+3.54% fwd7 CI+) | later shown redundant with momentum (23a) |
| 14 | Vol-expansion breakout | KILLED | compression adds nothing (increment negative) |
| 15 | Weekly crash bounce | KILLED | CI straddles 0; vol-conditioning nothing |
| 16 | Momentum acceleration | 7d ranking info-SIGNAL; accel KILLED | follow-up: grid{7,30,90} DEGRADES rotation (0.83 vs 1.10) — champion unchanged |
| 17 | Fallen-angel recovery | KILLED | -1.9%, wide CI |
| 18 | Trend overextension | SIGNAL — OPPOSITE | stretched coins earn MORE (+10.5% fwd30) |
| 19 | BTC->alt lead-lag | down-day SIGNAL (+0.82% next day) | up-days nothing; -> H22 |
| 20 | Sessions | US hours carry the drift | not tradable vs costs; execution note |
| 21 | Volume-conviction | KILLED (near-miss) | +2.44%, CI [-0.23,+4.65] |
| 22 | Crash-bounce strategy | **ELIGIBLE -> paper #3** | +0.441%/held-day net (CI clear), +32%/yr, Sharpe 0.89, MDD -48%; overlay shape, zero params |
| 23 | Incremental features | BOTH KILLED | shocks redundant w/ momentum; funding-confirm misses |
| 24-32 | Ranking batch (risk-adj, 52wh, residual, low-vol, MAX, illiq, vol-shock, FIP, skip-week) | ALL 9 KILLED | no institutional factor ranking beats raw momentum; references themselves noise at daily-spread level |
| 33 | Multi-horizon blend | info SIGNAL; FU-B1 KILLED | monotone in score, +2.41% CI+; blend-V1 Sharpe 0.60>0.53 but prop 28%<50% bar |
| 34 | Basis momentum | KILLED | like 23b: positioning change adds nothing to price momentum |
| 35 | Pairs ratio stat-arb | KILLED | reversion refuted; near-miss on MOMENTUM side (6th continuation confirmation) |
| 36 | Short-leg viability | KILLED | bottom-2 does NOT keep falling; long/flat stands |
| 37 | Breadth dial | KILLED | terciles monotone but CI wide |
| 38 | Dispersion dial | KILLED | terciles monotone but CI wide |
| 39 | Pick-correlation | KILLED | diversified picks buy no return |
| 40 | Trailing stop info test | **SIGNAL (stops help)** | post-stop-fire fwd30 -8.77% vs uptrend baseline, CI clear -> H42 |
| 41 | Rotation+crash-bounce book | **NOT eligible (prop bar)** | corr 0.188 (first low-corr sleeve!), Sharpe 1.36, CAGR +66%, DSR 0.995 — but prop 45.3%<62.8%: bounce variance trips 3% daily rule. Archived as OWN-CAPITAL book |
| 42a | V1 + chandelier stop | **CANDIDATE** | Sharpe 0.84 vs 0.53, MDD -13.3% vs -25.1%, prop 31.1%>27.9% |
| 42b | Rotation + chandelier stop | **CANDIDATE — beats champion on all metrics** | Sharpe 1.47 vs 1.10, MDD -29% vs -58%, prop 73.0%>62.8% @0.5x, **DSR 0.992 > 0.95 bar** (104 trials); paper account #4 since 2026-07-12 |
| 43 | Combo batch on rot-stop base | screen: only bounce admits; **43a KILLED (eval bars)** | rot-stop x V1 corr 0.521, x rotation 0.821 (blends dead); rot-stop+bounce Sharpe 1.55, +79%/yr, DSR 1.000 but prop 47.5%<73%, MDD worse -> replaces H41 as own-capital archive |
| 44-50 | Retail intraday batch (maker regime, 15m Bybit) | ALL 7 claims KILLED; **H44 ORB + H45 first-hour INVERTED (significant)** | fade earns 0.16-0.20%/event = 4-5x maker toll; sessions/funding/levels/bursts/VWAP noise -> H51 |
| 51 | Intraday fade strategies (51a fade-ORB, 51b fade-1st-hour) | BOTH KILLED (taker floor) | 51a Sharpe 0.14; 51b 0.44 < 0.7 bar; maker-PROXY 51b 0.90 corr +0.01 (most independent stream ever measured) — true maker-fill model = possible H52, queued behind sprint |
| 59 | Live paper drawdown vs each strategy's OWN backtest distribution (ledger +0, diagnostic) | **DEPLOYED SPEC INCONSISTENT — divergence hunt open** | rotation-stop live −13.06%/29d sits at p=0.0081 (block bootstrap) / 0.0060 (overlapping) of its own backtest window distribution; rotation −15.90% at p=0.0060/0.0032; **control vol-target CONSISTENT p=0.49**, so the method is not self-flagging. Worst backtest 29d window −17.53%, so the live month is RARE, not unprecedented. Cells 1+2 correlate 0.821 — ONE event seen twice, not two confirmations. Market-context check was **impossible**: lake ends 2026-07-09, paper starts 07-10, zero overlap |
| 59b | H59 market context (descriptive, ledger +0) | **"the whole market fell" is FALSE** | BTC **+2.62%** over the live window while the equal-weight 40-coin universe fell **−9.77%** (24/40 down). Worst 5: DEXE −95.0%, SYN −58.5%, PYR −55.2%, ATM −46.3%, VANRY −44.7%. Softens but does not overturn the INCONSISTENT verdict: a 1-2 name concentrated book losing 13.06% against a −9.77% alt average is unremarkable, but the verdict is against the strategy's OWN backtest, a separate question. **OPEN LEAD (not a finding):** SYN and ATM were top-ranked by 90d momentum and are in the worst 5 — needs its own registration |
| 58 | Learnable weighted indicator ensemble (logit over 6 indicators, purged walk-forward) | **KILLED at info stage — equal weights beat learned weights** | B equal-weight acc 0.5213, fwd7 spread **+2.79% CI [+0.83%,+4.90%] SIGNAL**; C learned 0.5062, −0.56% noise; L1/L2/rolling-retrain all noise. Stability bar PASSED 6/6 (four at 85-92%) and ablation degraded — weights stable and reproducible, just worse. Poison test refused to report on its first run (leak detector measured against a binary target, could not have caught a perfect leak) |
| 52-57 | Intraday frontier (true maker fill, order-flow, OI, lead-lag, ratio, POC) | 5 run ALL CLOSED; H54 data-blocked | H52 killed 0.69 vs 0.70 bar (near-miss stays closed); H53 contrarian SIGNAL 1.9bp + H57 bounce SIGNAL 2.8bp both SUB-TOLL; H55/H56 noise. Intraday family CLOSED absent new data dimension |

## Prop-firm simulation results (real CFD rules, 20k paths, EOD approx)

- V1 vol-target: 1-step static best **1.5x -> 50.0% pass, median 80d**,
  breakeven funded value $104. 2-step: 47.8%@1.5x.
- Rotation-wide: **0.5x -> 62.9% pass, median 100d**. Donchian: 46.5%@0.75x
  (GENERIC), loses under the firm's 3% daily rule.
- Crash-bounce: overlay only (78% flat -> eval timeouts standalone).
- UNIVERSAL: sizing beyond ~1.5x ALWAYS lowers pass rates; the
  constraint geometry (daily-loss + max-loss), not the return stream,
  dictates strategy choice and size. All pass rates are UPPER bounds
  (EOD trailing/daily checks; intraday is stricter). Intraday guard
  makes them slightly conservative in our favor.

## Meta-findings (the big ones)

1. **Crypto is a continuation market — 5+ independent confirmations.**
   Funding extremes, perp premium, dominance quadrants, single-day
   shocks, overextension: every crowding/strength signal predicted
   CONTINUATION; every contrarian folk-theory died. Only exception:
   next-day alt bounce after BTC crash days (H22) — a 1-day reactive
   effect, not positioning-based.
2. **Sizing beats switching.** Vol-target sizing (dial) survived where
   every regime filter (switch) failed (03, 06, rotation-sized).
3. **Cross-sectional edges feed on breadth.** Rotation got STRONGER on
   40 coins than 8 (Sharpe 0.90 -> 1.10) — opposite of the survivorship
   fear.
4. **Info-signal ≠ strategy improvement.** 7d ranking was real at info
   level but degraded the walk-forward (selector chases noise); shock
   signal was real but fully absorbed by deployed momentum. Incremental
   bars (beat the deployed system, not zero) killed both. **H58 sharpens
   it: fitting is not free.** An equal-weighted 6-indicator composite
   was a clear signal (+2.79%, CI clear); learning the weights on the
   same features, same windows, destroyed it (−0.56%, noise). The
   learned weights were STABLE (6/6 signs held), so this is not
   ordinary overfitting — logistic regression maximises likelihood on
   binary DIRECTION while the payoff is the return SPREAD, and
   optimising the wrong objective is worse than optimising nothing.
   Standing consequence: **an equal-weight baseline is mandatory in
   every future model-based hypothesis.** It is not a formality; it has
   now won.
5. **Diversification claims need timestamp-joined correlation on the
   common window** — tail-count alignment produced a false 0.35 (true:
   0.77) and nearly justified a bad combined book.
6. **Frequency kills.** Everything at 1h or faster dies after costs
   (01, 04, sessions). The edge lives at daily+.
7. **Horizon flips the sign: crypto CONTINUES at daily+ and REVERTS
   intraday — and the intraday reversion premium is the market
   maker's, not ours.** Four independent confirmations (H44 ORB, H45
   first-hour, H53 aggressor-flow fade, H57 POC bounce): every
   measurable intraday reversion premium is 2-4bp/event — real,
   significant, and BELOW retail execution at every accessible
   resolution (best strategy-grade attempt: H52 Sharpe 0.69 vs 0.70
   bar). Profitable day traders are rebate-tier market makers,
   untestable discretion, or survivorship. Intraday family CLOSED
   absent a new data dimension (deep OI, order-book depth).
8. **The objective function picks the config.** A deadline flipped BOTH
   standing rules (july-sprint.md): with retries and a hard date,
   4x sizing beats 1.5x and the eval-killed 43a book beats the
   champion. Corollary doctrine: EVALS = aggressive sprint config
   (downside capped at the fee), FUNDED = sustainable sizing (downside
   is the account). Also: rule GEOMETRY is worth money — HyroTrader's
   $39 swing upgrade (trailing->static drawdown) restores the exact
   geometry all our pass rates assume; without it they are overstated
   (cf. V1 50.0% static vs 39.1% EOD-trailing, intraday worse).
7. **The ranking is not improvable; the exits were.** Nine
   institutional factor rankings (24-32) all died against raw momentum,
   but the chandelier stop (40/42) — a better EXIT — beat the champion
   decisively. Refinement budget should go to exits/risk, not entries.
   Nuance to finding 2: a switch backed by a significant info-level
   signal can win; switches as free-floating filters still always died.
8. **Constraint geometry picks strategies, third confirmation (H41).**
   A book with corr 0.188, Sharpe 1.36 and double the CAGR still FAILED
   the eval bars because its variance lands on post-crash days that
   trip the 3% daily rule. Eval-fit and own-capital-fit are different
   objectives; H41's book is archived for the own-capital stage.

   *(Numbering note: 7 and 8 each appear twice above. That is a
   pre-existing defect in this list. Renumbering would silently rewrite
   references made elsewhere, so it is flagged rather than fixed, and new
   findings continue from 9.)*

9. **Linear correlation cannot see tail dependence, and the project's
   `|corr| < 0.30` bar is therefore blind to exactly the edges most
   likely to hurt (H67).** H67's short-variance book measured +0.0237
   against rotation-stop over 1,900 days — a comfortable pass. Conditioned
   on rotation-stop's own worst days it returns **−0.237%/day at the worst
   decile, −0.417% at the worst 5%, and −1.296% at the worst 1%**, against
   an unconditional +0.004%. Joint-loss FREQUENCY was 9.8% versus 10.4%
   under independence: the dependence is entirely in MAGNITUDE, which is
   the one thing Pearson correlation on daily returns does not measure.
   The mechanism is general, not specific to H67 — a short-convexity
   payoff is driven by SQUARED returns and is direction-blind, so it will
   pass a correlation gate against any directional book almost
   automatically. This matters because
   `family-expansion-program.md` §2 adds edges in quadrature
   (`Sharpe_total = √(Σ Sharpe_i²)`), and that arithmetic assumes
   independence the correlation bar did not establish.
   **Standing consequence, proposed and not yet adopted:** any hypothesis
   with an asymmetric or short-convexity payoff must clear a
   **tail-conditional bar** — mean return on the incumbent book's
   worst-decile days — alongside `|corr| < 0.30`. It needs its own
   decision before it becomes a rule.

10. **Two unrelated crypto premia died over the same two years (H62/H63/
    H65 carry, H67 VRP).** Funding carry earns ~0%/yr in 2025-2026 across
    three independent hypotheses. The variance risk premium decays
    monotonically over the identical window: 2021 +15.66%/yr, 2022 +9.30,
    2023 +6.79, 2024 −0.53, 2025 −8.60, 2026 −17.59. The two share no
    mechanism — one is a perpetual-swap financing rate, the other is
    options pricing — which makes market-wide maturation the natural
    reading. **Held as a hypothesis, not a finding:** two premia is two
    data points measured on the same calendar window, and that is exactly
    the confound that would manufacture this pattern from nothing. The
    operational consequence is real regardless of cause: **any edge sized
    on 2021-2023 history is sized on a regime that no longer exists**, and
    a hypothesis whose returns are concentrated before 2024 should say so
    in its verdict.

14. **Breadth feeds edges that HARVEST and starves edges that SELECT —
    now with evidence from both directions (H70).** H65 proposed this,
    H66 withdrew it, and H70 supplies the missing half. Varying the
    deployed rotation's slot count — the one number hypothesis 11 fixed
    by fiat ("Long-only. **K=2 FIXED**") and every descendant inherited
    untested — gives Sharpe **1.47 / 1.61 / 1.40 / 1.27** at K = 2/3/5/8
    and MDD **worse than K=2 at every higher K**. All three
    pre-registered predictions (Sharpe rising, CAGR falling, MDD
    improving, all monotone) were **wrong**.
    **The mechanism is mechanical:** carry harvests a premium paid by ~20
    near-independent funding streams, so averaging more cuts variance
    without cutting the mean. Rotation *selects*, and the 4th-8th ranked
    coins are worse assets rather than additional independent draws of
    the same edge. Diluting a selection edge lowers the mean faster than
    the variance. **Still a hypothesis, not a rule** — one measurement in
    each of two families is precisely the evidential state that produced
    the withdrawn refinement last time.
    **K=2 is vindicated on evidence for the first time.** K=3 beats it on
    return (Sharpe 1.61, CAGR +46.23%) and loses on drawdown; it was not
    the declared primary, it fails the registered MDD bar, and it is
    **not adopted** — acting on it needs a fresh registration.
    **And the live window says the opposite:** over 2026-07-10..08-26 the
    same cells give K=2 −6.06%, K=5 −3.85%, K=8 **−0.85%**, with MDD
    improving monotonically. So concentration is a **real contributor to
    the live drawdown** — about five of the six points — and 48 days is
    1.7% of the evidence behind the 2,880-day backtest. Both facts are
    true; neither licenses changing K. **The sharpened open question:
    is the live period unrepresentative, or has the K surface moved?
    That needs forward time, not another slice of the same history.**

13. **A significant spread is not a Sharpe — the info bar has no
    variance term (H69).** H68's S2 spread was **+3.17% per 7 days**, CI
    excluding zero, breadth 17/20, on 31,752 symbol-days. The strategy
    built from it with **zero new parameter search** — same symbols, same
    threshold, same window, engine-graded with next-open fills — earns
    **Sharpe 0.89** and is **beaten by equal-weight buy-and-hold (0.94)**.
    **Why:** `E[fwd|HIGH] − E[fwd|LOW]` with a CI excluding zero says the
    conditional means differ and says nothing about the volatility needed
    to collect the difference. The qualifying set averages **~1.4 names**,
    so a panel-wide mean has to be harvested through a concentrated book.
    The mean survived; the ratio did not.
    **Proposed, not adopted:** report an info SIGNAL alongside the
    **volatility of its bucket**. Two identical spreads are not equally
    valuable if one is carried by 15 names and the other by 1.4.
    **The benchmark bar earned its place.** H69's A1 and A2 passed
    (+9.176bp/day, CAGR +30.30%); on those alone it reads as a +30%/yr
    success. Only the buy-and-hold comparison separated that from the
    truth, and it was pre-registered specifically because the window's
    unconditional 7d return is +0.92%. **Any long-only crypto book tested
    on 2019-2026 needs a buy-and-hold bar or the verdict is meaningless.**
    Correlation with rotation-stop **+0.3929**, inside the 0.3-0.7 band
    predicted before the run — meta-finding 5 again.
    **Scope note for finding 9's proposed tail bar:** it added nothing
    here, because for a *directional* book the linear correlation bar
    already caught the dependence. H67's blindness was specific to
    **short-convexity** payoffs, so that amendment should be scoped to
    asymmetric payoffs rather than applied universally.

12. **The Coinbase premium is not the tether peg, and cross-venue
    dislocation is the first new INFO signal in a long time (H68).** The
    peg-adjusted premium between a USD venue (Coinbase) and USDT venues
    (Binance, OKX) predicts forward returns: **+3.17% at 7 days**, CI
    [+0.51%, +6.08%], breadth 17/20 symbols, on 31,752 symbol-days. The
    peg *alone* is NOISE at every horizon, which answers the obvious
    objection — the signal is in the asset dislocation, not the
    stablecoin. It is not momentum (correlations 0.02-0.09; survives
    removing the trailing-return extremes) and not concentration
    (dropping the two biggest contributors leaves +2.85%).
    **Sixth confirmation of meta-finding 1**, and the first from data
    outside the Binance price/derivative complex: every signalling cell
    is positive, i.e. continuation.
    **The crucial framing:** the premium is only **11bp at its 90th
    percentile** while the forward spread is **3.17%**. Nothing is being
    arbitraged — the dislocation is an *indicator* whose information is
    ~30x its own width. Cross-venue arbitrage remains untested and out of
    reach. **Weak point to confront, not average away: 2025 is the
    weakest year** (S1 −1.32%), though there is no monotone decay like
    carry or VRP. Info grade only; a strategy hypothesis is owed and
    faces the incremental bar.

11. **A screen in the wrong units overstates the edge — the convexity tax
    (H67).** BTC implied vol exceeded subsequent realized vol by 8.72 vol
    points on average, on 72.3% of days over five years. A variance
    position does not earn that. It earns `(K²−RV²)/(2K)`, and because
    realized VARIANCE is right-skewed the harvestable figure is **6.01**
    on BTC and **1.24** on ETH — an overstatement of a third and of 73%
    respectively. ETH's true premium sat below the 3.0 vol-point cost the
    whole time while the naive screen showed 4.55. General form: **screen
    in the units the position actually pays in, not the units the
    phenomenon is quoted in.**

## DSR re-check at 170 trials (2026-08-28) — the standing commitment, honoured

`family-expansion-program.md` §5 requires re-validating the deployed book
as N grows. Last honoured at 125; run again at 167/170.

| Book | Reproduced at its original N | DSR @167 | Bar 0.95 |
|---|---|---|---|
| rotation-stop (deployed) | 0.9921 vs published 0.992 | **0.9889** | CLEARS |
| rotation | 0.9905 vs published 0.990 | **0.9870** | CLEARS |

Forty-two more trials cost **0.003** each. Third confirmation that the
DSR bar is far less sensitive to ledger growth than was once feared. The
deployed book remains validated; what it is not is profitable live, which
is a different question and the one H59 opened.

## DSR re-check at 125 trials (2026-08-11, scripts/dsr_recheck.py)

Correction candidate 7 CLOSED. Reproduce-first guard passed on both books
before any recomputation was reported:

| Book | Published | Reproduced | DSR @ 125 | Bar 0.95 |
|---|---|---|---|---|
| rotation-stop (deployed) | 0.992 @104 | 0.9921 (drift 0.0001) | **0.9909** | CLEARS |
| rotation | 0.990 @65 | 0.9905 (drift 0.0005) | **0.9881** | CLEARS |

Growing the ledger 104 -> 125 cost rotation-stop only **−0.0011**. The
benchmark `expected_max_sharpe` scales as sqrt(2 ln N) x sd, and the trial
Sharpe variance is tiny (0.000183), so the hurdle barely moves. Practical
lesson: **the DSR bar is far less sensitive to ledger growth than feared** —
the earlier worry that new trials would retroactively disqualify the
deployed book was wrong, and worth recording as wrong.

The two reproduction defects that the earlier provisional attempt hit, both
now fixed: rotation-stop deflates the candidate over the CANDIDATE-CHAMPION
common window with variance over exactly two pp-Sharpes and
`fill_null(0.0)`; rotation deflates its WALK-FORWARD OOS stream with
variance over the GRID sliced to OOS start, and passes `n_obs=oos.height`
while the return series is one shorter — an off-by-one REPRODUCED on
purpose, because the published number is a function of it.

NOT re-checked: H41 (0.995@104) and H43a (1.000@107), archived own-capital
books, not deployed. Claiming a re-check that was not run would be worse
than the gap.

## Validated/deployed specs (exact)

- V1: VolTargetMomentum(lookback L, target 30%, window 30), per-symbol
  L re-selected each 90d by 1y-train walk-forward from {7,14,30,60,90,180};
  EW 8 slots, long/flat. Candidate-grade (DSR ~0.66 all-trials window).
- Rotation: VolTargetRotation(L, K=2, target 30%, window 30), L from
  {30,90} same protocol, abs-momentum gate, wide 40-coin universe.
  VALIDATED (DSR 0.990). Residual survivorship: fully-delisted coins
  absent (needs paid point-in-time data to erase).
- CrashBounce(threshold=-0.03): zero params, overlay shape.
- Shared decision core: live/decision.py — paper and MT5-live use the
  SAME code; strategies replayed over history each run (hysteresis-safe).

## Process rules that made this work (keep them)

- Numbered hypothesis doc with verdict bars committed BEFORE results.
- Kill test (cheap info study) before any strategy build; vectorized
  screening allowed pre-engine, event-driven engine is source of truth.
- Every trial (incl. failed variants and descriptive horizons) joins the
  ledger; DSR benchmarked vs ALL trials.
- Near-misses stay closed; reopening = new spec + stated reason.
- Paper accounts run ONLY validated/eligible specs, one spec per record
  (spec change = archive + fresh start).
- Report negative results with the same care as positive ones.

## Technical lessons (Windows/session specifics — also in auto-memory)

- Dashboard server loads code once: RESTART after dashboard changes.
- Windowless (pythonw) parents need CREATE_NO_WINDOW on subprocesses.
- Subprocesses need FULL env (stripped env breaks polars CPU detection).
- Patching .cmd files via Python string-replace fails silently on
  backslash paths — use the Write tool + grep -c to verify (bit twice).
- MetaQuotes-Demo has no crypto; firm server != MT5 default server.
- Binance funding API pagination needs explicit `since` (default returns
  only recent records — caused a wrong carry verdict, fixed same day).
- polars: from_epoch needs explicit cast to ms dtype; tzdata required on
  Windows; PYTHONIOENCODING=utf-8 for console polars printing.

## Open assumptions / honest caveats

- All EV numbers conditional on edges being real; V1 remains below the
  0.95 absolute bar (rotation is above it).
- Paper fills = signal-bar close (engine says next open) — adjacent in
  24/7 markets when run right after 00:00 UTC; drift is what Phase 5
  measures. MT5/live spreads at the firm are unverified vs the 1bp model.
- 5k funded account realistic value ~$50-80/mo initially; the prop path
  scales via bigger/multiple accounts, not summer riches. Expectations
  were set honestly and accepted.
- Survivorship: mitigated (wide universe incl. 90%+ crashers), not
  eliminated (fully-delisted coins unmeasurable without paid data).
