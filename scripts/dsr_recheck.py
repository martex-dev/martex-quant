"""Re-deflate the momentum books against the CURRENT ledger total.

    .venv/Scripts/python scripts/dsr_recheck.py

Correction candidate 7, acted on. Every published DSR was deflated against
the trial count at the time it was computed (65 for rotation, 104 for
rotation-stop), never against today's total. The ledger has grown to 125.
The question is simple and load-bearing: **does the DEPLOYED spec still
clear the 0.95 bar?**

WHAT THIS DOES NOT DO
---------------------
It does not alter a published value. Published figures are printed next to
the recomputation so the two are always read together.

Only ``n_trials`` changes. Every other input — the return stream, its
construction, the per-period Sharpe convention, skew, kurtosis, ``n_obs``,
and the ``trial_sharpe_variance`` estimator — is reconstructed to be exactly
what the original study fed. That isolates the effect of the trial count,
which is the entire question.

REPRODUCE FIRST, OR SAY NOTHING
-------------------------------
Each strategy is reproduced at its ORIGINAL n_trials before anything is
recomputed. If the reproduction misses the published figure, no recomputed
number is reported for that strategy. An earlier version of this script
failed exactly there and was left unmerged rather than published — the
figures below exist because that guard was obeyed, not bypassed.

The two defects that guard caught, and how each is fixed here:

* **rotation-stop reproduced 0.951 against a published 0.992.** The study
  did not deflate the full cached stream. It inner-joined the candidate and
  the champion on timestamp and used that COMMON window, and its variance
  input is the variance of exactly TWO per-period Sharpes (candidate and
  champion) over that window. It also builds returns with
  ``pct_change().fill_null(0.0)``, which keeps the first bar as a zero
  return; the earlier attempt used ``drop_nulls()`` and silently lost a row.
* **rotation reproduced 0.994 against a published 0.990 and was wrongly
  marked OK.** That agreement was coincidence: the sample was 3,158 days
  against the study's 2,880 because the study deflates its WALK-FORWARD
  out-of-sample stream, not a full backtest. Its variance input is the
  variance of per-lookback Sharpes over the GRID, each sliced to the
  out-of-sample start. It also passes ``n_obs=oos.height`` while the return
  series has ``height - 1`` elements — an off-by-one in the original that is
  REPRODUCED here rather than corrected, because the published number is a
  function of it. Fixing it would answer a different question than "does the
  published figure still clear the bar".

That last point is the standing rule of this file: **reproduce the estimator
as it was, including its defects.** Correcting an estimator and re-deflating
in one step makes the two effects inseparable.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import statistics
import tomllib
from collections.abc import Callable
from pathlib import Path

import polars as pl

from martex_quant.backtesting.metrics import (
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from martex_quant.backtesting.multi import MultiBacktestConfig, run_multi_backtest
from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.strategies.rotation import VolTargetRotation

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/tmp/h4x_streams"
BAR = 0.95
REPRODUCTION_TOLERANCE = 0.005
CONFIG = MultiBacktestConfig(initial_cash=10_000.0)


def ledger_total() -> int:
    """Today's total, read from the ledger rather than hardcoded.

    Hardcoding it is how the previous version acquired '120' in its filename
    and then went stale within a day.
    """
    payload = tomllib.loads((ROOT / "docs/research/ledger/trials.toml").read_text("utf-8"))
    return int(payload["ledger_total_claimed"])


def _load_wide_rotation_study():  # noqa: ANN202
    """Import the original study module so its walk-forward stream is ITS
    construction, not a paraphrase of it."""
    spec = importlib.util.spec_from_file_location(
        "wide_rotation_study", ROOT / "scripts/wide_rotation_study.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pp_of(returns: pl.Series) -> float:
    """Per-period Sharpe — the convention every historical DSR site feeds."""
    return (returns.mean() or 0.0) / (returns.std() or 1.0)


def dsr(returns: pl.Series, n_obs: int, n_trials: int, variance: float) -> float:
    skew, kurt = returns.skew(), returns.kurtosis()
    return probabilistic_sharpe_ratio(
        pp_of(returns),
        n_obs=n_obs,
        skew=skew if isinstance(skew, float) else 0.0,
        kurtosis=(kurt + 3.0) if isinstance(kurt, float) else 3.0,
        benchmark_sharpe=expected_max_sharpe(n_trials, variance),
    )


class Reconstruction:
    """One strategy's DSR inputs, rebuilt exactly as its study fed them."""

    def __init__(
        self,
        name: str,
        returns: pl.Series,
        n_obs: int,
        variance: float,
        published_dsr: float,
        published_n: int,
        estimator_note: str,
    ) -> None:
        self.name = name
        self.returns = returns
        self.n_obs = n_obs
        self.variance = variance
        self.published_dsr = published_dsr
        self.published_n = published_n
        self.estimator_note = estimator_note

    @property
    def reproduced(self) -> float:
        return dsr(self.returns, self.n_obs, self.published_n, self.variance)

    @property
    def faithful(self) -> bool:
        return abs(self.reproduced - self.published_dsr) < REPRODUCTION_TOLERANCE


