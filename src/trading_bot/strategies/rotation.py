"""Dual-momentum rotation. Spec: docs/hypotheses/11-cross-sectional-rotation.md."""

from __future__ import annotations

from trading_bot.backtesting.history import History
from trading_bot.backtesting.multi import MultiAssetStrategy


class DualMomentumRotation(MultiAssetStrategy):
    """Hold the top-K symbols by trailing L-day return, equal-weight — but
    only slots whose trailing return is POSITIVE (absolute-momentum gate);
    gated-out slots stay in cash. Long-only, stateless."""

    def __init__(self, lookback: int, top_k: int = 2) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        self.lookback = lookback
        self.top_k = top_k

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for symbol, history in histories.items():
            if len(history) > self.lookback:
                past = history[-1 - self.lookback].close
                scores[symbol] = history.current.close / past - 1.0
        ranked = sorted(scores, key=lambda s: scores[s], reverse=True)[: self.top_k]
        return {s: 1.0 / self.top_k for s in ranked if scores[s] > 0.0}
