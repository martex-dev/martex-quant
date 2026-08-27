"""Cross-venue premium ladder. Spec: docs/hypotheses/69-cross-venue-premium-strategy.md."""

from __future__ import annotations

import datetime as dt

from martex_quant.backtesting.history import History
from martex_quant.backtesting.multi import MultiAssetStrategy


class CrossVenuePremiumLadder(MultiAssetStrategy):
    """Hold symbols whose peg-adjusted venue premium is in the top decile
    of its own trailing window, equal-weight, through a ``hold``-day
    tranche ladder.

    Capital is split into ``hold`` equal tranches. On day *t* the tranche
    entered on day *e* holds that day's qualifying symbols at weight
    ``(1/hold) / n_qualifiers(e)``, for ``hold`` days. A tranche whose
    entry day had no qualifier sits in cash.

    Exactly ``hold`` entry days are live at any time — *t*, *t-1*, ...,
    *t-hold+1* — and each belongs to a distinct tranche, so the book is a
    pure function of the last ``hold`` qualifier sets and carries no
    hidden state. That matters for a research engine: replaying the same
    dates always produces the same weights.

    The qualifier sets are precomputed from data available strictly at or
    before their own date (a trailing percentile rank), so passing them in
    is not look-ahead. The strategy never sees a future bar; it is handed
    a lookup table keyed by the date whose close produced it.

    Long-only, no leverage, weights sum to at most 1.
    """

    def __init__(
        self,
        qualifiers: dict[dt.date, tuple[str, ...]],
        hold: int,
    ) -> None:
        if hold < 1:
            raise ValueError("hold must be >= 1")
        self.qualifiers = qualifiers
        self.hold = hold

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        if not histories:
            return {}
        # The engine does not pass the clock, so take it from the newest
        # closed bar. A symbol whose newest closed bar is older than that
        # did not trade today and must not be sized off a stale print.
        today = max(h.current.timestamp for h in histories.values()).date()
        tradeable = {s for s, h in histories.items() if h.current.timestamp.date() == today}

        weights: dict[str, float] = {}
        tranche = 1.0 / self.hold
        for age in range(self.hold):
            entry = today - dt.timedelta(days=age)
            names = self.qualifiers.get(entry, ())
            live = [s for s in names if s in tradeable]
            if not live:
                continue  # this tranche is in cash
            # Weight is set by the qualifier count on the ENTRY day, not by
            # how many are tradeable now: a name that stops trading frees
            # its slot to cash rather than silently concentrating the book.
            per_name = tranche / len(names)
            for symbol in live:
                weights[symbol] = weights.get(symbol, 0.0) + per_name
        return weights


class EqualWeightBuyAndHold(MultiAssetStrategy):
    """Equal weight across every symbol that has started trading.

    The Gate B benchmark: it answers "was the timing worth anything, or
    is this just owning the basket?" Union mode — a symbol joins the book
    once it has a bar — so it is comparable to a strategy that could only
    ever have traded what existed at the time.
    """

    def target_weights(self, histories: dict[str, History]) -> dict[str, float]:
        if not histories:
            return {}
        today = max(h.current.timestamp for h in histories.values()).date()
        live = [s for s, h in histories.items() if h.current.timestamp.date() == today]
        if not live:
            return {}
        return {s: 1.0 / len(live) for s in live}
