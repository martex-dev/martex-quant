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


class VolTargetRotation(MultiAssetStrategy):
    """DualMomentumRotation with the hyp-06 cure: the selected basket's
    weights are scaled by min(1, target_vol / realized basket vol) so the
    book runs a constant risk budget instead of constant notional."""

    def __init__(
        self,
        lookback: int,
        top_k: int = 2,
        target_vol_annual: float = 0.30,
        vol_window: int = 30,
    ) -> None:
        self._base = DualMomentumRotation(lookback, top_k)
        if not 0.0 < target_vol_annual <= 2.0:
            raise ValueError("target_vol_annual must be in (0, 2]")
        if vol_window < 5:
            raise ValueError("vol_window must be >= 5")
        self.lookback = lookback
        self.top_k = top_k
        self.target_vol_annual = target_vol_annual
        self.vol_window = vol_window

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        import math
        from statistics import mean, stdev

        base = self._base.target_weights(histories)
        if not base:
            return {}
        # Realized vol of the equal-weight basket of SELECTED symbols.
        per_day: list[list[float]] = []
        for symbol in base:
            history = histories[symbol]
            window = history.window(self.vol_window + 1)
            if len(window) < self.vol_window + 1:
                return {}  # not enough history to size responsibly: stay out
            closes = [bar.close for bar in window]
            per_day.append([closes[i + 1] / closes[i] - 1.0 for i in range(len(closes) - 1)])
        basket = [mean(day) for day in zip(*per_day, strict=True)]
        realized = stdev(basket) * math.sqrt(365)
        scale = 1.0 if realized <= 0 else min(1.0, self.target_vol_annual / realized)
        return {s: w * scale for s, w in base.items()}
