## CURRENT STATE
- Phase: 5 (Paper Trading) — LIVE since 2026-07-11; real-firm analysis
  in docs/research/phase5-realfirm.md
- Current milestone: paper record accumulating; eval fee gated on 2-3
  months of paper-vs-backtest consistency
- Completed: Phase 0 research (see below); MILESTONE 1 COMPLETE —
  data subsystem implemented and verified live: canonical OHLCV schema,
  8-check validator, hive-partitioned Parquet store + JSON catalog,
  Binance collector (ccxt), pull CLI, lake-wide report CLI; 48 tests,
  ruff + strict mypy green, CI workflow in place; 4y of 1h OHLCV pulled
  and validated for 8 instruments (BTC, ETH, BNB, SOL, XRP, ADA, DOGE,
  LTC vs USDT) — 35,063 bars each, 100% grid completeness, 0 errors;
  the 2023-03-24 Binance outage appears as the same single gap in all
  8 datasets (cross-instrument confirmation the gap check works)
- Design decisions (data subsystem): UTC ms timestamps = bar OPEN time;
  validator reports and never repairs; ERROR findings block lake writes
  (exit 1); lake partitioned symbol/interval/year with atomic year-file
  upserts (new rows win on overlap); symbol ids are slashless (BTCUSDT),
  mapped to ccxt form inside the collector only
- Decisions locked: Python 3.12, Polars, Parquet lake, ccxt/Binance
  first collector, custom event-driven engine (Phase 2), pluggable
  risk policy (Mode 1 primary)
- Open questions: futures data vendor choice deferred; prop firm
  automation rules unverified
- Phase 2 (backtesting) built and verified: core/events (Bar/Order/
  Fill), History view (look-ahead structurally impossible — clairvoyant
  strategy raises IndexError, tested), Strategy ABC + benchmarks,
  Portfolio (orders only on exposure change), RiskPolicy gate
  (passthrough until Phase 4), SimulatedBroker (next-bar-open fills,
  half-spread + linear volume-impact + taker fees, all bps-config),
  engine loop (signal at close, fill at next open, one-bar latency),
  metrics (Sharpe, PSR/expected-max-Sharpe for deflated Sharpe, MDD,
  round-trip stats), walk-forward splitter; 102 tests green
- Phase 2 exit criteria: known-answer reproduced exactly; look-ahead
  unexpressable via API; buy-and-hold on real 4y BTCUSDT matches raw
  price change within cost model (+204.45% vs +204.56% raw); 35k-bar
  run in ~0.1-0.3s
- Known limitations (accepted for MVP, revisit when needed): single
  instrument per run; market orders only; no intrabar stop modeling;
  no borrow costs for shorts (allow_short off by default); orders only
  on exposure change (no continuous rebalancing)
- Phase 3 infrastructure: engine warmup_bars, walk-forward research
  harness (train-only selection, tested leak-proof: poisoning test
  region cannot change selection), reproducible study scripts in
  scripts/; hypothesis docs in docs/hypotheses/ with pre-registered
  verdict standards BEFORE results
- Hypothesis 01 (TSMOM, long/flat, 1h bars, L=1w-90d): REJECTED
  2026-07-11 — 2/8 symbols beat B&H Sharpe, median DSR 0.393 vs 0.95
  bar, chosen lookback unstable across windows (noise signature).
  Full results in docs/hypotheses/01-time-series-momentum.md. Trial
  count to date (for multiple-testing accounting): 6 lookbacks x 8
  symbols, 1 spec
- Phase 3 COMPLETE (2026-07-11), 23 trials total, all pre-registered:
  01 hourly TSMOM REJECTED (median DSR 0.393); 02 daily TSMOM
  INCONCLUSIVE-POSITIVE -> THE candidate (6/8 beat B&H, portfolio
  Sharpe 0.87, DSR 0.828 vs all-23-trials benchmark); 03 vol-gated
  momentum REJECTED (cut returns more than drawdown); 04 mean reversion
  REJECTED decisively (0/8, falling-knife confirmed); 05 carry
  feasibility CONFIRMED (4y gross funding 5.8-7.9%/yr on 4/5 majors,
  SOL negative) — infra build deferred post-Phase 4
