"""CLI: run the TSLA CNN direction study end to end.

    python -m trading_bot.research.tesla.run --csv data/Tesla/Tasla_Stock_Updated_V2.csv

Every arm sees identical folds, identical inputs and identical scoring, so
differences between them are attributable to the model and nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from trading_bot.research.tesla.dataset import NEUTRAL, Dataset, build_dataset, load_bars
from trading_bot.research.tesla.evaluate import (
    DEFAULT_COST_BPS,
    FoldResult,
    aggregate,
    score_classification,
    score_trading,
)
from trading_bot.research.tesla.model import (
    Classifier,
    CNNClassifier,
    CNNConfig,
    GradientBoostingClassifier,
    LogisticClassifier,
    MajorityClassifier,
)
from trading_bot.research.tesla.splits import Fold, validation_tail, walk_forward_folds

# Keep TensorFlow quiet and deterministic-ish on CPU.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


def make_arms(window: int, n_channels: int, seed: int, arms: list[str]) -> list[Classifier]:
    """Instantiate the requested arms in a fixed order."""
    built: list[Classifier] = []
    for name in arms:
        if name == "majority":
            built.append(MajorityClassifier())
        elif name == "logistic":
            built.append(LogisticClassifier(seed=seed))
        elif name == "gbm":
            built.append(GradientBoostingClassifier(seed=seed))
        elif name == "cnn":
            built.append(CNNClassifier(window, n_channels, CNNConfig(seed=seed)))
        else:
            raise ValueError(f"unknown arm: {name}")
    return built


def run_fold(
    dataset: Dataset,
    fold: Fold,
    tradable: np.ndarray,
    arms: list[str],
    seed: int,
    threshold: float,
    cost_bps: float,
    allow_short: bool,
) -> list[FoldResult]:
    """Fit and score every arm on one fold.

    NEUTRAL samples (neither barrier touched) are dropped from BOTH training
    and scoring: the question asked is "which barrier first", and a bar that
    answered "neither" carries no directional truth to learn from.
    """
    train_idx = fold.train[tradable[fold.train]]
    test_idx = fold.test[tradable[fold.test]]
    if train_idx.size < 100 or test_idx.size < 20:
        raise ValueError(f"fold {fold.index} too small after dropping NEUTRAL samples")

    embargo = dataset.window + dataset.horizon - 1
    fit_idx, val_idx = validation_tail(train_idx, fraction=0.2, embargo=embargo)

    x_fit, y_fit = dataset.x[fit_idx], dataset.y[fit_idx]
    x_val, y_val = dataset.x[val_idx], dataset.y[val_idx]
    x_test, y_test = dataset.x[test_idx], dataset.y[test_idx]

    results: list[FoldResult] = []
    for model in make_arms(dataset.window, dataset.x.shape[2], seed, arms):
        model.fit(x_fit, y_fit, x_val, y_val)
        p_up = model.predict_proba_up(x_test)

        classification = score_classification(y_test, p_up, threshold=threshold)
        trading = score_trading(
            dataset,
            dataset.origin_index[test_idx],
            p_up,
            threshold=threshold,
            cost_bps=cost_bps,
            allow_short=allow_short,
        )
        extra: dict[str, float] = {}
        if isinstance(model, CNNClassifier):
            extra = {
                "parameters": float(model.n_parameters()),
                "epochs": float(model.epochs_run),
                "train_rows": float(x_fit.shape[0]),
            }
        results.append(
            FoldResult(
                fold=fold.index,
                arm=model.name,
                classification=classification,
                trading=trading,
                extra=extra,
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TSLA CNN direction study")
    parser.add_argument("--csv", type=Path, default=Path("data/Tesla/Tasla_Stock_Updated_V2.csv"))
    parser.add_argument("--window", type=int, default=30, help="bars of history per sample")
    parser.add_argument("--horizon", type=int, default=5, help="trading days to resolve the label")
    parser.add_argument(
        "--k-sigma", type=float, default=1.0, help="barrier width in trailing sigma"
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--min-train", type=int, default=500)
    parser.add_argument("--threshold", type=float, default=0.55)
    parser.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    parser.add_argument("--long-only", action="store_true", help="disallow short positions")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--arms",
        nargs="+",
        default=["majority", "logistic", "gbm", "cnn"],
        help="which models to run",
    )
    parser.add_argument("--out", type=Path, default=None, help="write results JSON here")
    args = parser.parse_args(argv)

    bars = load_bars(args.csv)
    dataset = build_dataset(bars, window=args.window, horizon=args.horizon, k_sigma=args.k_sigma)
    tradable = dataset.tradable
    embargo = dataset.window + dataset.horizon - 1

    print(f"bars      : {len(bars)}  {bars.dates[0]} -> {bars.dates[-1]}")
    print(f"samples   : {len(dataset)} (window={args.window}, horizon={args.horizon})")
    counts = np.bincount(dataset.y, minlength=3)
    print(
        f"labels    : UP {counts[1]}  DOWN {counts[0]}  NEUTRAL {counts[NEUTRAL]} "
        f"(k_sigma={args.k_sigma})"
    )
    print(
        f"tradable  : {int(tradable.sum())}  base rate UP "
        f"{float(np.mean(dataset.y[tradable] == 1)):.3f}"
    )
    print(f"embargo   : {embargo} samples purged around every test block\n")

    folds = walk_forward_folds(
        n_samples=len(dataset), n_folds=args.folds, embargo=embargo, min_train=args.min_train
    )

    results: list[FoldResult] = []
    for fold in folds:
        first, last = dataset.dates[fold.test[0]], dataset.dates[fold.test[-1]]
        print(f"fold {fold.index}: test {first} -> {last} ({fold.test.size} samples)")
        fold_results = run_fold(
            dataset,
            fold,
            tradable,
            args.arms,
            args.seed,
            args.threshold,
            args.cost_bps,
            allow_short=not args.long_only,
        )
        for r in fold_results:
            c, t = r.classification, r.trading
            print(
                f"  {r.arm:9s} auc {c.auc:.3f}  acc {c.accuracy:.3f}  "
                f"prec@{c.threshold:.2f} {c.precision:.3f} (cov {c.coverage:.2f})  "
                f"trades {t.n_trades:3d}  net {t.net_mean_bps:+7.1f}bp  t {t.t_stat:+.2f}"
            )
        results.extend(fold_results)
        print()

    print("=" * 78)
    print("POOLED ACROSS FOLDS")
    print("=" * 78)
    summary: dict[str, dict[str, float]] = {}
    for arm in args.arms:
        stats = aggregate(results, arm)
        summary[arm] = stats
        print(
            f"{arm:9s} mean AUC {stats['mean_auc']:.4f} (min {stats['min_auc']:.3f}, "
            f"{int(stats['folds_auc_above_half'])}/{int(stats['folds'])} folds > 0.5)  "
            f"acc {stats['mean_accuracy']:.3f} vs base {stats['mean_base_rate']:.3f}  "
            f"trades {int(stats['total_trades'])}  net {stats['net_mean_bps']:+.1f}bp/trade  "
            f"{int(stats['folds_net_positive'])}/{int(stats['folds'])} folds net positive"
        )

    if args.out is not None:
        payload = {
            "config": vars(args) | {"csv": str(args.csv), "out": str(args.out)},
            "summary": summary,
            "folds": [asdict(r) for r in results],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
