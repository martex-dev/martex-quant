"""`martex-quant` — the command line entry point for an installed copy.

Everything the platform can do was already reachable as `python -m
martex_quant.<something>` or a script under `scripts/`, but only from a git
checkout with the repo root as the working directory. This module is the
front door: one command, discoverable subcommands, and a workspace so an
installed wheel knows where its data lives.

    martex-quant init my-lab        # scaffold a workspace + research corpus
    martex-quant quickstart         # pull data, backtest it, show the result
    martex-quant dashboard          # operations dashboard in the browser

Design notes:

- Heavy imports (polars, ccxt, the engine) happen inside the handlers, not at
  module scope. `martex-quant --help` should be instant, and `doctor` has to be
  able to report a missing dependency rather than die on it.
- Handlers return a process exit code. Anything that touches the network or
  the lake reports failure by returning nonzero, never by raising a traceback
  at a user who did not write the code.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from martex_quant import __version__
from martex_quant import workspace as ws

DASHBOARD_PORT = 8765

# Strategy names the paper trader accepts. Duplicated as literals rather than
# imported, so `--help` does not pay for importing the decision core.
PAPER_STRATEGIES = (
    "vol-target",
    "donchian",
    "rotation",
    "rotation-stop",
    "crash-bounce",
    "combined",
)

BACKTEST_STRATEGIES = {
    # name: (grid, description)
    "momentum": ([7, 14, 30, 60, 90, 180], "time-series momentum, long/flat"),
    "vol-target": ([7, 14, 30, 60, 90, 180], "momentum scaled to a volatility target"),
    "donchian": ([10, 20, 40, 55, 80, 120], "Donchian channel breakout"),
}


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="martex-quant",
        description=(
            "Quantitative trading research platform: data, backtesting, "
            "statistical validation, Monte Carlo, paper trading, dashboard. "
            "Research software — not financial advice. See DISCLAIMER.md."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # One command per line: Windows PowerShell has no `&&`, and chaining
        # there is a parser error that runs neither half.
        epilog=("first run:\n  martex-quant init my-lab\n  cd my-lab\n  martex-quant quickstart\n"),
    )
    parser.add_argument("--version", action="version", version=f"martex-quant {__version__}")
    parser.add_argument(
        "-w",
        "--workspace",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"workspace directory (default: ${ws.HOME_ENV} or the current directory)",
    )
    subs = parser.add_subparsers(dest="command", metavar="<command>")

    p_init = subs.add_parser("init", help="create a workspace and copy in the research corpus")
    p_init.add_argument("directory", type=Path, nargs="?", default=Path("."))
    p_init.add_argument(
        "--overwrite", action="store_true", help="replace corpus files that already exist"
    )
    p_init.set_defaults(handler=cmd_init, needs_workspace=False)

    p_doctor = subs.add_parser("doctor", help="check the install, the workspace, and the data")
    p_doctor.set_defaults(handler=cmd_doctor, needs_workspace=False)

    p_quick = subs.add_parser(
        "quickstart", help="guided first run: pull a year of data, backtest it, explain the result"
    )
    p_quick.add_argument("--symbol", default="BTCUSDT")
    p_quick.add_argument("--years", type=float, default=2.0)
    p_quick.set_defaults(handler=cmd_quickstart, needs_workspace=True)

    p_data = subs.add_parser("data", help="market data lake: pull and inspect")
    data_subs = p_data.add_subparsers(dest="data_command", metavar="<action>")
    p_pull = data_subs.add_parser("pull", help="download, validate, and store OHLCV history")
    p_pull.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    p_pull.add_argument("--interval", required=True, help="1m 5m 15m 1h 4h 6h 12h 1d")
    p_pull.add_argument("--years", type=float, default=4.0)
    p_pull.set_defaults(handler=cmd_data_pull, needs_workspace=True)
    p_status = data_subs.add_parser("status", help="what is in the lake")
    p_status.set_defaults(handler=cmd_data_status, needs_workspace=True)
    p_data.set_defaults(handler=_needs_subcommand(p_data), needs_workspace=False)

    p_back = subs.add_parser(
        "backtest", help="walk-forward backtest a strategy over lake data, with costs"
    )
    p_back.add_argument("--symbol", default="BTCUSDT")
    p_back.add_argument("--strategy", choices=sorted(BACKTEST_STRATEGIES), default="momentum")
    p_back.add_argument("--interval", default="1d")
    p_back.add_argument("--train", type=int, default=365, help="train window in bars")
    p_back.add_argument("--test", type=int, default=90, help="out-of-sample window in bars")
    p_back.set_defaults(handler=cmd_backtest, needs_workspace=True)

    p_mc = subs.add_parser(
        "montecarlo", help="Monte Carlo the candidate against prop-firm rule sets"
    )
    p_mc.add_argument("--paths", type=int, default=5000, help="simulated evaluations per ruleset")
    p_mc.set_defaults(handler=cmd_montecarlo, needs_workspace=True)

    p_paper = subs.add_parser("paper", help="run one paper-trading cycle (one day's decision)")
    p_paper.add_argument("--strategy", choices=PAPER_STRATEGIES, default="rotation-stop")
    p_paper.add_argument("--cash", type=float, default=5_000.0)
    p_paper.add_argument("--root", type=Path, default=None, help="state dir override")
    p_paper.set_defaults(handler=cmd_paper, needs_workspace=True)

    p_dash = subs.add_parser("dashboard", help="serve the operations dashboard")
    p_dash.add_argument("--port", type=int, default=DASHBOARD_PORT)
    p_dash.add_argument("--no-open", action="store_true", help="do not open a browser")
    p_dash.set_defaults(handler=cmd_dashboard, needs_workspace=True)

    p_ledger = subs.add_parser("ledger", help="the hypothesis ledger: every trial ever run")
    p_ledger.add_argument("--limit", type=int, default=25, help="rows to show (0 for all)")
    p_ledger.add_argument("--verdict", default=None, help="filter, e.g. VALIDATED or KILLED")
    p_ledger.set_defaults(handler=cmd_ledger, needs_workspace=True)

    return parser


def _needs_subcommand(parser: argparse.ArgumentParser) -> Any:
    def handler(_: argparse.Namespace) -> int:
        parser.print_help()
        return 2

    return handler


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    target = args.directory.expanduser().resolve()
    print(f"workspace: {target}")
    for line in ws.initialise(target, overwrite=args.overwrite):
        print(f"  {line}")
    print()
    print("next:")
    if target != Path.cwd().resolve():
        print(f"  cd {_display_path(target)}")
    print("  martex-quant quickstart")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from martex_quant.bundle import bundle_root, is_editable_checkout

    target = ws.resolve(args.workspace)
    ok = True

    print(f"martex-quant {__version__}")
    print(f"python      {sys.version.split()[0]} ({sys.executable})")
    print(f"install     {'source checkout' if is_editable_checkout() else 'installed package'}")
    print()

    print("dependencies")
    for module, why in (
        ("polars", "dataframes"),
        ("pyarrow", "parquet lake"),
        ("pydantic", "config and event schemas"),
        ("ccxt", "exchange data"),
    ):
        found = _try_import(module)
        ok = ok and found
        print(f"  {'ok     ' if found else 'MISSING'} {module:<10} {why}")
    print()

    print("research corpus")
    source = bundle_root()
    if source is None:
        print("  MISSING docs/research/ledger/trials.toml — the ledger is not available")
        ok = False
    else:
        print(f"  ok      {source}")
    print()

    print(f"workspace   {target}")
    if not ws.looks_like_workspace(target):
        print("  not initialised — run: martex-quant init")
        ok = False
    else:
        lake = target / "data" / "lake"
        entries = _catalog_entries(lake)
        if entries is None:
            print("  lake      empty — run: martex-quant data pull --symbol BTCUSDT --interval 1d")
        else:
            print(f"  lake      {len(entries)} dataset(s)")
        paper = target / "data" / "paper"
        accounts = sorted(p.name for p in paper.glob("*") if p.is_dir()) if paper.is_dir() else []
        named = ": " + ", ".join(accounts) if accounts else ""
        print(f"  paper     {len(accounts)} account(s){named}")

    print()
    print("ok" if ok else "problems found — see above")
    return 0 if ok else 1


def cmd_quickstart(args: argparse.Namespace) -> int:
    symbol = args.symbol
    print("=" * 68)
    print("QUICKSTART — pull real data, backtest it honestly, read the result")
    print("=" * 68)
    print()
    print(f"step 1/2  downloading {args.years:g} years of daily {symbol} bars from Binance")
    print("          (validated on arrival; bad data is never written to the lake)")
    print()

    code = cmd_data_pull(
        argparse.Namespace(symbol=symbol, interval="1d", years=args.years, workspace=None)
    )
    if code != 0:
        print()
        print("data pull failed. Common causes: no internet, or Binance is blocked")
        print("in your region. Nothing else in the quickstart can run without it.")
        return code

    print()
    print("step 2/2  walk-forward backtest: momentum, costs included")
    print("          Parameters are re-chosen on each training window and then")
    print("          judged only on the window that follows — out of sample.")
    print()

    code = cmd_backtest(
        argparse.Namespace(
            symbol=symbol, strategy="momentum", interval="1d", train=365, test=90, workspace=None
        )
    )
    if code != 0:
        return code

    print()
    print("-" * 68)
    print("What you are looking at")
    print("-" * 68)
    print(
        "This is one strategy, one symbol, one run. It is NOT evidence of an\n"
        "edge, whatever the numbers say. A single backtest that looks good is\n"
        "the normal output of random chance plus parameter choice — which is\n"
        "why this project ran 120 pre-registered hypotheses and killed most\n"
        "of them.\n"
    )
    print("Where to go next:")
    print("  martex-quant ledger              every hypothesis and its verdict")
    print("  martex-quant montecarlo          pass odds against prop-firm rules")
    print("  martex-quant paper --strategy rotation-stop     one forward day")
    print("  martex-quant dashboard           equity curves, journals, diaries")
    return 0


def cmd_data_pull(args: argparse.Namespace) -> int:
    from martex_quant.data.pull import run as pull_run

    argv = ["--symbol", args.symbol, "--interval", args.interval, "--years", str(args.years)]
    try:
        return pull_run(argv)
    except Exception as exc:  # network, exchange, or validation failure
        print(f"data pull failed: {exc}", file=sys.stderr)
        return 1


def cmd_data_status(args: argparse.Namespace) -> int:
    lake = Path("data") / "lake"
    entries = _catalog_entries(lake)
    if entries is None:
        print(f"no catalog at {lake}/catalog.json — the lake is empty")
        print("pull some data:  martex-quant data pull --symbol BTCUSDT --interval 1d")
        return 1

    print(f"{len(entries)} dataset(s) in {lake.resolve()}")
    print()
    print(f"{'symbol':<12} {'int':<5} {'rows':>7}  {'from':<11} {'to':<11} {'err':>4} {'warn':>5}")
    for entry in entries:
        print(
            f"{entry.symbol:<12} {entry.interval.value:<5} {entry.rows:>7}  "
            f"{entry.start.date().isoformat():<11} {entry.end.date().isoformat():<11} "
            f"{entry.validation_errors:>4} {entry.validation_warnings:>5}"
        )
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    from martex_quant.backtesting.engine import BacktestConfig
    from martex_quant.backtesting.metrics import compute_metrics
    from martex_quant.backtesting.research import walk_forward_backtest
    from martex_quant.data.models import Interval
    from martex_quant.data.store.parquet_store import ParquetStore
    from martex_quant.strategies.breakout import DonchianBreakout
    from martex_quant.strategies.momentum import TimeSeriesMomentum
    from martex_quant.strategies.vol_target import VolTargetMomentum

    try:
        interval = Interval(args.interval)
    except ValueError:
        print(f"unknown interval {args.interval!r}", file=sys.stderr)
        return 2

    factories = {
        "momentum": (lambda p: TimeSeriesMomentum(int(p)), lambda p: int(p) + 1),
        "vol-target": (lambda p: VolTargetMomentum(int(p)), lambda p: max(int(p), 30) + 1),
        "donchian": (lambda p: DonchianBreakout(int(p)), lambda p: int(p) + 1),
    }
    grid = BACKTEST_STRATEGIES[args.strategy][0]
    factory, warmup = factories[args.strategy]

    store = ParquetStore(Path("data") / "lake")
    try:
        df = store.read(args.symbol, interval)
    except Exception as exc:
        print(f"cannot read {args.symbol} {interval.value} from the lake: {exc}", file=sys.stderr)
        print(
            f"pull it first:  martex-quant data pull --symbol {args.symbol} "
            f"--interval {interval.value}",
            file=sys.stderr,
        )
        return 1

    needed = args.train + args.test
    if df.height < needed:
        print(
            f"{args.symbol} {interval.value} has {df.height} bars; this walk-forward "
            f"needs at least {needed} (train {args.train} + test {args.test}).",
            file=sys.stderr,
        )
        print("Pull more history, or lower --train/--test.", file=sys.stderr)
        return 1

    outcome = walk_forward_backtest(
        df=df,
        symbol=args.symbol,
        interval=interval,
        param_grid=grid,
        strategy_factory=factory,
        warmup_of=warmup,
        train_size=args.train,
        test_size=args.test,
        config=BacktestConfig(initial_cash=10_000.0),
    )

    print(
        f"{args.strategy} on {args.symbol} {interval.value}  "
        f"({BACKTEST_STRATEGIES[args.strategy][1]})"
    )
    print(f"walk-forward: {len(outcome.windows)} window(s), train {args.train} / test {args.test}")
    print()
    print(f"{'window':>6} {'param':>7} {'train sharpe':>13} {'oos growth':>11} {'fills':>6}")
    for i, window in enumerate(outcome.windows, start=1):
        print(
            f"{i:>6} {window.chosen_param:>7.0f} {window.train_sharpe:>13.2f} "
            f"{(window.test_growth - 1) * 100:>10.2f}% {window.n_test_fills:>6}"
        )
    print()

    metrics = compute_metrics(outcome.oos_equity, [], interval)
    print("stitched out-of-sample equity")
    print(f"  total return: {(outcome.total_growth - 1) * 100:+.2f}%")
    print(f"  sharpe (ann.): {metrics.sharpe:.2f}   max drawdown: {metrics.max_drawdown_pct:.2f}%")
    print()
    print("Costs (fees, spread, slippage) are already inside these numbers.")
    print("Round-trip stats are omitted here: the curve is stitched across")
    print("windows, so fills from different windows are not one trade history.")
    return 0


def cmd_montecarlo(args: argparse.Namespace) -> int:
    import statistics

    from martex_quant.backtesting.candidate import candidate_oos_daily_returns
    from martex_quant.risk_management.prop_sim import PropFirmRules, simulate_evaluation

    lake = Path("data") / "lake"
    try:
        returns = candidate_oos_daily_returns(lake)
    except Exception as exc:
        print(f"cannot build the candidate return stream: {exc}", file=sys.stderr)
        print(
            "This needs daily bars for the 8-symbol universe. Pull them with:\n"
            "  for s in BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT ADAUSDT DOGEUSDT LTCUSDT; "
            'do martex-quant data pull --symbol "$s" --interval 1d; done',
            file=sys.stderr,
        )
        return 1

    ann_vol = statistics.stdev(returns) * (365**0.5)
    print(
        f"candidate out-of-sample returns: {len(returns)} days, "
        f"mean {statistics.mean(returns) * 100:+.3f}%/day, annualised vol {ann_vol * 100:.1f}%"
    )
    print()

    rulesets = [
        PropFirmRules(
            name="GENERIC-A 50k",
            account_size=50_000.0,
            profit_target_pct=0.06,
            trailing_dd_pct=0.04,
            daily_loss_pct=0.02,
            max_days=None,
            evaluation_fee=170.0,
        ),
        PropFirmRules(
            name="GENERIC-B 50k (strict)",
            account_size=50_000.0,
            profit_target_pct=0.08,
            trailing_dd_pct=0.03,
            daily_loss_pct=0.02,
            max_days=90,
            evaluation_fee=100.0,
        ),
    ]

    header = (
        f"{'ruleset':<24} {'scale':>6} {'pass':>7} {'95% CI':>16} "
        f"{'bust':>7} {'timeout':>8} {'days':>6}"
    )
    print(header)
    for rules in rulesets:
        for scale in (0.25, 0.5, 1.0, 2.0):
            result = simulate_evaluation(returns, rules, risk_scale=scale, n_paths=args.paths)
            ci = f"[{result.pass_ci_low:.1%}, {result.pass_ci_high:.1%}]"
            days = (
                str(result.median_days_to_pass) if result.median_days_to_pass is not None else "n/a"
            )
            print(
                f"{rules.name:<24} {scale:>6.2f} {result.pass_rate:>7.1%} {ci:>16} "
                f"{result.fail_rate:>7.1%} {result.timeout_rate:>8.1%} {days:>6}"
            )
    print()
    print(
        "These rule sets are GENERIC, modelled on publicly known structures —\n"
        "they are not any real firm's current terms. Pass rates are upper\n"
        "bounds: the simulation checks trailing drawdown end-of-day, while a\n"
        "real firm checks it intraday. Many firms also prohibit automation.\n"
        "Verify the actual rules before paying any evaluation fee."
    )
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    import json

    from martex_quant.live.paper import PaperTrader

    root = args.root if args.root is not None else Path("data") / "paper" / args.strategy
    try:
        trader = PaperTrader(args.strategy, root, initial_cash=args.cash)
        mark = trader.run_once()
    except Exception as exc:
        print(f"paper run failed: {exc}", file=sys.stderr)
        print(
            "This command fetches live bars from Binance; check your connection.", file=sys.stderr
        )
        return 1

    print(json.dumps(mark, indent=2))
    print()
    print(f"state written to {root.resolve()}")
    print("Run this once a day, shortly after 00:00 UTC. See docs for scheduling.")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from martex_quant.dashboard.server import serve

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_open:
        # A headless box has no browser; serving is the point, not opening.
        with contextlib.suppress(Exception):
            webbrowser.open(url)
    print(f"serving {Path.cwd()}")
    try:
        serve(Path.cwd(), port=args.port)
    except KeyboardInterrupt:
        print()
        print("dashboard stopped")
    except OSError as exc:
        print(f"cannot serve on port {args.port}: {exc}", file=sys.stderr)
        print("Another process may already be using it; try --port 8766.", file=sys.stderr)
        return 1
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    from martex_quant.research.ledger.query import summarise
    from martex_quant.research.ledger.registry import LEDGER_DIR, TRIALS_FILE, load_ledger

    path = Path.cwd() / LEDGER_DIR / TRIALS_FILE
    if not path.is_file():
        print(f"no ledger at {path}", file=sys.stderr)
        print("Run `martex-quant init` in this directory to copy in the corpus.", file=sys.stderr)
        return 1

    ledger = load_ledger(Path.cwd())
    print(summarise(ledger))
    print()

    trials = ledger.trials
    if args.verdict:
        wanted = args.verdict.strip().lower()
        trials = [t for t in trials if t.verdict.value.lower() == wanted]
        if not trials:
            seen = sorted({t.verdict.value for t in ledger.trials})
            print(f"no trials with verdict {args.verdict!r}. Known verdicts: {', '.join(seen)}")
            return 0

    shown = trials if args.limit == 0 else trials[-args.limit :]
    hidden = len(trials) - len(shown)
    if hidden:
        print(f"showing the last {len(shown)} of {len(trials)} (use --limit 0 for all)")
        print()

    print(f"{'#':>4} {'hypothesis':<12} {'verdict':<12} {'family':<32} {'DSR':>6}")
    for trial in shown:
        dsr = f"{trial.dsr:.3f}" if trial.dsr is not None else "-"
        print(
            f"{trial.trial_id:>4} {_truncate(trial.hypothesis, 12):<12} "
            f"{trial.verdict.value:<12} {_truncate(trial.family, 32):<32} {dsr:>6}"
        )
    print()
    print("Every trial ever run stays here, including the failures — the")
    print("statistical bar is deflated against all of them, not just survivors.")
    print("Full reasoning per hypothesis: docs/hypotheses/")
    return 0


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _try_import(module: str) -> bool:
    from importlib.util import find_spec

    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _catalog_entries(lake: Path) -> list[Any] | None:
    """Catalog entries, or None when the lake has never been written to."""
    if not (lake / "catalog.json").is_file():
        return None
    from martex_quant.data.store.catalog import Catalog

    return Catalog(lake).entries()


def _truncate(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _display_path(path: Path) -> str:
    try:
        relative = path.relative_to(Path.cwd())
    except ValueError:
        return str(path)
    return str(relative) if str(relative) != "." else str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "handler", None) is None:
        parser.print_help()
        return 0

    if getattr(args, "needs_workspace", False):
        target = ws.resolve(args.workspace)
        if not target.is_dir():
            print(f"no such workspace: {target}", file=sys.stderr)
            print("Create it with:  martex-quant init", file=sys.stderr)
            return 1
        os.chdir(target)

    handler: Any = args.handler
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
