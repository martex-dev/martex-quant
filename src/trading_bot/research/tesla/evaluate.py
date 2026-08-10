"""Scoring — statistical first, then the only test that pays: net of costs.

Accuracy alone is close to useless here. A stock with an upward drift can
be "predicted" at 55% by always saying up, and a model can be right 55% of
the time on moves too small to cover the spread. So every arm is scored on
three levels:

1. **Discrimination** — ROC AUC on tradable samples. 0.50 is coin-flipping.
2. **Selectivity** — precision and coverage at a confidence threshold. A
   model that is 60% right on the 10% of days it feels strongly about is
   more useful than one that is 52% right every day.
3. **Economics** — a return series from acting on the signal, net of a
   round-trip cost, with a t-statistic. This is where most published
   direction models quietly die.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

import numpy as np
import numpy.typing as npt

from trading_bot.research.tesla.dataset import Dataset

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

# Round-trip cost in basis points. TSLA is one of the most liquid names on
# US markets and retail commission is typically zero, so this is spread
# plus a slippage allowance, not a commission schedule.
DEFAULT_COST_BPS = 10.0


@dataclass
class ClassificationScore:
    """Discrimination and selectivity for one arm on one test block."""

    n: int
    base_rate: float
    accuracy: float
    auc: float
    threshold: float
    coverage: float
    precision: float


@dataclass
class TradingScore:
    """Economics of acting on the signal over one test block."""

    n_trades: int
    gross_mean_bps: float
    net_mean_bps: float
    net_total_pct: float
    hit_rate: float
    t_stat: float


@dataclass
class FoldResult:
    """Everything one arm produced on one fold."""

    fold: int
    arm: str
    classification: ClassificationScore
    trading: TradingScore
    extra: dict[str, float] = field(default_factory=dict)


def roc_auc(y_true: IntArray, scores: FloatArray) -> float:
    """AUC via the rank identity; returns NaN if only one class is present."""
    pos = int(np.sum(y_true == 1))
    neg = int(np.sum(y_true == 0))
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(scores.size, dtype=np.float64)
    ranks[order] = np.arange(1, scores.size + 1, dtype=np.float64)

    # Average ranks within ties, otherwise a constant predictor scores != 0.5.
    sorted_scores = scores[order]
    start = 0
    for i in range(1, scores.size + 1):
        if i == scores.size or sorted_scores[i] != sorted_scores[start]:
            if i - start > 1:
                ranks[order[start:i]] = float(np.mean(ranks[order[start:i]]))
            start = i

    rank_sum = float(np.sum(ranks[y_true == 1]))
    return (rank_sum - pos * (pos + 1) / 2.0) / (pos * neg)


def score_classification(
    y_true: IntArray, p_up: FloatArray, threshold: float = 0.55
) -> ClassificationScore:
    """Discrimination plus precision on the high-confidence subset.

    ``threshold`` is symmetric: we count a call whenever ``p_up`` is above
    it or below ``1 - threshold``, and score whether that call was right.
    """
    n = int(y_true.size)
    if n == 0:
        return ClassificationScore(
            0, float("nan"), float("nan"), float("nan"), threshold, 0.0, float("nan")
        )

    predicted_up = p_up >= 0.5
    accuracy = float(np.mean(predicted_up == (y_true == 1)))

    confident = (p_up >= threshold) | (p_up <= 1.0 - threshold)
    coverage = float(np.mean(confident))
    if bool(confident.any()):
        precision = float(np.mean(predicted_up[confident] == (y_true[confident] == 1)))
    else:
        precision = float("nan")

    return ClassificationScore(
        n=n,
        base_rate=float(np.mean(y_true == 1)),
        accuracy=accuracy,
        auc=roc_auc(y_true, p_up),
        threshold=threshold,
        coverage=coverage,
        precision=precision,
    )


def forward_returns(dataset: Dataset, origins: IntArray) -> FloatArray:
    """Open-to-open log return earned by acting on a signal at ``origin``.

    The signal is produced at the close of day ``t``; the earliest tradable
    price is the next day's open. The position is held ``horizon`` days and
    exits at an open as well. Using closes for entry would be a look-ahead
    of exactly one bar — small, and enough to flip a marginal result.
    """
    bars = dataset.bars
    horizon = dataset.horizon
    n_bars = len(bars)
    out = np.full(origins.size, np.nan, dtype=np.float64)
    for i, t in enumerate(origins):
        entry_idx = int(t) + 1
        exit_idx = entry_idx + horizon
        if exit_idx >= n_bars:
            continue
        out[i] = float(np.log(bars.open[exit_idx] / bars.open[entry_idx]))
    return out


def score_trading(
    dataset: Dataset,
    origins: IntArray,
    p_up: FloatArray,
    threshold: float = 0.55,
    cost_bps: float = DEFAULT_COST_BPS,
    allow_short: bool = True,
) -> TradingScore:
    """Turn probabilities into positions and charge the toll.

    Rule: go long when ``p_up >= threshold``, short when
    ``p_up <= 1 - threshold`` (if shorting is allowed), otherwise stand
    aside. Every taken trade pays ``cost_bps`` round trip.
    """
    gross = forward_returns(dataset, origins)
    valid = np.isfinite(gross)

    direction = np.zeros(p_up.size, dtype=np.float64)
    direction[p_up >= threshold] = 1.0
    if allow_short:
        direction[p_up <= 1.0 - threshold] = -1.0

    taken = valid & (direction != 0.0)
    n_trades = int(np.sum(taken))
    if n_trades == 0:
        return TradingScore(0, float("nan"), float("nan"), 0.0, float("nan"), float("nan"))

    trade_gross = direction[taken] * gross[taken]
    trade_net = trade_gross - cost_bps * 1e-4

    net_mean = float(np.mean(trade_net))
    net_std = float(np.std(trade_net, ddof=1)) if n_trades > 1 else float("nan")
    t_stat = net_mean / (net_std / sqrt(n_trades)) if net_std and net_std > 0 else float("nan")

    return TradingScore(
        n_trades=n_trades,
        gross_mean_bps=float(np.mean(trade_gross)) * 1e4,
        net_mean_bps=net_mean * 1e4,
        net_total_pct=float(np.expm1(np.sum(trade_net))) * 100.0,
        hit_rate=float(np.mean(trade_gross > 0.0)),
        t_stat=float(t_stat),
    )


def aggregate(results: list[FoldResult], arm: str) -> dict[str, float]:
    """Pool one arm's folds into headline numbers.

    Per-fold AUCs are averaged; trade statistics are pooled by trade count
    so that a fold with three trades cannot outvote a fold with two hundred.
    """
    rows = [r for r in results if r.arm == arm]
    if not rows:
        return {}

    aucs = np.asarray([r.classification.auc for r in rows], dtype=np.float64)
    finite_auc = aucs[np.isfinite(aucs)]
    trades = np.asarray([r.trading.n_trades for r in rows], dtype=np.float64)
    net = np.asarray([r.trading.net_mean_bps for r in rows], dtype=np.float64)
    weighted_net = (
        float(np.nansum(net * trades) / trades.sum()) if trades.sum() > 0 else float("nan")
    )

    return {
        "folds": float(len(rows)),
        "mean_auc": float(np.mean(finite_auc)) if finite_auc.size else float("nan"),
        "min_auc": float(np.min(finite_auc)) if finite_auc.size else float("nan"),
        "folds_auc_above_half": float(np.sum(finite_auc > 0.5)),
        "mean_accuracy": float(np.mean([r.classification.accuracy for r in rows])),
        "mean_base_rate": float(np.mean([r.classification.base_rate for r in rows])),
        "total_trades": float(trades.sum()),
        "net_mean_bps": weighted_net,
        "folds_net_positive": float(np.sum(net > 0.0)),
    }
