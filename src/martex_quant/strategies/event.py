"""Event-driven strategies. Hypothesis 22: crash-day alt bounce."""

from __future__ import annotations

from martex_quant.backtesting.history import History
from martex_quant.backtesting.multi import MultiAssetStrategy


class CrashBounce(MultiAssetStrategy):
    """Equal-weight long ALL listed alts for the day after a BTC crash day
    (BTC daily return below ``threshold``); flat otherwise.

    Zero tunable parameters by design — the -3% threshold was fixed in
    hypothesis 19's pre-registration, before any strategy existed.
    Consecutive crash days simply keep the position on.
    """

    def __init__(self, btc_symbol: str = "BTCUSDT", threshold: float = -0.03) -> None:
        if threshold >= 0:
            raise ValueError("threshold must be negative")
        self.btc_symbol = btc_symbol
        self.threshold = threshold

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        btc = histories.get(self.btc_symbol)
        if btc is None or len(btc) < 2:
            return {}
        ret = btc.current.close / btc[-2].close - 1.0
        if ret >= self.threshold:
            return {}
        alts = [s for s in histories if s != self.btc_symbol]
        if not alts:
            return {}
        return {s: 1.0 / len(alts) for s in alts}
