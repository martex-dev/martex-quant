"""Intraday guard tests: daily trip, static latch, next-day re-arm."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from test_mt5_broker import FakeMT5

from trading_bot.live.guard import check_once, is_halted
from trading_bot.live.mt5_broker import MAGIC, Mt5Broker

T0 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class GuardFakeMT5(FakeMT5):
    """FakeMT5 with mutable equity and closable positions."""

    def set_equity(self, value: float) -> None:
        self._equity = value

    def add_position(self, symbol: str, volume: float, ticket: int) -> None:
        self.positions.append(
            SimpleNamespace(magic=MAGIC, symbol=symbol, volume=volume, type=0, ticket=ticket)
        )

    def order_send(self, request: dict) -> SimpleNamespace:
        result = super().order_send(request)
        if "position" in request:  # a close: remove the position
            self.positions = [p for p in self.positions if p.ticket != request["position"]]
        return result


def make(tmp_path: Path, equity: float = 5_000.0) -> tuple[GuardFakeMT5, Mt5Broker, Path]:
    fake = GuardFakeMT5(equity=equity)
    broker = Mt5Broker(mt5=fake, dry_run=False)
    broker.connect()
    return fake, broker, tmp_path / "guard"


def test_no_action_on_quiet_day(tmp_path: Path) -> None:
    _, broker, root = make(tmp_path)
    record = check_once(broker, root, now=T0)
    assert record["action"] == "none"
    assert not is_halted(root, T0)


def test_daily_trip_flattens_and_halts_until_next_day(tmp_path: Path) -> None:
    fake, broker, root = make(tmp_path)
    fake.add_position("BTCUSD", 0.2, ticket=1)
    check_once(broker, root, now=T0)  # records day start 5000

    fake.set_equity(4_870.0)  # -2.6% on the day
    record = check_once(broker, root, now=T0 + timedelta(hours=2))
    assert "DAILY TRIP" in record["action"]
    assert fake.positions == []  # flattened
    assert is_halted(root, T0 + timedelta(hours=3))

    # Next UTC day: re-armed automatically.
    next_day = T0 + timedelta(days=1)
    record = check_once(broker, root, now=next_day)
    assert record["action"] == "none"
    assert not is_halted(root, next_day)


def test_static_floor_latches_forever(tmp_path: Path) -> None:
    fake, broker, root = make(tmp_path)
    fake.add_position("ETHUSD", 1.0, ticket=2)
    check_once(broker, root, now=T0)

    fake.set_equity(4_700.0)  # firm floor; ours is 4750 — already breached
    record = check_once(broker, root, now=T0 + timedelta(hours=1))
    assert "STATIC FLOOR" in record["action"]
    assert (root / "KILLED").exists()
    assert fake.positions == []

    # Days later, equity recovered: STILL halted. The latch does not care.
    fake.set_equity(5_500.0)
    later = T0 + timedelta(days=5)
    check_once(broker, root, now=later)
    assert is_halted(root, later)


def test_killed_latch_re_flattens_reopened_positions(tmp_path: Path) -> None:
    fake, broker, root = make(tmp_path)
    check_once(broker, root, now=T0)
    fake.set_equity(4_600.0)
    check_once(broker, root, now=T0 + timedelta(hours=1))  # latches

    fake.add_position("BTCUSD", 0.1, ticket=9)  # something re-opened somehow
    record = check_once(broker, root, now=T0 + timedelta(hours=2))
    assert record["action"] == "re-flatten (killed)"
    assert fake.positions == []


def test_trade_runner_refuses_while_halted(tmp_path: Path) -> None:
    from test_paper_trader import FakeDailyCollector

    from trading_bot.live import trade

    fake, broker, guard_root = make(tmp_path)
    check_once(broker, guard_root, now=T0)
    fake.set_equity(4_600.0)
    check_once(broker, guard_root, now=T0 + timedelta(hours=1))  # latched

    mark = trade.run_once(
        broker,
        FakeDailyCollector(),
        "vol-target",
        tmp_path / "live",
        now=T0 + timedelta(hours=3),
        guard_root=guard_root,
    )
    assert mark == {
        "ts": (T0 + timedelta(hours=3)).isoformat(),
        "halted": True,
        "orders": 0,
    }
    assert fake.sent == []
