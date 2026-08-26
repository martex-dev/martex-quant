"""The History view: the only window a strategy has onto market data.

It wraps the full bar sequence but exposes bars only up to an internal cursor
that the engine advances. There is no API to read past the cursor, so a
strategy cannot express look-ahead even deliberately — indexing beyond the
newest closed bar raises IndexError.
"""

from __future__ import annotations

from collections.abc import Sequence

from martex_quant.core.events import Bar


class History:
    def __init__(self, bars: Sequence[Bar]) -> None:
        self._bars = bars
        self._cursor = -1  # index of the newest CLOSED bar; -1 = nothing yet

    def advance(self) -> None:
        """Engine-only: mark the next bar as closed. Strategies never call this."""
        if self._cursor + 1 >= len(self._bars):
            raise IndexError("cannot advance past the end of the data")
        self._cursor += 1

    def __len__(self) -> int:
        return self._cursor + 1

    def __getitem__(self, index: int) -> Bar:
        """Bars indexed over the CLOSED range only: 0 .. len(self)-1.

        Negative indices count back from the newest closed bar, so ``[-1]``
        is always "now" and can never be a future bar.
        """
        n = len(self)
        if index < 0:
            index += n
        if not 0 <= index < n:
            raise IndexError(f"bar index {index} outside closed range [0, {n})")
        return self._bars[index]

    @property
    def current(self) -> Bar:
        return self[-1]

    def window(self, n: int) -> Sequence[Bar]:
        """The last ``n`` closed bars (fewer near the start of the data)."""
        if n <= 0:
            raise ValueError("window size must be positive")
        return self._bars[max(0, len(self) - n) : len(self)]

    def closes(self, n: int) -> list[float]:
        return [bar.close for bar in self.window(n)]
