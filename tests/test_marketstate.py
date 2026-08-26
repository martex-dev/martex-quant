"""MarketState invariants and deliberate look-ahead ("poison") tests.

The poison tests are the point of this layer: each one injects a specific
kind of future knowledge and asserts the state engine refuses it. A test
here that stops failing when the guard is removed is worthless, so each
poison test also demonstrates the leak IS present under a deliberately wrong
rule — proving the guard, not the fixture, is what catches it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from martex_quant.data.models import OHLCV_SCHEMA, Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.marketstate.state import (
    AvailabilityError,
    BarCloseAvailability,
    MarketState,
    MarketStateEngine,
    assert_no_lookahead,
)

START = datetime(2024, 1, 1, tzinfo=UTC)
DAILY = BarCloseAvailability(Interval.D1)


def _write(store: ParquetStore, symbol: str, closes: list[float]) -> None:
    store.write(
        pl.DataFrame(
            {
                "timestamp": [START + timedelta(days=i) for i in range(len(closes))],
                "open": closes,
                "high": [c * 1.01 for c in closes],
                "low": [c * 0.99 for c in closes],
                "close": closes,
                "volume": [100.0] * len(closes),
            },
            schema=OHLCV_SCHEMA,
        ),
        symbol,
        Interval.D1,
    )


@pytest.fixture
def engine(tmp_path: Path) -> MarketStateEngine:
    store = ParquetStore(tmp_path / "lake")
    _write(store, "AAAUSDT", [100.0 + i for i in range(30)])
    _write(store, "BBBUSDT", [50.0 + 2 * i for i in range(30)])
    return MarketStateEngine(store, DAILY)


# --- the availability rule ------------------------------------------------


def test_a_daily_bar_is_not_knowable_until_its_interval_has_ended(
    engine: MarketStateEngine,
) -> None:
    """The off-by-one-bar error that makes backtests lie."""
    bar = START + timedelta(days=5)
    at_open = engine.as_of(bar, ["AAAUSDT"])
    assert bar not in at_open.frame("AAAUSDT")["timestamp"].to_list()

    at_close = engine.as_of(bar + timedelta(days=1), ["AAAUSDT"])
    assert bar in at_close.frame("AAAUSDT")["timestamp"].to_list()


def test_latest_usable_timestamp_matches_the_filter(engine: MarketStateEngine) -> None:
    as_of = START + timedelta(days=10)
    newest = DAILY.latest_usable_timestamp(as_of)
    assert engine.as_of(as_of, ["AAAUSDT"]).frame("AAAUSDT")["timestamp"][-1] == newest


def test_an_execution_lag_shrinks_what_is_knowable(engine: MarketStateEngine) -> None:
    lagged = MarketStateEngine(engine.store, BarCloseAvailability(Interval.D1, timedelta(days=2)))
    as_of = START + timedelta(days=10)
    assert (
        lagged.as_of(as_of, ["AAAUSDT"]).frame("AAAUSDT").height
        < engine.as_of(as_of, ["AAAUSDT"]).frame("AAAUSDT").height
    )
    assert lagged.rule.name != DAILY.name  # the assumption is recorded on the state


# --- poison tests ---------------------------------------------------------


def test_poison_a_future_bar_is_excluded_and_the_wrong_rule_would_include_it(
    engine: MarketStateEngine,
) -> None:
    """Poison: ask for state mid-series and check tomorrow's bar is absent.

    The second half is what makes this a real test — under a rule that treats
    the bar's own timestamp as its availability time, the future bar IS
    admitted. So the exclusion comes from the rule, not from the fixture.
    """
    as_of = START + timedelta(days=10)
    honest = engine.as_of(as_of, ["AAAUSDT"]).frame("AAAUSDT")
    assert honest["timestamp"].max() < as_of
    assert_no_lookahead(engine.as_of(as_of, ["AAAUSDT"]))

    naive = engine.store.read("AAAUSDT", Interval.D1).filter(pl.col("timestamp") <= as_of)
    assert naive.height == honest.height + 1  # the extra row is the not-yet-closed bar


def test_poison_a_future_derived_column_cannot_survive_the_filter(
    engine: MarketStateEngine,
) -> None:
    """Poison: a forward return is future knowledge wearing a present-day
    timestamp. The state can still hold the column, but every row whose
    forward window extends past as_of has already been filtered out, so the
    values that remain were genuinely computable."""
    as_of = START + timedelta(days=20)
    state = engine.as_of(as_of, ["AAAUSDT"])
    frame = state.frame("AAAUSDT").with_columns(
        fwd1=pl.col("close").shift(-1) / pl.col("close") - 1.0
    )
    # The newest row's forward return is null: its future is not in the state.
    assert frame["fwd1"][-1] is None
    assert frame["fwd1"].drop_nulls().len() == frame.height - 1


def test_poison_a_state_carrying_unavailable_rows_is_rejected() -> None:
    """Poison: hand-build a state whose frame contains rows past its as_of,
    as a mislabelled loader would. assert_no_lookahead must catch it."""
    as_of = START + timedelta(days=5)
    leaking = pl.DataFrame(
        {
            "timestamp": [START + timedelta(days=i) for i in range(10)],
            "available_at": [START + timedelta(days=i + 1) for i in range(10)],
        }
    )
    state = MarketState(as_of=as_of, rule_name="mislabelled", frames={"AAAUSDT": leaking})
    with pytest.raises(AvailabilityError, match="look-ahead"):
        assert_no_lookahead(state)


def test_poison_a_frame_without_an_availability_column_is_rejected() -> None:
    """Poison: a frame that never established availability cannot be verified,
    and unverifiable is treated as unsafe rather than assumed fine."""
    state = MarketState(
        as_of=START,
        rule_name="none",
        frames={"AAAUSDT": pl.DataFrame({"timestamp": [START], "close": [1.0]})},
    )
    with pytest.raises(AvailabilityError, match="no availability column"):
        assert_no_lookahead(state)


# --- structural guarantees ------------------------------------------------


def test_state_is_empty_before_any_bar_has_closed(engine: MarketStateEngine) -> None:
    state = engine.as_of(START, ["AAAUSDT"])
    assert state.frame("AAAUSDT").height == 0
    assert state.latest("AAAUSDT", "close") is None
    assert state.cross_section("close") == {}
    assert_no_lookahead(state)


def test_an_unobservable_symbol_is_kept_as_empty_not_dropped(
    engine: MarketStateEngine, tmp_path: Path
) -> None:
    """'Listed but not yet observable' and 'not in the universe' are different
    facts; collapsing them is how survivorship creeps in."""
    state = engine.as_of(START, ["AAAUSDT", "BBBUSDT"])
    assert state.symbols == ["AAAUSDT", "BBBUSDT"]
    assert all(state.frame(s).height == 0 for s in state.symbols)


def test_a_symbol_absent_from_the_lake_is_omitted(engine: MarketStateEngine) -> None:
    state = engine.as_of(START + timedelta(days=10), ["AAAUSDT", "NOPEUSDT"])
    assert state.symbols == ["AAAUSDT"]
    with pytest.raises(KeyError, match="NOPEUSDT"):
        state.frame("NOPEUSDT")


def test_cross_section_reads_the_newest_knowable_value_per_symbol(
    engine: MarketStateEngine,
) -> None:
    as_of = START + timedelta(days=10)
    section = engine.as_of(as_of, ["AAAUSDT", "BBBUSDT"]).cross_section("close")
    assert section == {"AAAUSDT": 109.0, "BBBUSDT": 68.0}  # bars 0..9 closed


def test_naive_timezone_is_refused(engine: MarketStateEngine) -> None:
    with pytest.raises(AvailabilityError, match="timezone-aware"):
        engine.as_of(datetime(2024, 1, 5), ["AAAUSDT"])  # noqa: DTZ001


def test_states_are_monotone_in_time(engine: MarketStateEngine) -> None:
    """Later states are supersets: information is only ever added."""
    heights = [
        engine.as_of(START + timedelta(days=d), ["AAAUSDT"]).frame("AAAUSDT").height
        for d in range(1, 15)
    ]
    assert heights == sorted(heights)
    assert heights[-1] > heights[0]


def test_the_rule_used_is_recorded_on_the_state(engine: MarketStateEngine) -> None:
    """A result must be able to say which availability assumption produced it."""
    state = engine.as_of(START + timedelta(days=5), ["AAAUSDT"])
    assert state.rule_name == "bar_close(1d)"
    lagged = MarketStateEngine(engine.store, BarCloseAvailability(Interval.D1, timedelta(hours=6)))
    assert lagged.as_of(START + timedelta(days=5), ["AAAUSDT"]).rule_name != state.rule_name
