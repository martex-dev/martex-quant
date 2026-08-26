# Using the platform

Every command below is a subcommand of `tradingbot`. Add `--help` to any of
them for the full list of options.

> This is research software. Nothing here is financial advice, and no
> strategy in this repository is proven profitable with real money. Read
> [DISCLAIMER.md](../DISCLAIMER.md).

---

## Workspaces

A **workspace** is a directory holding your data lake, your paper-trading
records, and a copy of the research corpus. Create one:

```bash
tradingbot init my-lab
cd my-lab
```

It looks like this:

```
my-lab/
  data/
    lake/       validated market data (Parquet + catalog)
    paper/      paper-trading state, journals, equity curves, diaries
    series/     derived series
  docs/
    hypotheses/ the 29 pre-registered hypothesis documents
    research/   the trial ledger, the evaluation runbook, design notes
  config/
    universe.json   the rotation universe
```

Commands find the workspace in this order:

1. `--workspace DIR` (or `-w DIR`) on the command line
2. the `TRADING_BOT_HOME` environment variable
3. the current directory

So `cd my-lab` once and every command just works, or run
`tradingbot -w ~/my-lab dashboard` from anywhere.

Re-running `init` on an existing workspace is safe: it creates what is
missing and never overwrites what is there. Use `--overwrite` to restore
corpus files you have edited.

---

## `doctor` — check everything

```bash
tradingbot doctor
```

Reports your Python version, the install type, each dependency, whether the
research corpus resolved, and what your workspace contains. Run this first
whenever something is not working. Exit code is nonzero when it finds a
problem, so it is usable in scripts.

---

## `quickstart` — the guided first run

```bash
tradingbot quickstart
```

Downloads three years of daily Bitcoin bars, walk-forward backtests a
momentum strategy over them with realistic costs, prints the result, and
explains why a single good-looking backtest is not evidence of an edge.

Options: `--symbol ETHUSDT`, `--years 5`.

---

## `data` — the market data lake

```bash
tradingbot data pull --symbol BTCUSDT --interval 1d --years 4
tradingbot data status
```

`pull` collects, **validates**, and stores OHLCV history. Validation is not
cosmetic: data with ERROR-severity findings (gaps, duplicate timestamps,
impossible bars) is never written to the lake, and the command exits nonzero
so a script can react. It reports problems; it never silently repairs them.

Intervals: `1m`, `5m`, `15m`, `1h`, `4h`, `6h`, `12h`, `1d`.

`status` lists every dataset in the lake with its row count, date range, and
validation findings.

To pull the eight-symbol universe the Monte Carlo simulation needs:

```bash
for s in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT ADAUSDT DOGEUSDT LTCUSDT; do
  tradingbot data pull --symbol "$s" --interval 1d
done
```

On Windows PowerShell:

```powershell
foreach ($s in "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LTCUSDT") {
  tradingbot data pull --symbol $s --interval 1d
}
```

---

## `backtest` — walk-forward, out of sample

```bash
tradingbot backtest --symbol BTCUSDT --strategy momentum
tradingbot backtest --symbol ETHUSDT --strategy donchian --train 500 --test 120
```

Strategies: `momentum`, `vol-target`, `donchian`.

This is **walk-forward**, not a single fitted backtest. On each training
window the parameter is re-chosen from a grid; that choice is then judged
only on the window that follows, which the selection never saw. The printed
equity curve is the stitched out-of-sample result, with fees, spread, and
slippage already inside it.

Two things to understand about the output:

- **A high total return means very little on its own.** It is one strategy,
  one symbol, one run. Ranking a handful of parameters and reporting the
  winner is how most retail backtests fool their authors.
- Round-trip statistics are deliberately omitted. The curve is stitched
  across windows, so fills from different windows are not one trade history
  and win rate would be misleading.

---

## `montecarlo` — prop-firm evaluation odds

```bash
tradingbot montecarlo --paths 5000
```

