"""Paper trader tests with a fake collector — no network, deterministic."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from trading_bot.data.models import Interval, ohlcv_frame_from_rows
from trading_bot.live.paper import SYMBOLS, PaperTrader

DAY_MS = 86_400_000
T0 = datetime(2024, 1, 1, tzinfo=UTC)


class FakeDailyCollector:
    """Serves a deterministic uptrend so momentum strategies go long."""

    def __init__(self, n_days: int = 560) -> None:
        start_ms = int(T0.timestamp() * 1000)
        self.n_days = n_days
        rows = []
        price = 100.0
        for i in range(n_days):
            close = price * 1.002  # steady +0.2%/day, low vol
            rows.append([start_ms + i * DAY_MS, price, close * 1.001, price * 0.999, close, 1e6])
            price = close
        self.df = ohlcv_frame_from_rows(rows)

    def fetch_ohlcv(
        self, symbol: str, interval: Interval, start: datetime, end: datetime
    ) -> pl.DataFrame:
        return self.df.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))


def make_trader(tmp_path: Path) -> tuple[PaperTrader, datetime]:
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "vol-target", tmp_path / "paper", collector=FakeDailyCollector(), initial_cash=5_000.0
    )
    return trader, now


def test_first_run_selects_params_and_goes_long(tmp_path: Path) -> None:
    trader, now = make_trader(tmp_path)
    mark = trader.run_once(now=now)

    assert set(trader.state["params"]) == set(SYMBOLS)
    assert mark["n_fills"] == len(SYMBOLS)  # entered every symbol
    # Steady uptrend, low vol -> full exposure everywhere
    assert all(e > 0.9 for e in mark["exposures"].values())
    assert mark["equity"] < 5_000.0  # entry costs paid
    assert mark["equity"] > 4_990.0  # ...but only costs


def test_state_persists_and_second_run_is_stable(tmp_path: Path) -> None:
    trader, now = make_trader(tmp_path)
    trader.run_once(now=now)

    # Fresh instance from the same directory: state must reload.
    reloaded = PaperTrader(
        "vol-target", tmp_path / "paper", collector=FakeDailyCollector(), initial_cash=5_000.0
    )
    assert reloaded.state["positions"]
    mark2 = reloaded.run_once(now=now + timedelta(days=1))
    # Same signal, position already on: no churn.
    assert mark2["n_fills"] == 0
    # No reselection within 90 days:
    assert reloaded.state["last_reselect"] == trader.state["last_reselect"]


def test_journal_and_equity_files_written(tmp_path: Path) -> None:
    trader, now = make_trader(tmp_path)
    trader.run_once(now=now)

    journal = (tmp_path / "paper" / "journal.jsonl").read_text(encoding="utf-8").strip()
    fills = [json.loads(line) for line in journal.splitlines()]
    assert len(fills) == len(SYMBOLS)
    assert all(f["side"] == "buy" and f["fee"] > 0 for f in fills)

    equity_lines = (tmp_path / "paper" / "equity.jsonl").read_text(encoding="utf-8").strip()
    assert len(equity_lines.splitlines()) == 1


def test_reselect_after_90_days(tmp_path: Path) -> None:
    trader, now = make_trader(tmp_path)
    trader.run_once(now=now)
    first = trader.state["last_reselect"]
    trader.run_once(now=now + timedelta(days=91))
    assert trader.state["last_reselect"] != first


def test_rotation_paper_trader_end_to_end(tmp_path: Path) -> None:
    """Cross-sectional path: selects a lookback, holds top-2 as fractions of
    TOTAL equity, journals fills."""
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "rotation",
        tmp_path / "paper",
        collector=FakeDailyCollector(),
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark = trader.run_once(now=now)

    assert set(trader.state["params"]) == {"lookback"}
    fractions = mark["exposures"]
    invested = {s: f for s, f in fractions.items() if f > 0}
    assert len(invested) == 2  # top-2 slots
    assert sum(invested.values()) == pytest.approx(1.0, abs=0.05)  # low-vol -> full budget
    assert mark["n_fills"] == 2
    # Second run same day: no churn.
    mark2 = trader.run_once(now=now + timedelta(days=1))
    assert mark2["n_fills"] == 0


def test_daily_story_written_and_honest(tmp_path: Path) -> None:
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "vol-target", tmp_path / "p1", collector=FakeDailyCollector(), initial_cash=5_000.0
    )
    mark = trader.run_once(now=now)
    story = mark["story"]
    assert "Rising and held" in story  # uptrend fake data -> in the market
    assert "Trades today: bought" in story

    rot = PaperTrader(
        "rotation",
        tmp_path / "p2",
        collector=FakeDailyCollector(),
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark2 = rot.run_once(now=now)
    assert "ranked all" in mark2["story"]
    assert "holds the strongest" in mark2["story"]


def test_combined_paper_trader_blends_both_sleeves(tmp_path: Path) -> None:
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "combined",
        tmp_path / "paper",
        collector=FakeDailyCollector(),
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark = trader.run_once(now=now)

    assert set(trader.state["params"]) == {"per_symbol", "lookback"}
    fractions = mark["exposures"]
    # Uptrend fake data: trend sleeve fully long (each 0.5/8) and rotation
    # sleeve holds top-2 (0.25 each): two symbols at 0.3125, six at 0.0625.
    values = sorted(fractions.values(), reverse=True)
    assert values[0] == pytest.approx(0.3125, abs=0.02)
    assert values[1] == pytest.approx(0.3125, abs=0.02)
    assert values[2] == pytest.approx(0.0625, abs=0.02)
    assert sum(fractions.values()) == pytest.approx(1.0, abs=0.05)
    story = mark["story"]
    assert "TREND HALF" in story and "ROTATION HALF" in story


def test_crash_bounce_paper_flat_without_crash(tmp_path: Path) -> None:
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "crash-bounce",
        tmp_path / "paper",
        collector=FakeDailyCollector(),  # steady +0.2%/day: never a crash
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark = trader.run_once(now=now)
    assert mark["n_fills"] == 0
    assert mark["exposures"] == {}
    assert "no crash" in mark["story"]
    assert trader.state["params"] == {"threshold": -0.03}


class CrashingCollector(FakeDailyCollector):
    """Uptrend that collapses ~28% over days 551-554 (the last bars visible
    to a run at day 555): long-lookback momentum stays positive, but the
    chandelier stop must be latched."""

    CRASH_FROM = 551

    def __init__(self) -> None:
        super().__init__()
        closes = self.df["close"].to_list()
        rows = []
        start_ms = int(T0.timestamp() * 1000)
        price = closes[0]
        for i, close in enumerate(closes):
            c = close * (0.92 ** (i - self.CRASH_FROM + 1)) if i >= self.CRASH_FROM else close
            rows.append(
                [start_ms + i * DAY_MS, price, max(c, price) * 1.001, min(c, price) * 0.999, c, 1e6]
            )
            price = c
        from trading_bot.data.models import ohlcv_frame_from_rows

        self.df = ohlcv_frame_from_rows(rows)


def test_rotation_stop_paper_trader_end_to_end(tmp_path: Path) -> None:
    """Stop variant: same cross-sectional path as rotation on calm data."""
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "rotation-stop",
        tmp_path / "paper",
        collector=FakeDailyCollector(),
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark = trader.run_once(now=now)
    assert set(trader.state["params"]) == {"lookback"}
    invested = {s: f for s, f in mark["exposures"].items() if f > 0}
    assert len(invested) == 2  # steady uptrend: no stop fires, top-2 held
    assert mark["n_fills"] == 2
    assert "ranked all" in mark["story"]


def test_rotation_stop_goes_flat_after_crash(tmp_path: Path) -> None:
    """After a 30% collapse the stop latch must hold every slot in cash,
    even while long-lookback momentum is still positive."""
    now = T0 + timedelta(days=555)
    trader = PaperTrader(
        "rotation-stop",
        tmp_path / "paper",
        collector=CrashingCollector(),
        initial_cash=5_000.0,
        symbols=list(SYMBOLS),
    )
    mark = trader.run_once(now=now)
    assert mark["exposures"] == {}
    assert mark["n_fills"] == 0
    assert "Safety stop active" in mark["story"]
