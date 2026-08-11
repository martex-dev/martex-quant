"""H58 kill test: does LEARNING indicator weights beat equal weighting?

    .venv/Scripts/python scripts/h58_ensemble_study.py

Pre-registered in docs/hypotheses/58-learned-indicator-ensemble.md, committed
before this ran. 5 declared cells (B, C, D1, D2, E); the individual
indicators are references, not trials, as in H24-H32.

The decisive bar is C > B. The claim is specifically that LEARNING the
weights helps, so if learned weights do not beat equal weights the hypothesis
is false as stated regardless of how any single model scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from trading_bot.data.store.parquet_store import ParquetStore
from trading_bot.features.panel import (
    daily_panel,
    forward_return,
    momentum,
    rolling_mean_close,
    rolling_mean_volume,
    up_day_share,
    vol_excl_current,
)
from trading_bot.research.ensemble import (
    LeakageError,
    assert_features_are_causal,
    leak_alarm,
    run_walk_forward,
)
from trading_bot.research.relationships import Cell, Condition, measure_cell

FEATURES = ["r30", "r90", "vol30", "ma90_dev", "v_ratio", "upshare90"]
TARGET, OUTCOME = "target", "fwd7"
TRAIN, TEST, PURGE = 730, 180, 7  # 2y train, 6m test, 7d purge = the horizon
SEEDS = {"B": 5801, "C": 5802, "D1": 5803, "D2": 5804, "E": 5805}


def build_panel(store: ParquetStore, universe: list[str]) -> pl.DataFrame:
    panel = daily_panel(
        store,
        universe,
        base_columns=("close", "volume", "ret"),
        feature_stages=[
            [
                momentum(30),
                momentum(90),
                vol_excl_current(30, name="vol30"),
                rolling_mean_close(90, name="ma90"),
                rolling_mean_volume(7, name="v7"),
                rolling_mean_volume(30, name="v30"),
                up_day_share(90, name="upshare90"),
                forward_return(7),
            ],
        ],
        on_missing_symbol="skip",
    )
    return panel.with_columns(
        ma90_dev=pl.col("close") / pl.col("ma90") - 1.0,
        v_ratio=pl.col("v7") / pl.col("v30"),
        target=(pl.col("fwd7") > 0).cast(pl.Int8),
    )


def evaluate(run, panel_days: int) -> dict[str, float]:  # noqa: ANN001
    """Out-of-sample accuracy, and the forward-return spread when the model
    says 'enter' versus when it does not — measured with the same day-block
    bootstrap every kill test in this corpus uses."""
    predictions = run.predictions
    if predictions.is_empty():
        return {
            "accuracy": float("nan"),
            "spread": float("nan"),
            "lo": float("nan"),
            "hi": float("nan"),
        }
    cell = Cell(
        condition=Condition("model says enter", pl.col("prob") > 0.5),
        outcome=OUTCOME,
        horizon=7,
        seed=SEEDS.get(run.name, 5800),
    )
    result = measure_cell(predictions, cell)
    return {
        "accuracy": run.accuracy,
        "spread": result.effect,
        "lo": result.ci_low,
        "hi": result.ci_high,
        "n": float(result.n_a),
        "significant": float(result.ci_excludes_zero),
    }


def show(label: str, metrics: dict[str, float], windows: int) -> None:
    sig = "SIGNAL" if metrics.get("significant") else "noise"
    print(
        f"  {label:<28} acc {metrics['accuracy']:.4f}  "
        f"fwd7 spread {metrics['spread']:+.3%}  "
        f"CI [{metrics['lo']:+.3%}, {metrics['hi']:+.3%}]  {sig:<6} "
        f"({windows} windows)"
    )


def main() -> None:
    store = ParquetStore(Path("data/lake"))
    universe = json.loads(Path("config/universe.json").read_text(encoding="utf-8"))["symbols"]
    panel = build_panel(store, universe)
    n_days = panel["day"].n_unique()
    print(f"H58 panel: {panel.height} symbol-days over {n_days} dates\n")

    # --- the poison test must pass before any result is admissible ---
    print("=== POISON TEST: a forward-derived column must be refused ===")
    try:
        assert_features_are_causal([*FEATURES, "fwd7"])
        print("  FAILED — the harness accepted fwd7 as a predictor. Results inadmissible.")
        return
    except LeakageError as exc:
        print(f"  caught: {str(exc)[:96]}...")
    flagged = leak_alarm(panel, [*FEATURES, "fwd7"], OUTCOME)
    print(f"  leak alarm on the poisoned set: {flagged or 'NOTHING FLAGGED — harness is blind'}")
    if not flagged:
        print("  Results inadmissible.")
        return
    print(
        f"  leak alarm on the declared features: {leak_alarm(panel, FEATURES, TARGET) or 'clean'}\n"
    )

    runs = {}
    print("=== references (NOT trials): each indicator alone ===")
    for feature in FEATURES:
        run = run_walk_forward(
            panel,
            name=f"A:{feature}",
            features=[feature],
            target=TARGET,
            outcome=OUTCOME,
            train=TRAIN,
            test=TEST,
            purge=PURGE,
            penalty="none",
        )
        show(f"A: {feature} alone", evaluate(run, n_days), run.n_windows)

    print("\n=== declared cells ===")
    specs = [
        ("B", "B: equal-weighted", "none", True),
        ("C", "C: learned weights", "none", False),
        ("D1", "D1: learned + L2", "l2", False),
        ("D2", "D2: learned + L1", "l1", False),
    ]
    for key, label, penalty, equal in specs:
        run = run_walk_forward(
            panel,
            name=key,
            features=FEATURES,
            target=TARGET,
            outcome=OUTCOME,
            train=TRAIN,
            test=TEST,
            purge=PURGE,
            penalty=penalty,  # type: ignore[arg-type]
            equal_weight=equal,
            seed=SEEDS[key],
        )
        runs[key] = (run, evaluate(run, n_days))
        show(label, runs[key][1], run.n_windows)

    # E is the rolling retrain: a shorter train window that re-fits more often.
    run_e = run_walk_forward(
        panel,
        name="E",
        features=FEATURES,
        target=TARGET,
        outcome=OUTCOME,
        train=365,
        test=90,
        purge=PURGE,
        penalty="l2",
        seed=SEEDS["E"],
    )
    runs["E"] = (run_e, evaluate(run_e, n_days))
    show("E: rolling retrain (1y/3m)", runs["E"][1], run_e.n_windows)

    # --- the decisive bar ---
    print("\n=== VERDICT BARS (pre-registered) ===")
    b_acc, c_acc = runs["B"][1]["accuracy"], runs["C"][1]["accuracy"]
    beats = c_acc > b_acc
    print(f"  BAR 1 — C must beat B: {c_acc:.4f} vs {b_acc:.4f} -> {'PASS' if beats else 'FAIL'}")

    stability = runs["C"][0].sign_stability()
    stable = sum(1 for v in stability.values() if v >= 2 / 3)
    print(f"  BAR 2 — weight sign stability >=2/3 of windows: {stable}/{len(FEATURES)} features")
    for feature, share in sorted(stability.items(), key=lambda kv: -kv[1]):
        mean_w = runs["C"][0].mean_weights()[feature]
        print(f"      {feature:<12} mean weight {mean_w:+.4f}   sign stable {share:.0%}")

    print("  BAR 3 — ablation: drop the highest-|weight| indicator")
    top = max(runs["C"][0].mean_weights().items(), key=lambda kv: abs(kv[1]))[0]
    reduced = [f for f in FEATURES if f != top]
    ablated = run_walk_forward(
        panel,
        name="ablation",
        features=reduced,
        target=TARGET,
        outcome=OUTCOME,
        train=TRAIN,
        test=TEST,
        purge=PURGE,
        penalty="none",
        seed=5806,
    )
    ab = evaluate(ablated, n_days)
    print(
        f"      dropping '{top}': acc {ab['accuracy']:.4f} vs full {c_acc:.4f} "
        f"({'degrades' if ab['accuracy'] < c_acc else 'NO degradation — not used'})"
    )

    any_signal = any(m.get("significant") for _, m in runs.values())
    print(
        f"\nVERDICT: bar1 {'PASS' if beats else 'FAIL'}; "
        f"any cell with CI clear of zero: {'yes' if any_signal else 'NO'} -> "
        f"{'proceed to write up' if beats and any_signal else 'H58 KILLED at the info stage'}"
    )


if __name__ == "__main__":
    main()
