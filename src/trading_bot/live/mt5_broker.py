"""MT5 execution adapter.

Connects to a RUNNING, ALREADY-LOGGED-IN MetaTrader 5 terminal on this
machine (login happens in the terminal GUI — credentials never pass
through this code). The ``MetaTrader5`` package is Windows-only and an
optional dependency; the module import stays lazy so the rest of the
system (and CI on Linux) never needs it.

Safety posture:
- dry_run=True by default: orders are logged, never sent.
- Orders are tagged with a magic number; reconciliation only counts OUR
  positions, so manual trades in the same account are never touched.
- Unmapped symbols and volume-below-minimum are hard skips with loud
  logs, never silent approximations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAGIC = 520_001  # tags every order this system places

# Default mapping from our lake symbols to typical CFD tickers. The firm's
# actual tickers may differ — override via Mt5Broker(symbol_map=...) after
# checking the terminal's Market Watch.
DEFAULT_SYMBOL_MAP = {
    "BTCUSDT": "BTCUSD",
    "ETHUSDT": "ETHUSD",
    "BNBUSDT": "BNBUSD",
    "SOLUSDT": "SOLUSD",
    "XRPUSDT": "XRPUSD",
    "ADAUSDT": "ADAUSD",
    "DOGEUSDT": "DOGEUSD",
    "LTCUSDT": "LTCUSD",
}


@dataclass(frozen=True)
class OrderOutcome:
    symbol: str  # our symbol id
    broker_symbol: str
    requested_units: float
    lots: float
    dry_run: bool
    sent: bool
    detail: str


class Mt5Broker:
    def __init__(
        self,
        mt5: Any | None = None,
        symbol_map: dict[str, str] | None = None,
        dry_run: bool = True,
    ) -> None:
        if mt5 is None:
            import MetaTrader5 as mt5_module  # Windows-only, optional dep

            mt5 = mt5_module
        self._mt5 = mt5
        self.symbol_map = symbol_map if symbol_map is not None else dict(DEFAULT_SYMBOL_MAP)
        self.dry_run = dry_run

    def connect(self) -> None:
        """Attach to the running terminal. Raises if none is logged in."""
        if not self._mt5.initialize():
            raise RuntimeError(
                f"cannot attach to MT5 terminal: {self._mt5.last_error()} — "
                "is the terminal running and logged in?"
            )
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError("MT5 attached but no account is logged in")
        logger.info(
            "attached to MT5: account %s, equity %.2f %s",
            info.login,
            info.equity,
            info.currency,
        )

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def equity(self) -> float:
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError("no MT5 account info")
        return float(info.equity)

    def positions(self) -> dict[str, float]:
        """Our net position in base units per OUR symbol id (magic-filtered)."""
        reverse = {v: k for k, v in self.symbol_map.items()}
        result: dict[str, float] = {}
        for pos in self._mt5.positions_get() or []:
            if pos.magic != MAGIC or pos.symbol not in reverse:
                continue
            ours = reverse[pos.symbol]
            contract = self._contract_size(pos.symbol)
            signed = pos.volume * contract * (1.0 if pos.type == 0 else -1.0)  # 0 = buy
            result[ours] = result.get(ours, 0.0) + signed
        return result

    def place_market(self, symbol: str, delta_units: float) -> OrderOutcome:
        """Buy (delta>0) or sell (delta<0) ``delta_units`` base units."""
        broker_symbol = self.symbol_map.get(symbol)
        if broker_symbol is None:
            return OrderOutcome(symbol, "?", delta_units, 0.0, self.dry_run, False, "unmapped")

        info = self._mt5.symbol_info(broker_symbol)
        if info is None:
            return OrderOutcome(
                symbol, broker_symbol, delta_units, 0.0, self.dry_run, False, "unknown to broker"
            )
        contract = float(info.trade_contract_size)
        lots = abs(delta_units) / contract
        step = float(info.volume_step)
        lots = round(lots / step) * step
        if lots < float(info.volume_min):
            return OrderOutcome(
                symbol,
                broker_symbol,
                delta_units,
                lots,
                self.dry_run,
                False,
                f"below min volume {info.volume_min}",
            )
        lots = min(lots, float(info.volume_max))

        if self.dry_run:
            logger.info(
                "[DRY RUN] %s %s %.4f lots (%.6f units)",
                "BUY" if delta_units > 0 else "SELL",
                broker_symbol,
                lots,
                abs(delta_units),
            )
            return OrderOutcome(symbol, broker_symbol, delta_units, lots, True, False, "dry run")

        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": broker_symbol,
            "volume": lots,
            "type": self._mt5.ORDER_TYPE_BUY if delta_units > 0 else self._mt5.ORDER_TYPE_SELL,
            "deviation": 50,  # max slippage in points
            "magic": MAGIC,
            "comment": "trading_bot",
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        result = self._mt5.order_send(request)
        ok = result is not None and result.retcode == self._mt5.TRADE_RETCODE_DONE
        detail = f"retcode={getattr(result, 'retcode', 'none')}"
        if not ok:
            logger.error("order FAILED for %s: %s", broker_symbol, detail)
        else:
            logger.info("filled %s %.4f lots: %s", broker_symbol, lots, detail)
        return OrderOutcome(symbol, broker_symbol, delta_units, lots, False, ok, detail)

    def flatten_all(self) -> list[OrderOutcome]:
        """Close every position this system owns (magic-tagged), by ticket.

        Used by the intraday guard. Respects dry_run like everything else.
        """
        outcomes = []
        reverse = {v: k for k, v in self.symbol_map.items()}
        for pos in self._mt5.positions_get() or []:
            if pos.magic != MAGIC or pos.symbol not in reverse:
                continue
            if self.dry_run:
                logger.info("[DRY RUN] would CLOSE %s %.4f lots", pos.symbol, pos.volume)
                outcomes.append(
                    OrderOutcome(
                        reverse[pos.symbol], pos.symbol, 0.0, pos.volume, True, False, "dry run"
                    )
                )
                continue
            request = {
                "action": self._mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": self._mt5.ORDER_TYPE_SELL if pos.type == 0 else self._mt5.ORDER_TYPE_BUY,
                "position": pos.ticket,
                "deviation": 50,
                "magic": MAGIC,
                "comment": "guard flatten",
                "type_filling": self._mt5.ORDER_FILLING_IOC,
            }
            result = self._mt5.order_send(request)
            ok = result is not None and result.retcode == self._mt5.TRADE_RETCODE_DONE
            detail = f"retcode={getattr(result, 'retcode', 'none')}"
            (logger.info if ok else logger.error)("close %s: %s", pos.symbol, detail)
            outcomes.append(
                OrderOutcome(reverse[pos.symbol], pos.symbol, 0.0, pos.volume, False, ok, detail)
            )
        return outcomes

    def _contract_size(self, broker_symbol: str) -> float:
        info = self._mt5.symbol_info(broker_symbol)
        return float(info.trade_contract_size) if info is not None else 1.0
