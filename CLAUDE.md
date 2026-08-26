## SESSION START — READ THESE FIRST

1. **PROJECT_STATE.md** — what is running right now, schedules, the firm,
   the eval plan, next actions.
2. **PROJECT_MEMORY.md** — full hypothesis ledger (105 trials), all
   results, meta-findings, lessons, open caveats.

Do not re-derive or re-litigate anything recorded there. Do not re-test
killed ideas without a new pre-registered spec and a stated reason.

## NON-NEGOTIABLE OPERATING RULES (distilled from 23 hypotheses)

- Pre-register every hypothesis: numbered doc in docs/hypotheses/ with
  verdict bars, COMMITTED BEFORE any test runs. Count every trial
  (including variants and descriptive horizons) in the ledger; DSR is
  always benchmarked against ALL trials ever run.
- Kill test (cheap information study) BEFORE any strategy build.
  Event-driven engine is the source of truth for strategies; vectorized
  screening only pre-engine.
- New features must beat the DEPLOYED system incrementally, not zero.
- Paper accounts run only validated/eligible specs; one spec per record
  (spec change = archive the record, fresh $5,000 start).
- Live/real-money actions are gated: the runbook
  (docs/research/eval-runbook.md) governs the eval; going live is a
  deliberate CLI step, never a dashboard button; the guard's KILLED
  latch is cleared only by a human.
- Every session: run pytest + ruff + strict mypy before committing;
  commit per component; push to origin (GitHub MartexHACK/martex-quant).
- Restart the dashboard server after changing dashboard code.
- Report negative results with the same rigor as positive ones. The
  ledger's honesty is the project's only real asset.

## THE USER'S GOAL (stated 2026-07-12 — calibrate everything to it)

This is an INCOME project, not an investing project. Target:
income-scale returns (aspiration >= 20%/month; e.g. >= $1k/mo on a $5k
funded account), starting from tiny capital ($50-100 own, $5k funded).
Mode 2 (aggressive growth) of the original charter is FIRST-CLASS, not
an afterthought. Concretely:

- Strategy search and RR/sizing decisions optimize expected GROWTH and
  monthly income potential; "maximum survivable aggression"
  (growth-optimal/Kelly-style sizing of validated edges), not
  drawdown minimization for its own sake.
- Present the aggressive option's real numbers (including failure
  probability and worst windows) instead of defaulting to the
  conservative recommendation; the user chooses.
- The ONE thing that never bends for the goal: validation discipline.
  No unvalidated edge gets aggressive sizing — busting guarantees
  $0/month. Aggression in sizing, discipline in evidence.

- Python 3.12, polars, src layout, stdlib-first (no new deps without
  reason). Windows: use the Write tool for .cmd files; full env +
  CREATE_NO_WINDOW for subprocesses; PYTHONIOENCODING=utf-8.
- Update PROJECT_STATE.md when operational reality changes and
  PROJECT_MEMORY.md when verdicts/lessons land; keep both current so
  any session can hand off cleanly.
- The user is a student and strong-beginner programmer: explain what
  matters in plain language (the dashboard diary sets the tone), be
  brutally honest about odds and expectations, challenge bad ideas, and
  never let enthusiasm outrun the ledger.


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
martex_quant/

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
martex_quant/
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

**Milestone 1: Validated Data Foundation.** Scope: repository scaffolding with CI, lint, typing; the `data/` subsystem complete — one collector (Binance OHLCV via ccxt is the cheapest starting point since it's free and lets us build the pipeline before spending on futures data), the validation processor, the Parquet store with catalog, and a data-quality report command. Deliverable: `python -m martex_quant.data.pull --symbol BTCUSDT --interval 1h --years 4` produces validated, gap-audited Parquet plus a quality report, with the whole pipeline under test.

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