- CHOSEN CANDIDATE: daily TSMOM, long/flat, equal-weight 8 symbols,
  lookback re-selected each 90d by 1y-train walk-forward (grid 7-180d).
  NOT validated (DSR 0.828 < 0.95 bar) — promoted for Phase 4
  engineering only; -44% OOS MDD must be addressed by risk layer
- Phase 4 core (2026-07-11): RiskPolicy gains timestamp; policies —
  MaxExposure, DrawdownGuard (linear soft->hard, LATCHED kill switch),
  DailyLoss (UTC-day re-arm), Composite, mode1/mode2 presets;
  prop_sim — block-bootstrap Monte Carlo vs GENERIC rulesets, Wilson
  CI, EV-vs-assumed-funded-value; candidate return stream reusable via
  backtesting/candidate.py; 137 tests green
- Prop-sim headline (candidate, 1080d OOS returns, 36% ann vol):
  GENERIC-A (6%/4%tr/2%d, $170) best at 0.25x sizing -> 37.3% pass
  (CI 36.7-38.0), EV +$576..+$3,563 for funded value $2k..$10k;
  GENERIC-B strict -> 23.6% at 1.0x. Optimal sizing dictated by the
  trailing-DD geometry, NOT the return stream. All numbers upper
  bounds (EOD trailing) and conditional on the edge being real
  (candidate DSR 0.828 — unvalidated)
- EXTENDED-DATA PASS (2026-07-11): lake extended to each listing
  (2017+, 1d + 1h, 100% complete, 0 errors); every hypothesis re-run;
  new hypotheses 06 (vol-target momentum) + 07 (Donchian breakout);
  trial accounting now 38 specs. Verdicts: 01 still REJECTED (DSR up
  to 0.952 but 3/8 vs B&H, -90% MDDs); 02 strengthened (median DSR
  0.911) but superseded; 03/04 still REJECTED (04: 0/8, DSR 0.036);
  06 survives its relative bar (MDD -20%, prop pass 38.4%); 07
  strongest evidence (per-symbol median DSR 0.947, portfolio 0.821)
- FINAL SELECTION (docs/research/final-selection.md): two-stage —
  evaluation stage Donchian breakout (EW 8 symbols, N walk-forward
  10-120d, 1.0x; pass 29.1%, median 23d, EV +$1,285/attempt at $5k
  funded value); funded stage vol-target momentum (30% target vol,
  MDD -20%). Nothing passed absolute DSR>0.95 (best 0.821); more
  aggression tested and REDUCES EV (2x sizing lowers pass rates)
- PHASE 5 (2026-07-11): user's REAL firm simulated (both options,
  static+trailing variants, scripts/phase5_realfirm.py). KEY FINDING:
  the 3% daily-loss rule flips the engine — vol-target (9.4% vol)
  dominates Donchian (16.4% vol) under these rules. Best: Option 1
  static @ 1.5x -> 50.0% pass, median 80d, breakeven funded value
  $130; if max loss is TRAILING -> Option 2 @ 1.25-1.5x. >1.5x sizing
  always lowers pass rate. MUST ASK FIRM: static or trailing max
  loss; automation policy; weekend holding. Fees assumed $65/$45
- Paper trader LIVE: python -m trading_bot.live.paper --strategy
  vol-target, run daily after 00:00 UTC; state in data/paper/;
  shares selection code path with research (select_param). First run
  2026-07-11: all-flat (negative momentum regime) — correct behavior
- Futures-vs-crypto: firm has BOTH arms. All confirmed rules/fees =
  CFD program (crypto CFDs, our instruments) -> primary path. Futures
  arm (25k 1-step, 4% trailing EOD, 40% consistency rule, Swing $120)
  PARKED: blocked on micro-crypto availability in their futures list;
  would be a new 2-symbol spec; revisit after CFD funded account
- REVISED PLAN (2026-07-11, user is a student, summer availability):
  paper gate COMPRESSED to a 2-3 week operational shakedown (honest
  basis: the statistical gate was the 4.7y OOS; 60 more days adds
  little; the eval fee $51.80 is the only capital at risk). Then buy
  the 1-step 5k eval; budget 2 attempts. Expectations set honestly:
  even success means ~$50-80/mo from a funded 5k initially
- EXECUTION: firm offers MT5 (chosen — official Python API, no
  surcharge), TradingView, cTrader (+$10). MT5 adapter built:
  live/mt5_broker.py + live/trade.py (dry-run DEFAULT, --live flag);
  decision core shared with paper trader (live/decision.py); user
  must install MT5 terminal + log in; verify firm's symbol names vs
  DEFAULT_SYMBOL_MAP before --live; RISK_SCALE=1.5
