# PROJECT_STATE.md — operational snapshot (2026-07-12)

Read together with PROJECT_MEMORY.md (knowledge/lessons) and CLAUDE.md
(standing instructions). This file = what is RUNNING and what happens next.

## Phase

Phase 5 (paper trading). Shakedown day 3 of 14; **gate: ~2026-07-25** —
if the paper record is clean (no missed nightly runs, sane decisions),
buy the eval. NO fee before the gate.

## The three paper accounts ($5,000 each, since 2026-07-11/12)

| Account | Spec | Universe | Status |
|---|---|---|---|
| vol-target | VolTargetMomentum (30% vol target, 30d window), per-symbol lookback walk-forward {7..180d}/90d reselect, long/flat | legacy 8 | Flat (no momentum regime) |
| rotation | VolTargetRotation K=2, L walk-forward {30,90}/90d reselect, abs-momentum gate, 30% vol budget | WIDE 40 (config/universe.json) | Holding DEXE+SYN ~6% each; first green mark +$17 |
| crash-bounce | CrashBounce: BTC day < -3% -> EW all alts one day; zero params | WIDE alts | Flat (no crash) |

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

~195 tests green, ruff + strict mypy clean, CI on GitHub. Trial ledger: 83
(single source of truth: PROJECT_MEMORY.md + CLAUDE.md history).

## Next actions (in order)

1. Nothing daily — let the shakedown run; watch dashboard.
2. 2026-07-25 gate: review 14-day record -> eval purchase decision +
   engine choice (needs firm symbol list).
3. Backlog (docs/research/backlog.md): options/Deribit VRP data project,
   correlation-spike de-risking, carry infra (post-eval, own-capital).
4. October: move paper task 03:10 -> 02:10 local (DST) to stay near the
   UTC close.
