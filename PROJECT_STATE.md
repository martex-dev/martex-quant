# PROJECT_STATE.md — operational snapshot (2026-07-12)

Read together with PROJECT_MEMORY.md (knowledge/lessons) and CLAUDE.md
(standing instructions). This file = what is RUNNING and what happens next.

## Phase

Phase 5 (paper trading). Shakedown day 3 of 14; **gate: ~2026-07-25** —
if the paper record is clean (no missed nightly runs, sane decisions),
buy the eval. NO fee before the gate.

## The four paper accounts ($5,000 each)

| Account | Spec | Universe | Status |
|---|---|---|---|
| vol-target | VolTargetMomentum (30% vol target, 30d window), per-symbol lookback walk-forward {7..180d}/90d reselect, long/flat | legacy 8 | Flat (no momentum regime) |
| rotation | VolTargetRotation K=2, L walk-forward {30,90}/90d reselect, abs-momentum gate, 30% vol budget | WIDE 40 (config/universe.json) | Holding DEXE+SYN ~6% each; first green mark +$17 |
| crash-bounce | CrashBounce: BTC day < -3% -> EW all alts one day; zero params | WIDE alts | Flat (no crash) |
| rotation-stop | StopVolTargetRotation = rotation spec + chandelier latch (2xATR14 off 30d high, clears on new 30d high); H42b, DSR 0.992 | WIDE 40 | Since 2026-07-12; holds ATM+DEXE ~11% each (SYN stop-latched — first live divergence from rotation) |

All three run nightly at 03:10 local via Task Scheduler task
"TradingBot Paper Trader" -> scripts/run_paper_daily.cmd (StartWhenAvailable).
Each writes equity.jsonl + journal.jsonl + a plain-English diary story
per day under data/paper/<name>/.

## Automation inventory

- Task "TradingBot Paper Trader": daily 03:10 local (00:10 UTC summer).
- Dashboard: http://127.0.0.1:8765 — HKCU Run key `TradingBotDashboard`
  (windowless pythonw, scripts/dashboard_service.pyw). Desktop shortcut
  "Trading Bot Dashboard". RESTART the server after any dashboard code
  change (it loads Python once; stale rev in header = tell).
- Guard (live/guard.py): built+tested, NOT scheduled yet — gets a 5-min
  Task Scheduler entry on eval day 0 (daily trip -2.5%, static latch
  $4,750 via KILLED file).
- GitHub: private repo MartexHACK/trading-bot, CI green, push after commit.

## The firm (CFD program — confirmed answers)

- 1-step 5k eval: target +10%, max loss $300 STATIC, daily loss 3%,
  unlimited time, 1:30, fee **$51.80**. Automation ALLOWED. No weekend
  restrictions. (Other sizes: 10k 1-step $98; 2-step 2.5k/$19, 5k/$35,
  10k/$69. Futures arm PARKED: 25k, 4% trailing EOD, 40% consistency,
  Swing $120 — revisit post-funded, needs micro-crypto check.)
- Platform: MT5 (chosen). Adapter built: live/mt5_broker.py +
  live/trade.py (DRY-RUN default, --live flag, magic 520001).
  User's terminal currently logged into MetaQuotes-Demo (no crypto) —
  firm server credentials arrive only WITH the eval purchase.

## Eval plan (docs/research/eval-runbook.md — pre-registered)

- At gate: choose eval engine. V1 vol-target @1.5x = 50.0% pass (fully
  shaken down, needs only 8 majors). Rotation-wide @0.5x = 62.9% pass,
  VALIDATED (DSR 0.990) but younger paper record and needs ~40 symbols —
  **blocked on the firm's CFD symbol list coverage (day-0 check)**.
- Day 0 = verification only: dry run vs firm server, write
  config/symbol_map.json, check contract sizes/min volumes/spreads.
- Live discipline: RISK_SCALE 1.5 (V1) in live/trade.py; guard scheduled;
  no manual trades; budget 2 attempts (~$104); failure/success handling
  pre-written in the runbook.

