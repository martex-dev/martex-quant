"""MT5 adapter and live runner tests against a fake MT5 module — no
terminal, no network, no real orders anywhere near the test suite."""

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from test_paper_trader import T0, FakeDailyCollector

from martex_quant.live import trade
from martex_quant.live.mt5_broker import MAGIC, Mt5Broker


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_FILLING_IOC = 2
    TRADE_RETCODE_DONE = 10009

    def __init__(self, equity: float = 5_000.0) -> None:
        self._equity = equity
        self.positions: list[SimpleNamespace] = []
        self.sent: list[dict] = []

    def initialize(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def last_error(self) -> tuple:
        return (0, "ok")

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(login=12345, equity=self._equity, currency="USD")

    def positions_get(self) -> list[SimpleNamespace]:
        return self.positions

    def symbol_info(self, symbol: str) -> SimpleNamespace | None:
        if symbol == "MISSING":
            return None
        return SimpleNamespace(
            trade_contract_size=1.0, volume_step=0.01, volume_min=0.01, volume_max=100.0
        )

    def order_send(self, request: dict) -> SimpleNamespace:
        self.sent.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE)


def make_broker(fake: FakeMT5, dry_run: bool = True) -> Mt5Broker:
    broker = Mt5Broker(mt5=fake, dry_run=dry_run)
    broker.connect()
    return broker


def test_dry_run_never_sends_orders() -> None:
    fake = FakeMT5()
    broker = make_broker(fake, dry_run=True)
    outcome = broker.place_market("BTCUSDT", 0.15)
    assert outcome.dry_run and not outcome.sent
    assert outcome.lots == 0.15
    assert fake.sent == []


def test_live_order_sent_with_magic() -> None:
    fake = FakeMT5()
    broker = make_broker(fake, dry_run=False)
    outcome = broker.place_market("ETHUSDT", -2.0)
    assert outcome.sent
    (request,) = fake.sent
    assert request["magic"] == MAGIC
    assert request["symbol"] == "ETHUSD"
    assert request["type"] == FakeMT5.ORDER_TYPE_SELL
    assert request["volume"] == 2.0


def test_lot_rounding_to_step() -> None:
    broker = make_broker(FakeMT5())
    outcome = broker.place_market("BTCUSDT", 0.1234)
    assert outcome.lots == 0.12


def test_below_min_volume_skipped() -> None:
    fake = FakeMT5()
    broker = make_broker(fake, dry_run=False)
    outcome = broker.place_market("BTCUSDT", 0.001)
    assert not outcome.sent
    assert "below min" in outcome.detail
    assert fake.sent == []


def test_unmapped_symbol_skipped() -> None:
    broker = make_broker(FakeMT5(), dry_run=False)
    outcome = broker.place_market("PEPEUSDT", 1.0)
    assert not outcome.sent
    assert outcome.detail == "unmapped"


def test_positions_filtered_by_magic_and_signed() -> None:
    fake = FakeMT5()
    fake.positions = [
        SimpleNamespace(magic=MAGIC, symbol="BTCUSD", volume=0.5, type=0),  # our long
        SimpleNamespace(magic=MAGIC, symbol="ETHUSD", volume=2.0, type=1),  # our short
        SimpleNamespace(magic=999, symbol="BTCUSD", volume=9.0, type=0),  # manual trade
        SimpleNamespace(magic=MAGIC, symbol="XAUUSD", volume=1.0, type=0),  # not ours
    ]
    broker = make_broker(fake)
    positions = broker.positions()
    assert positions == {"BTCUSDT": 0.5, "ETHUSDT": -2.0}


def test_live_runner_dry_run_end_to_end(tmp_path: Path) -> None:
    fake = FakeMT5(equity=5_000.0)
    broker = make_broker(fake, dry_run=True)
    now = T0 + timedelta(days=555)
    mark = trade.run_once(broker, FakeDailyCollector(), "vol-target", tmp_path / "live", now=now)

    assert mark["dry_run"] is True
    assert mark["equity"] == 5_000.0
    assert mark["orders"] == 8  # uptrend: wants to enter everything
    assert all(e > 0.9 for e in mark["exposures"].values())
    assert fake.sent == []  # ...but dry run sent nothing

    journal = (tmp_path / "live" / "journal.jsonl").read_text(encoding="utf-8")
    assert len(journal.strip().splitlines()) == 8


def test_live_runner_sends_and_reconciles(tmp_path: Path) -> None:
    fake = FakeMT5(equity=5_000.0)
    broker = make_broker(fake, dry_run=False)
    now = T0 + timedelta(days=555)
    trade.run_once(broker, FakeDailyCollector(), "vol-target", tmp_path / "live", now=now)
    assert len(fake.sent) == 8

    # Simulate the fills now existing as positions; a second run at the same
    # equity should be near-flat (only dust deltas, all skipped).
    fake.positions = [
        SimpleNamespace(magic=MAGIC, symbol=req["symbol"], volume=req["volume"], type=req["type"])
        for req in fake.sent
    ]
    fake.sent.clear()
    trade.run_once(broker, FakeDailyCollector(), "vol-target", tmp_path / "live", now=now)
    assert fake.sent == []  # nothing to do: positions already at target