def reconstruct_rotation_stop() -> Reconstruction:
    """H42b, published DSR 0.992 at 104 trials (h41_h42_fub1_studies.py).

    The study joins champion and candidate on timestamp and deflates the
    CANDIDATE over that common window, with variance taken over exactly the
    two per-period Sharpes. Reproduced here line for line.
    """
    rot = pl.read_parquet(CACHE / "rot_champion_stream.parquet")
    rots = pl.read_parquet(CACHE / "rot_stop_stream.parquet")
    to_ret = pl.col("equity").pct_change().fill_null(0.0).alias("ret")
    common = (
        rot.select("timestamp", to_ret)
        .join(rots.select("timestamp", to_ret), on="timestamp", how="inner", suffix="_s")
        .sort("timestamp")
    )
    candidate, champion = common["ret_s"], common["ret"]
    return Reconstruction(
        name="rotation-stop  (DEPLOYED SPEC)",
        returns=candidate,
        n_obs=common.height,
        variance=statistics.variance([pp_of(candidate), pp_of(champion)]),
        published_dsr=0.992,
        published_n=104,
        estimator_note=(
            "common-window inner join; variance over 2 pp-Sharpes "
            "(candidate, champion); fill_null(0.0) keeps the first bar"
        ),
    )


def reconstruct_rotation(lake: ParquetStore, universe: list[str]) -> Reconstruction:
    """H11 wide, published DSR 0.990 at 65 trials (wide_rotation_study.py).

    Deflates the WALK-FORWARD out-of-sample stream. Variance is over the
    per-lookback Sharpes on the GRID, each sliced to the OOS start. The
    study's ``n_obs=oos.height`` off-by-one is reproduced deliberately.
    """
    study = _load_wide_rotation_study()
    frames: dict[str, pl.DataFrame] = {}
    for symbol in universe:
        with contextlib.suppress(FileNotFoundError):
            frames[symbol] = lake.read(symbol, Interval.D1)

    oos = study.wf_stream(frames, 2)
    returns = oos["equity"].pct_change().drop_nulls()
    oos_start = oos["timestamp"][0]

    trial_pp: list[float] = []
    for lookback in study.GRID:
        fixed = run_multi_backtest(
            frames,
            VolTargetRotation(lookback, top_k=2),
            config=CONFIG,
            warmup_bars=max(lookback, 30) + 1,
        )
        sliced = fixed.equity_curve.filter(pl.col("timestamp") >= oos_start)
        trial_pp.append(pp_of(sliced["equity"].pct_change().drop_nulls()))

    return Reconstruction(
        name="rotation",
        returns=returns,
        n_obs=oos.height,  # the study's own off-by-one, reproduced on purpose
        variance=statistics.variance(trial_pp),
        published_dsr=0.990,
        published_n=65,
        estimator_note=(
            f"walk-forward OOS stream; variance over GRID={study.GRID} "
            "Sharpes sliced to OOS start; n_obs=oos.height (off-by-one, kept)"
        ),
    )


def report(item: Reconstruction, total: int) -> bool:
    print(f"\n{item.name}")
    print(f"  sample     : {item.returns.len()} returns, n_obs={item.n_obs} as fed")
    print(f"  estimator  : {item.estimator_note}")
    print(f"  per-period : {pp_of(item.returns):+.5f}   trial variance {item.variance:.6f}")

    drift = abs(item.reproduced - item.published_dsr)
    if not item.faithful:
        print(
            f"  REPRODUCTION FAILED: {item.reproduced:.3f} vs published "
            f"{item.published_dsr:.3f} (drift {drift:.3f})"
        )
        print("  -> no recomputed figure reported for this strategy.")
        return False

    print(
        f"  reproduced @ {item.published_n:>3} trials: {item.reproduced:.4f} "
        f"vs published {item.published_dsr:.3f}  OK (drift {drift:.4f})"
    )
    recomputed = dsr(item.returns, item.n_obs, total, item.variance)
    verdict = "CLEARS" if recomputed >= BAR else "FAILS"
    print(f"  DSR @ {total} trials (today) : {recomputed:.4f}   {verdict} the {BAR} bar")
    print(f"  cost of the ledger growing  : {recomputed - item.published_dsr:+.4f}")
    return True


def main() -> None:
    total = ledger_total()
    lake = ParquetStore(ROOT / "data/lake")
    universe = json.loads((ROOT / "config/universe.json").read_text("utf-8"))["symbols"]

    print(f"DSR re-check at the current ledger total: {total} trials, bar {BAR}")
    print("Published values are NEVER altered; only n_trials changes.\n")

    builders: list[Callable[[], Reconstruction]] = [
        reconstruct_rotation_stop,
        lambda: reconstruct_rotation(lake, universe),
    ]
    faithful = [report(build(), total) for build in builders]

    print("\n" + "=" * 70)
    if not all(faithful):
        print("At least one reproduction FAILED. Those rows report no recomputed")
        print("figure and nothing from them may be quoted.")
    else:
        print("All reproductions faithful. The recomputed figures above are sound.")
    print(
        "\nScope note: this pass covers the two momentum books that are running\n"
        "on paper. H41 (0.995@104) and H43a (1.000@107) are archived own-capital\n"
        "books and are NOT reconstructed here — they are not deployed, and\n"
        "claiming a re-check that was not run would be worse than the gap."
    )


if __name__ == "__main__":
    main()