## Data lake

48 validated datasets, 0 errors: legacy 8 (1h+1d, 2017+), +32 wide-universe
coins (1d, full depth). Funding cache data/funding/ (7y, 8 symbols); perp
closes data/perp/. Universe rule in config/universe.json.

## Code health

~200 tests green, ruff + strict mypy clean, CI on GitHub. Trial ledger:
104 (single source of truth: PROJECT_MEMORY.md).

## Research batches H24-H43 (2026-07-12, complete)

17 new base hypotheses + combos: 15 killed at info stage, blend-V1
killed at strategy grade, H41 combined book NOT eligible.
**Rotation+chandelier-stop (42b) is CANDIDATE with DSR 0.992, beating
the champion on every metric** (Sharpe 1.47/1.10, MDD -29%/-58%, prop
73.0%/62.8% @0.5x) -> paper account #4. V1+stop (42a) also candidate.
H43 combo screen: momentum books inter-correlate 0.52-0.82 (no blends);
rot-stop+bounce (43a) killed on eval bars but is THE own-capital
archive book (Sharpe 1.55, +79%/yr, DSR 1.000, corr 0.118 components).
New strategies: strategies/blend.py, strategies/stops.py.

## JULY SPRINT (user goal 2026-07-12: ~$400 banked by Jul 31)

Plan: docs/research/july-sprint.md + eval-runbook-sprint-amendment.md
(**SINGLE-ATTEMPT REVISION 2026-07-13 governs**: user has ONE fee).
**FIRM: HyroTrader 1-step 5k, $69 + $39 swing upgrade = $108.**
**Config: rotation-stop ALONE @ RISK_SCALE 0.85** — P(pass) 62.3%,
bust 37.7%, median 48d (funded ~end Aug); bounce overlay dropped from
the eval (lowers one-shot odds); no retries, bust -> gate plan.
Rule adjustments stand: per-position 3% stops, low-cap filter, 1.8x
gross clamp, consistency dilution tactic. **User buys 2026-07-13**
(platform: Bybit), then API keys -> config/secrets/hyro.json.

## Next actions (in order)

1. USER (2026-07-13): buy 1-step 5k + SWING upgrade ($108), Bybit
   platform; create API keys (trade-only); save config/secrets/hyro.json;
   say "keys are in".
2. BUILD (in progress): live/bybit_broker.py (ccxt, DRY-RUN default),
   universe_hyro.json low-cap filter, per-position 3% stops, 1.8x gross
   clamp, sprint scheduler, guard entry. Dry-run go/no-go together
   BEFORE first live order.
3. Sprint doctrine going forward: EVALS get aggressive sprint config
   (downside = fee); FUNDED accounts get sustainable sizing (downside
   = the account). Switch-down automated per amendment.
4. Paper shakedown continues untouched (4 accounts nightly); Jul 25
   gate now only governs the PATIENT fallback if all 3 sprint attempts
   bust.
5. TRACK 2 CLOSED (2026-07-13): the full intraday campaign (H44-57,
   26 trials) is complete. Meta-finding: intraday crypto REVERTS and
   every reversion premium (4 independent confirmations) is 2-4bp —
   real but BELOW retail execution costs; best strategy-grade attempt
   H52 Sharpe 0.69 vs 0.70 bar. The intraday family is CLOSED absent
   a new data dimension (H54 OI is registered-but-data-blocked).
   Data assets gained: 15m OHLCV + taker-buy imbalance, 12 Bybit/
   Binance perps, 2021+ (data/intraday/). Ledger: 120 (119 run).
3. Backlog (docs/research/backlog.md): options/Deribit VRP data project,
   correlation-spike de-risking, carry infra (post-eval, own-capital);
   own-capital book = rotation-stop + crash-bounce overlay (43a:
   Sharpe 1.55, +79%/yr, fails only eval geometry) — register
   own-capital bars post-funded.
4. October: move paper task 03:10 -> 02:10 local (DST) to stay near the
   UTC close.