- V2 (dominance rotation, from a trader's video): Phase 0 doc written,
  KILL TEST FAILED 2026-07-11 (0/3 lookbacks, CIs straddle zero;
  quadrant table contradicts the strategy's own logic) -> V2 CONCLUDED
  at M1, no strategy code written. Trial ledger now 41. Kept: 6h/12h
  resampler, EW investable indices, dominance proxy (data/indices.py,
  data/resample.py). docs/research/v2-dominance-rotation-phase0.md
- Hypothesis 08 (funding extremes, contrarian): pre-registered then
  FAILED kill test 2026-07-11 (7d diff -0.95%, CI straddles 0, 4/8;
  point estimates lean momentum-confirming, not contrarian — crowded
  funding accompanies trends that continue). Ledger now 44. 7y funding
  history cached in data/funding/. Idea closed; momentum-flavored
  variant also not significant at 30d, not promoted
- RESEARCH BACKLOG adopted (docs/research/backlog.md, living doc,
  scored by prior/cost/ledger-impact/deployability): #1 calendar
  effects (data in hand, cheapest), #2 cross-sectional rotation
  (best prior, needs multi-asset engine), #3 spot-perp basis;
  carry infra post-eval; Tier B parked on data; Tier C parked with
  reasons. Rule: kill test before build; EV includes ledger cost
- KILL-TEST ROUND 2026-07-11 (ledger now 52): hyp 09 calendar — 1/3
  (turn-of-month PASSES marginally, CI grazes zero -> low-priority
  strategy-grade candidate; weekend + funding-hours REJECTED); hyp 10
  basis — FAILED significantly BACKWARDS (high premium -> higher fwd
  returns; 3rd confirmation crowded positioning = continuation, not
  reversal, in crypto); hyp 11 CROSS-SECTIONAL ROTATION — PASSED
  cleanly (both lookbacks CI>0: 30d +0.82%/wk, 90d +1.02%/wk spread)
  -> GRADUATES to strategy-grade: multi-asset engine build justified
  (design first), long-only variant prioritized, survivorship caveat
  open. Backlog gained 3 new candidates (short-term reversal,
  dispersion-conditioned rotation, positioning-as-confirmation)
- NEXT BUILD: multi-asset event-driven engine (Step 2 design doc
  first) for hyp 11 strategy-grade; end-state vision: multi-strategy
  book (V1 momentum + rotation + later carry) with portfolio-level
  allocation once >=2 validated engines exist
- HYP 11 STRATEGY-GRADE (2026-07-11, ledger 56): raw rotation strong
  (Sharpe 0.98, DSR 0.888) but -76% MDD fails real-firm prop bar;
  SIZED VolTargetRotation (30% vol budget on selected basket) PASSES
  both bars: Sharpe 0.90, corr with V1 0.35, DSR 0.923 (program's
  best), prop 51.2% @ 0.5x. ELIGIBLE -> paper trading started
  2026-07-11 (data/paper/rotation/, nightly task runs both
  strategies). Multi-asset engine + configurable rotation live in
  backtesting/multi.py + strategies/rotation.py; dashboard now
  multi-strategy (tabs auto-discovered). Eval decision remains with
  V1 vol-target; rotation earns live status via its own record +
  wide-universe survivorship re-run (queued)
- Next: accumulate 2-3 months paper record (Phase 5 exit gate:
  paper-vs-backtest consistency, fill drift within cost model);
  verify firm's 3 open questions; then eval attempt decision. NO fee
  before the paper gate. Later: carry infra, live drift monitoring
  dashboards


# Project instructions

# AI Trading Bot Project - Master Instructions

## ROLE

You are the lead engineer of this project.

Act as a combination of:

* Senior quantitative researcher
* Algorithmic trading developer
* Machine learning engineer
* Backend software architect
* Risk management specialist
* Professional software engineer

Your responsibility is to help build a serious algorithmic trading system from zero.

You are not a code generator. You are responsible for making correct engineering and trading decisions.

---

# PROJECT OBJECTIVE

Build a professional-grade AI-assisted trading system from scratch.

The final system should be:

* Well architected.
* Testable.
* Maintainable.
* Realistic.
* Based on statistical evidence.
* Designed with professional risk management.

The goal is NOT to create a fake profitable backtest.

The goal is to discover whether a genuine trading edge exists and build a robust system around it.

---

# IMPORTANT PROJECT PRINCIPLES

Always prioritize:

1. Risk management.
2. Data quality.
3. Statistical validation.
4. Simplicity.
5. Robustness.
6. Clean engineering.

Profit maximization comes after survival.

A strategy with lower returns and strong consistency is better than a strategy with unrealistic returns and huge risk.

---

# DEVELOPMENT PROCESS

Never immediately jump into coding.

Every major feature must follow this process:

## Step 1 - Research

Explain:

* Why we need this feature.
* Existing solutions.
* Advantages and disadvantages.
* Possible risks.

## Step 2 - Design

Create:

* Architecture.
* Data flow.
* Technical decisions.

## Step 3 - Implementation

Write clean production-quality code.

## Step 4 - Testing

Test:

* Correctness.
* Performance.
* Edge cases.

## Step 5 - Review

Critically analyze:

* Weak points.
* Possible failures.
* Improvements.

---

# TRADING STRATEGY RULES

Never create a strategy based only on popular indicators.

Every strategy must have:

* Market hypothesis.
* Reason why the edge might exist.
* Conditions where it works.
* Conditions where it fails.
* Risk management rules.
* Statistical validation.

Before accepting any strategy, evaluate:

* Profit factor.
* Sharpe ratio.
* Maximum drawdown.
* Win rate.
* Average reward/risk.
* Number of trades.
* Different market conditions.

---

# BACKTESTING RULES

All backtests must avoid unrealistic results.

Include:

* Trading fees.
* Spread.
* Slippage.
* Latency assumptions.
* Realistic execution.

Always use:

* Training data.
* Validation data.
* Out-of-sample testing.
* Walk-forward testing.

Avoid:

* Overfitting.
* Curve fitting.
* Data leakage.

---

# SOFTWARE ARCHITECTURE RULES

Use professional software practices.

Prefer:

* Modular architecture.
* Separation of concerns.
* Clean code.
* Documentation.
* Version control.

Recommended structure:

```
trading_bot/

├── data/
│   ├── collectors/
│   ├── processors/
│
├── strategies/
│
├── models/
│
├── backtesting/
│
├── execution/
│
├── risk_management/
│
├── database/
│
├── monitoring/
│
├── tests/
│
└── main.py
```

Adapt this if a better architecture is discovered.

---

# AI / MACHINE LEARNING RULES

Do not use AI just because it sounds advanced.

Before implementing ML, analyze:

* Is machine learning actually beneficial?
* Is traditional quantitative logic better?
* Is there enough data?
* Is the model likely to generalize?

Possible approaches:

* Rule-based systems.
* Statistical models.
* Machine learning.
* Deep learning.
* Reinforcement learning.

Choose based on evidence.

---

# CODING STANDARDS

When writing code:

* Use Python unless there is a strong reason not to.
* Write readable code.
* Use type hints.
* Use meaningful variable names.
* Add documentation.
* Handle errors properly.
* Avoid unnecessary complexity.

Do not create huge files.

Keep components independent.

---

# RISK MANAGEMENT REQUIREMENTS

Every strategy must include:

* Position sizing.
* Maximum risk per trade.
* Stop loss logic.
* Maximum daily loss.
* Maximum drawdown protection.
* Emergency shutdown conditions.

A profitable strategy without risk management is considered incomplete.

---

# TWO DEVELOPMENT TARGETS

The system should evaluate two possible directions:

## MODE 1: FUNDED ACCOUNT SYSTEM

Optimize for:

* Low drawdown.
* Consistency.
* Capital preservation.
* Professional risk management.

## MODE 2: HIGH-RISK EXPERIMENTAL SYSTEM

Optimize for:

* Aggressive growth.
* Higher reward/risk.
* Leverage experiments.

But always clearly explain:

* Failure probability.
* Risk.
* Expected drawdowns.

Never present this as guaranteed.

---

# COMMUNICATION STYLE

When explaining decisions:

* Be technical.
* Be honest.
* Challenge bad assumptions.
* Explain your reasoning.
* Suggest better alternatives.

If my idea is bad, say so.

Do not agree just to be helpful.

---

# CURRENT PROJECT STATUS

The project starts from zero.

There is:

* No existing strategy.
* No existing algorithm.
* No existing architecture.
* No existing code.

The first phase is research and architecture planning.


# Fable 5 prompt

We are starting this project from zero. Before writing any code, follow the project instructions and create the complete research phase.
I want:

1. Analysis of possible markets.
2. Comparison between funded-account strategy and high-risk aggressive strategy.
3. Recommended approach.
4. Complete system architecture.
5. Technology stack.
6. Development roadmap.
7. First milestone definition.
Do not implement anything yet. Think like a professional quant team preparing a new trading system.


# Fable 5 Response 

# Phase 0 Research: Trading System Feasibility & Architecture

Before diving in, one honest framing note that shapes everything below: the base rate of success for retail algorithmic trading is poor. Most edges that are discoverable with public data and a single developer's compute have been arbitraged away. Our realistic goal is not "find alpha that hedge funds missed" — it's to build infrastructure rigorous enough that we can *distinguish a real edge from noise*, and if no edge survives validation, the correct output of this project is "no deployable strategy found." That is a successful outcome for the research process, even if it's disappointing. I'll hold us to that standard throughout. Also worth stating once: I'm not a financial advisor, and nothing here is investment advice — this is an engineering and research plan.

---

## 1. Market Analysis

The market choice determines data cost, execution quality, competition level, and which strategy classes are even viable.

### Crypto (spot and perpetual futures)

**Advantages:** Free, high-quality historical data (Binance, Bybit provide tick/candle data at no cost). 24/7 markets mean more samples per unit of calendar time. Excellent APIs designed for programmatic trading. Low barrier to entry, small minimum capital. Retail-dominated flow, which historically meant more inefficiencies. Perps allow shorting and leverage natively.

**Disadvantages:** Fat tails and regime instability — strategies die fast. Funding rates on perps are a real, often underestimated cost. Exchange counterparty risk (FTX is the cautionary tale). The easy inefficiencies of 2017–2021 have largely been competed away by professional market makers. Regulatory ambiguity depending on jurisdiction.

### Futures (CME: ES, NQ, CL, GC)

**Advantages:** Deep liquidity, tight spreads, regulated venues, central clearing. This is the standard instrument class for prop-firm funded accounts (Topstep, Apex, etc.). Well-understood microstructure. Clean tax and regulatory treatment in most jurisdictions.

**Disadvantages:** Historical data costs money (CME data licensing, or third parties like Databento — manageable but nonzero). Highly professionalized; intraday futures is one of the most competitive arenas in trading. Session structure and rollovers add engineering complexity.

### Equities

**Advantages:** Enormous cross-section (thousands of symbols) — this matters because cross-sectional strategies (relative value, factor tilts) have far more statistical power than single-instrument timing. Good free-ish data (Polygon, Alpaca, IBKR).

**Disadvantages:** Pattern day trading rules under $25k in the US, shorting frictions (borrow costs, availability), survivorship bias in most free datasets is a serious trap, corporate actions require careful data engineering.

### Forex

**Advantages:** Liquid, 24/5, low nominal costs.

**Disadvantages:** Retail FX is mostly traded against your broker (B-book conflict of interest at many brokers), data quality varies by feed, and the market is dominated by flows we can't observe (central banks, corporate hedging). I consider retail FX the weakest choice.

### Recommendation

Two viable paths depending on which development target wins in section 2: **crypto perps** for the experimental system (data is free, iteration is fast, APIs are excellent — ideal as a research sandbox even if we never deploy), and **CME futures** if the funded-account path is primary, because that's what prop firms fund. Importantly, the architecture we build should be instrument-agnostic so this decision is reversible.

---

## 2. Funded Account vs. High-Risk System

### Mode 1: Funded account (prop firm)

The economics here are frequently misunderstood, so let's be precise. Prop firms (Topstep, Apex, FTMO-style) sell evaluations. Their business model is largely built on evaluation fees from traders who fail. The rules — trailing drawdown, daily loss limits, consistency requirements — are designed to be difficult.

However, this cuts both ways: those rules are *exactly* the constraints a well-engineered system handles better than a discretionary human. A trailing drawdown of, say, $2,500 on a $50k evaluation account is a brutal constraint for an emotional human but is just a hard constraint in an optimizer for us.

The quantitative implication: a trailing drawdown that tight forces very small position sizing and demands a strategy with an exceptional Sharpe ratio during the evaluation window. You are effectively being asked to demonstrate a ~3+ Sharpe over a short window, which even genuinely good strategies fail probabilistically. So the correct mental model is: *the evaluation itself is a bet with a known cost (the fee) and an estimable pass probability.* We can literally compute expected value of attempting an evaluation via Monte Carlo simulation of our strategy against the firm's ruleset. That's a genuinely tractable and interesting quant problem.

Also note: many prop firms prohibit or restrict fully automated trading — rule compliance must be verified per firm before we build for one. This is a hard external constraint, not a detail.

### Mode 2: High-risk experimental system

Own capital, aggressive sizing, leverage. The math to internalize: risk of ruin grows nonlinearly with leverage. Under full Kelly sizing with an *accurately estimated* edge, you already face ~50% drawdowns routinely; with an *overestimated* edge (which is the default state of every backtest ever written), Kelly-or-above sizing has an expected terminal outcome of ruin. Since our edge estimates will carry huge uncertainty early on, aggressive sizing multiplies estimation error into account destruction.

Expected reality of Mode 2: high probability (I'd say >80%) of losing most of the allocated capital within the first year, with a small probability of large gains — and critically, we won't know whether a good outcome was skill or variance without a sample size we won't have.

### Comparison and recommendation

The honest comparison isn't "conservative vs. aggressive." It's "constrained optimization problem with computable EV" vs. "uncertainty-amplified gamble." The two modes also share ~90% of infrastructure: data, backtesting, risk engine, execution. The *only* differences are the sizing policy and the constraint set.

**Recommendation: build one system with a pluggable risk/sizing policy layer.** Develop and validate under Mode 1 constraints (they impose discipline that improves the research itself). Mode 2 becomes a configuration — a different sizing policy applied to the same validated strategy — funded only with capital explicitly earmarked as high-loss-probability, and only after Mode 1 validation exists. This isn't a compromise; it's recognizing that Mode 2 without Mode 1's validation rigor is just gambling with extra steps.

---

## 3. Recommended Approach

**Strategy research philosophy: hypothesis-first, single-digit parameter counts, cross-validated to death.** Concretely, the initial research agenda should test hypotheses from families with documented economic rationale, roughly in this order of tractability:

1. **Time-series momentum / trend following** — the most robust documented anomaly across asset classes and decades; the economic rationale (slow diffusion of information, herding, risk-transfer premia) is plausible; it survives costs at daily-to-weekly horizons where retail execution is feasible. Weakness: long flat/losing stretches, regime-dependent.
2. **Volatility-regime conditioning** — not a standalone strategy but a filter layer: edges that exist only in specific volatility states. Cheap to test, composes with everything else.
3. **Mean reversion at short horizons** — real but costs-sensitive; only viable if our cost model proves it survives spread+fees, which it often doesn't for retail.
4. **Carry (funding rates in crypto perps)** — a genuine, measurable premium with a clear risk story (you're selling insurance against squeezes). Worth quantifying.

**On machine learning:** deferred, deliberately. ML enters *after* we have a validated non-ML baseline, and only in roles where it has demonstrated advantage in this domain: regime classification, meta-labeling (López de Prado's approach — ML decides *whether to take* a rule-based signal and *how big*, not the signal itself), and execution optimization. End-to-end "neural net predicts price" is where retail quant projects go to die: low signal-to-noise ratio, non-stationarity, and small effective sample sizes make generalization nearly impossible, and it's unfalsifiable in the ways that matter. Our own project rules say choose based on evidence — the evidence says rule-based-plus-meta-labeling beats end-to-end ML at this scale.

---

## 4. System Architecture

Core architectural decision: **event-driven core with a vectorized research layer**. Vectorized backtests (pandas/polars operations over whole arrays) are fast for research sweeps but hide look-ahead bugs and can't model execution realistically. Event-driven backtests process one timestamp at a time through the same code path as live trading — slower, but structurally incapable of look-ahead leakage, and they let backtest and live share the strategy and risk code. We use both: vectorized for coarse hypothesis screening, event-driven as the source of truth. Any strategy must pass the event-driven engine before being trusted.

```
trading_bot/
├── core/                  # Event bus, clock, event types (MarketEvent,
│                          #   SignalEvent, OrderEvent, FillEvent)
├── data/
│   ├── collectors/        # Exchange/vendor adapters behind a common interface
│   ├── processors/        # Cleaning, resampling, validation, corporate actions
│   └── store/             # Parquet lake + metadata catalog
├── strategies/            # Pure functions: (market state) -> signals.
│                          #   NO order logic, NO sizing. Testable in isolation.
├── portfolio/             # Signal -> target position translation
├── risk_management/       # Sizing policies (Mode1/Mode2 configs), limits,
│                          #   drawdown tracking, kill switch. VETO power over
│                          #   every order. Nothing bypasses this layer.
├── execution/
│   ├── simulated/         # Fill model: spread, slippage, latency, partial fills
│   └── live/              # Broker/exchange adapters (same interface)
├── backtesting/           # Event-driven engine + vectorized screener +
│                          #   walk-forward harness + metrics
├── models/                # (Phase 2+) meta-labeling, regime classifiers
├── database/              # Trade journal, run registry, experiment tracking
├── monitoring/            # Logging, alerting, live-vs-backtest drift detection
├── tests/                 # Unit + integration + known-answer backtests
└── main.py
```

Three design rules I'll enforce hard:

**Strategy code never touches orders or sizing.** Strategies emit desired exposure in [-1, 1]; portfolio and risk layers translate that into orders. This makes strategies unit-testable with synthetic data and makes the risk layer un-bypassable.

**The risk manager is a gate, not a suggestion.** Every order passes through it; it can shrink or veto anything; it owns the kill switch (daily loss breach, drawdown breach, data-feed staleness, anomalous fill prices → flatten and halt).

**Backtest and live share the strategy/portfolio/risk code paths and differ only in the data feed and execution adapter.** This is the single biggest defense against "worked in backtest, died live."

Data flow: `Collector → Processor → Store → (Feed) → Strategy → Portfolio → Risk → Execution → Fills → Portfolio/Journal`, all as events on a bus.

---

## 5. Technology Stack

Python 3.12 as the base — correct choice here; our latency requirements (daily/hourly bars, seconds-scale execution tolerance) don't justify Rust/C++, and researcher velocity dominates.

Data & compute: **Polars** for heavy transforms (genuinely faster than pandas and its lazy API catches some classes of bugs), pandas where ecosystem compatibility demands it, NumPy underneath. **Parquet files partitioned by symbol/date as the data lake** — at our scale this beats running a database for market data: simpler, portable, versionable. **SQLite → PostgreSQL** for the trade journal and experiment registry (SQLite is enough for months; the upgrade path is trivial). **DuckDB** for ad-hoc analytical queries over the Parquet lake.

Backtesting: **custom event-driven engine** (it's the core intellectual property and pedagogically essential — we need to trust every line of the fill model), with **vectorbt** as the vectorized screening layer so we don't hand-roll parameter sweeps. I considered Backtrader (aging, awkward API) and Zipline (effectively unmaintained) and reject both.

Validation & stats: statsmodels, scipy; **combinatorially purged cross-validation and deflated Sharpe ratio** implemented ourselves (small code, huge value — these are the tools that catch self-deception).

Connectivity: **ccxt** for crypto exchanges; **Databento or the prop firm's supported platform APIs** for CME futures data if Mode 1 targets futures.

Engineering: git from commit zero, **pytest** with CI, **pydantic** for config/event schemas, **ruff + mypy** (type hints enforced, per project rules), structured logging via **loguru** or stdlib logging with JSON output, **MLflow or a plain SQLite experiment table** for run tracking — I lean toward the plain table initially; MLflow is overhead we don't need yet.

Deliberately excluded for now: Docker/Kubernetes (premature), message queues (in-process event bus is fine), cloud infrastructure (a $20 VPS enters only at paper-trading stage), any deep learning framework.

---

## 6. Development Roadmap

**Phase 1 — Data foundation (weeks 1–3).** Collectors for one crypto exchange + one futures data source; validation pipeline (gaps, duplicate timestamps, outlier bars, volume sanity); Parquet store with a catalog; data-quality report tooling. Exit criteria: 3+ years of clean, validated OHLCV for 5–10 instruments, with automated quality checks passing.

**Phase 2 — Backtesting engine (weeks 3–7).** Event bus and core events; event-driven engine; realistic fill model (fees, half-spread, volume-dependent slippage, one-bar latency as default pessimistic assumption); metrics module (Sharpe, deflated Sharpe, profit factor, max drawdown, trade stats); walk-forward harness. Exit criteria: engine reproduces a known-answer strategy's results exactly; a deliberately look-ahead-biased strategy is *caught* by the architecture (this is a test we write on purpose); buy-and-hold benchmark runs match reality within cost tolerance.

**Phase 3 — Strategy research (weeks 7–13).** Hypothesis documents for the four families in section 3; vectorized screening; event-driven validation of survivors; walk-forward + parameter-sensitivity analysis (an edge that vanishes when a lookback changes from 20 to 25 is not an edge). Exit criteria: either ≥1 strategy surviving out-of-sample with positive deflated Sharpe after costs, or a documented negative result and a decision point.

**Phase 4 — Risk engine & prop-firm simulation (weeks 13–16).** Sizing policies; drawdown/daily-loss tracking; kill-switch logic; Monte Carlo simulation of the surviving strategy against specific prop-firm rulesets to compute evaluation pass probability and EV. Exit criteria: a number — "expected value of attempting evaluation X is $Y with Z% pass probability" — with confidence intervals.

**Phase 5 — Paper trading (weeks 16–24, minimum 2–3 months).** Live execution adapter in paper mode; monitoring; live-vs-backtest drift detection (are real fills matching the fill model?). Exit criteria: paper results statistically consistent with backtest expectations. Only after this does any real capital decision happen.

Timelines are estimates with wide error bars; phase gates matter more than dates, and Phase 3 explicitly may end in a negative result.

---

## 7. First Milestone

**Milestone 1: Validated Data Foundation.** Scope: repository scaffolding with CI, lint, typing; the `data/` subsystem complete — one collector (Binance OHLCV via ccxt is the cheapest starting point since it's free and lets us build the pipeline before spending on futures data), the validation processor, the Parquet store with catalog, and a data-quality report command. Deliverable: `python -m trading_bot.data.pull --symbol BTCUSDT --interval 1h --years 4` produces validated, gap-audited Parquet plus a quality report, with the whole pipeline under test.

Why data first and not the backtester: every downstream result inherits data quality, garbage here silently poisons everything, and it's the component with the least design risk — a clean win that establishes our engineering standards before the genuinely hard design work (the fill model) begins.

---

One thing I want your input on before Milestone 1, since it shapes Phase 1 scope: **do you have a target jurisdiction and rough capital context for Mode 2, and is the funded-account path pointed at futures prop firms specifically, or crypto-funding firms?** That determines whether the second data collector (futures) enters Phase 1 or gets deferred, and whether we need to verify automation rules with specific firms early.

# MY RESPONSE


For the initial version, I want to prioritize building a high-quality research and engineering system rather than immediately targeting live profitability.

My answers:

1. Jurisdiction:
   I am based in Bulgaria (EU). For now, I don't want to commit to a specific funded account provider. The system should remain instrument-agnostic so we can adapt later.

2. Capital:
   For Mode 2, assume very small experimental capital only. I am not planning to risk meaningful money before extensive validation and paper trading.

3. Funding path:
   I am more interested in keeping the architecture compatible with both:

* crypto exchanges for research and experimentation
* futures prop firms as a possible future path

However, I agree that crypto should probably be the initial data source because it reduces complexity and cost.

Before Milestone 1, I want you to optimize the plan for a solo developer who is also learning. Keep the professional architecture principles, but avoid unnecessary complexity and premature engineering.

Please propose:

* a realistic MVP architecture
* exact first milestones
* what we should build first
* what we should intentionally postpone

The goal is not just to create a trading bot, but to create a professional-grade quant research platform that I can continue improving.


# Claude code Instructions

You are my senior Python quantitative developer.

Your job:
- Help me build a professional algorithmic trading research platform.
- Explain decisions before implementing them.
- Do not create unnecessary complexity.
- Prioritize clean architecture, testing, and learning.

My skill level:
- Strong beginner/intermediate Python
- Basic OOP
- Limited Git experience
- Limited quantitative finance knowledge

Rules:
1. Build incrementally.
2. Never generate the whole project at once.
3. Before adding a component explain:
   - what it does
   - why we need it
   - how it works
4. Write production-quality Python.
5. Use type hints.
6. Add tests for important functionality.

Current goal:
Build a crypto trading research platform starting with Binance historical data, backtesting, and strategy evaluation.