Block-bootstraps the validated candidate's out-of-sample daily returns
thousands of times against prop-firm rule sets — profit target, trailing
drawdown, daily loss limit, time horizon — and reports the probability of
passing an evaluation at several risk scales, with 95% confidence intervals,
bust rates, and timeout rates.

This is the most useful command in the project for calibrating expectations.
It typically shows that scaling risk *up* lowers pass probability, and that
even a strategy that survived validation fails most evaluations.

Requires daily bars for the eight-symbol universe (see `data pull` above).

The bundled rule sets are **generic**, modelled on publicly known structures
— not any real firm's current terms. Pass rates are upper bounds: the
simulation checks trailing drawdown end-of-day while a real firm checks it
intraday. Many firms also prohibit automated trading outright. Verify the
actual rules before paying any evaluation fee.

---

## `paper` — forward testing

```bash
tradingbot paper --strategy rotation-stop --cash 5000
```

Runs **one** decision cycle: fetches recent daily bars, re-selects parameters
on the same schedule the walk-forward validation used, reconstructs the
strategy's state, simulates fills at the newest close with the backtest cost
model, and appends to the journal and equity curve.

Strategies: `vol-target`, `donchian`, `rotation`, `rotation-stop`,
`crash-bounce`, `combined`.

Run it **once per day**, shortly after 00:00 UTC. State lives in
`data/paper/<strategy>/`; each strategy is its own $5,000 account with its
own journal, equity curve, and plain-English daily diary.

### Scheduling it

**Linux / macOS** — `crontab -e`:

```
10 3 * * * cd ~/my-lab && ~/my-lab/.venv/bin/tradingbot paper --strategy rotation-stop >> data/paper/runs.log 2>&1
```

**Windows** — use the bundled launcher with Task Scheduler:

```
scripts\run_paper_daily.cmd
```

Set the task's "Start in" directory to your workspace. See the comments at
the top of that file.

Changing a strategy's spec means archiving its record and starting a fresh
$5,000 account. One spec per record — otherwise the equity curve is a
composite of two different systems and means nothing.

---

## `dashboard` — the operations view

```bash
tradingbot dashboard
tradingbot dashboard --port 8766 --no-open
```

Serves a local dashboard at `http://127.0.0.1:8765` (opens your browser
unless you pass `--no-open`) showing each paper account's equity curve,
trade journal, positions, and daily diary, plus the Lab view over the
hypothesis ledger.

It binds to `127.0.0.1` only — it is not reachable from your network, and it
has no authentication. Do not put it behind a public reverse proxy.

There is **no button anywhere in the dashboard that trades real money.**
That is deliberate.

---

## `ledger` — the research record

```bash
tradingbot ledger
tradingbot ledger --verdict killed --limit 40
tradingbot ledger --limit 0
```

Every trial ever run, with its verdict, family, and published deflated Sharpe
ratio — including the failures, which is the point. The statistical bar for
any new result is deflated against the *total* trial count, not just the
survivors, so the graveyard is load-bearing evidence rather than an
embarrassment.

Full reasoning per hypothesis lives in `docs/hypotheses/`.

---

## Going further

- Add a strategy: implement `Strategy` in `src/trading_bot/strategies/`. A
  strategy maps market history to a target exposure in `[-1, +1]`. It never
  sizes positions, never creates orders, and never sees account state — that
  is portfolio and risk territory, by design, which is what makes strategies
  unit-testable and the risk layer un-bypassable.
- Before you trust any result, read
  [`docs/research/eval-runbook.md`](research/eval-runbook.md) and the
  hypothesis documents. The method matters more than any individual number.
- Pre-register before you test. The rule that makes this project's ledger
  worth anything is that every hypothesis was written down, with its pass
  bars, and committed *before* the run.

## Real money

Live execution is not exposed through this CLI, is never a dashboard button,
requires your own broker credentials and a deliberate command-line action,
and sits behind a risk guard whose KILLED latch only a human can clear.
Please leave those gates in place. See [DISCLAIMER.md](../DISCLAIMER.md).
