"""Unit tests for BlendMomentum (H33/FU-B1) and the stop overlays (H42)."""

from datetime import UTC, datetime, timedelta

from trading_bot.backtesting.history import History
from trading_bot.core.events import Bar
from trading_bot.strategies.blend import BlendMomentum
from trading_bot.strategies.stops import StopVolTargetMomentum, update_stop

START = datetime(2024, 1, 1, tzinfo=UTC)


def make_history(closes: list[float], advance_all: bool = True) -> History:
    bars = [
        Bar(START + timedelta(days=i), c, c * 1.01, c * 0.99, c, 100.0)
        for i, c in enumerate(closes)
    ]
    history = History(bars)
    if advance_all:
        for _ in bars:
            history.advance()
    return history


def test_blend_flat_below_warmup() -> None:
    history = make_history([100.0] * 50)
    assert BlendMomentum().on_bar(history) == 0.0


def test_blend_full_score_in_steady_uptrend() -> None:
    closes = [100.0 * 1.002**i for i in range(200)]
    exposure = BlendMomentum().on_bar(make_history(closes))
    # All three horizons positive; low vol -> capped scale. Full exposure.
    assert exposure == 1.0


def test_blend_partial_score() -> None:
    # Long downtrend, mild rally in the last 35 days: r30 > 0 but the
    # 90d and 180d horizons stay negative -> score 1/3 (0.35 quantized).
    closes = [300.0 - i for i in range(165)] + [135.0 + 1.5 * i for i in range(35)]
    exposure = BlendMomentum().on_bar(make_history(closes))
    assert 0.0 < exposure <= 0.35


def test_blend_flat_when_all_horizons_negative() -> None:
    closes = [400.0 - i for i in range(200)]
    assert BlendMomentum().on_bar(make_history(closes)) == 0.0


def test_stop_fires_after_sharp_drop_and_clears_on_new_high() -> None:
    # Calm rise to 130, then a plunge far beyond 2 x ATR14.
    closes = [100.0 + i for i in range(31)] + [110.0]
    history = make_history(closes)
    assert update_stop(history, False) is True
    # While price stays below the rolling 30d high, the latch holds.
    closes2 = closes + [112.0]
    assert update_stop(make_history(closes2), True) is True
    # A new 30d close-high clears it.
    closes3 = closes + [131.0]
    assert update_stop(make_history(closes3), True) is False


def test_stop_not_stopped_with_short_history() -> None:
    assert update_stop(make_history([100.0] * 10), False) is False


def test_stop_momentum_flat_while_stopped() -> None:
    # Uptrend then crash: base momentum (short lookback) may flip positive
    # on a dead-cat bounce, but the stop must hold the strategy flat.
    closes = [100.0 + i for i in range(60)] + [140.0, 141.0, 142.0]
    strategy = StopVolTargetMomentum(lookback=7)
    history = make_history(closes[:61], advance_all=True)
    assert strategy.on_bar(history) == 0.0  # drop from 159 to 140: stopped
    assert strategy._stopped is True
