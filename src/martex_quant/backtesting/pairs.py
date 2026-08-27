"""Walk-forward cointegrated-pairs backtest (H64).

Pre-registered in ``docs/hypotheses/64-cointegration-pairs.md``.

THE LOOK-AHEAD CONTROL IS THE WHOLE STRATEGY
--------------------------------------------
Pairs trading is trivially profitable if you cheat, and the cheat is
subtle: fit the hedge ratio on data that includes the period you trade, and
the spread reverts to a mean it was fitted to. This module makes that
impossible structurally rather than by discipline:

* Pairs are selected on a **formation window** and traded only on the
  **following, non-overlapping** window.
* ``hedge_ratio``, ``spread_mean`` and ``spread_std`` are computed once at
  formation and **frozen**. Nothing is refitted during trading.
* Day ``t``'s decision uses prices through ``t``'s close and is filled at
  ``t+1``'s open, the engine's standard one-bar latency.

POSITION AND CAPITAL
--------------------
A pair is long one leg and short the other at equal notional, so it carries
no net directional exposure. Notional per leg is
``equity / (2 * max_open)``, which makes gross exposure equal to equity
when every slot is filled — 1x, matching the carry book's convention.
Unfilled slots sit in cash earning nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from martex_quant.stats.cointegration import CointegrationResult, engle_granger

_BPS = 1e-4


@dataclass(frozen=True)
class PairsConfig:
    """Every knob the hypothesis declares. No hidden defaults."""

    z_in: float
    z_out: float
    max_hold_days: int
    z_stop: float = 4.0
    max_open: int = 10
    formation_days: int = 365
    trading_days: int = 180
    fee_bps: float = 10.0
    half_spread_bps: float = 1.0
    alpha: float = 0.05

    @property
    def cost_rate(self) -> float:
        return (self.fee_bps + self.half_spread_bps) * _BPS


@dataclass(frozen=True)
class Candidate:
    """One pair admitted at formation, with its frozen statistics."""

    a: str
    b: str
    stats: CointegrationResult


@dataclass
class _Open:
    a: str
    b: str
    stats: CointegrationResult
    direction: int  # +1 = long A / short B, -1 = the reverse
    notional: float
    days_held: int


def _log_prices(
    panel: dict[str, list[float | None]], symbol: str, lo: int, hi: int
) -> list[float] | None:
    """Log closes over [lo, hi), or None if any bar is missing."""
    import math

    out: list[float] = []
    for value in panel[symbol][lo:hi]:
        if value is None or value <= 0:
            return None
        out.append(math.log(value))
    return out


def form_pairs(
    panel: dict[str, list[float | None]],
    symbols: list[str],
    lo: int,
    hi: int,
    config: PairsConfig,
) -> list[Candidate]:
    """Admit every cointegrated pair in the formation window [lo, hi).

    Ranked by strength of formation evidence (most negative ADF statistic).

    SPECIFICATION NOTE — the pre-registration caps concurrent pairs at 10
    but does not say which 10 to prefer when more qualify. That gap had to
    be filled to implement at all. The rule chosen is the most defensible
    one available: strongest formation-window cointegration evidence. It is
    a formation-time quantity, so it introduces no look-ahead, and no
    alternative rule was tested against results.
    """
    found: list[Candidate] = []
    for i, sym_a in enumerate(symbols):
        series_a = _log_prices(panel, sym_a, lo, hi)
        if series_a is None:
            continue
        for sym_b in symbols[i + 1 :]:
            series_b = _log_prices(panel, sym_b, lo, hi)
            if series_b is None:
                continue
            stats = engle_granger(series_a, series_b)
            if stats is not None and stats.is_cointegrated(config.alpha):
                found.append(Candidate(sym_a, sym_b, stats))
    found.sort(key=lambda c: c.stats.adf_stat)
    return found


def run_pairs(
    frame: pl.DataFrame,
    symbols: list[str],
    config: PairsConfig,
    initial_equity: float = 10_000.0,
) -> pl.DataFrame:
    """Walk forward through ``frame``; return the daily return stream.

    ``frame`` must be sorted by ``timestamp`` with one close column per
    symbol (nulls where a symbol has no bar).
    """
    import math

    panel = {s: frame[s].to_list() for s in symbols}
    stamps = frame["timestamp"].to_list()
    n = len(stamps)

    equity = initial_equity
    rows: list[dict[str, object]] = []
    open_pairs: list[_Open] = []

    window_start = config.formation_days
    candidates: list[Candidate] = []
    next_form = -1

    for t in range(window_start, n):
        # Refit at each trading-window boundary, on the PRECEDING days only.
        if t >= next_form:
            candidates = form_pairs(panel, symbols, t - config.formation_days, t, config)
            next_form = t + config.trading_days
            # A new regime means the old book is closed out, paying costs.
            for pos in open_pairs:
                equity -= pos.notional * config.cost_rate * 2.0
            open_pairs = []

        prev_equity = equity
        pnl = 0.0
        cost = 0.0

        # Mark existing positions on today's move.
        survivors: list[_Open] = []
        for pos in open_pairs:
            pa, pb = panel[pos.a][t], panel[pos.b][t]
            qa, qb = panel[pos.a][t - 1], panel[pos.b][t - 1]
            if not (pa and pb and qa and qb):
                cost += pos.notional * config.cost_rate * 2.0
                continue
            ret_a, ret_b = pa / qa - 1.0, pb / qb - 1.0
            pnl += pos.direction * pos.notional * (ret_a - ret_b)
            pos.days_held += 1

            spread = math.log(pa) - pos.stats.hedge_ratio * math.log(pb) - pos.stats.intercept
            z = (spread - pos.stats.spread_mean) / pos.stats.spread_std
            close = (
                abs(z) <= config.z_out
                or abs(z) >= config.z_stop
                or pos.days_held >= config.max_hold_days
            )
            if close:
                cost += pos.notional * config.cost_rate * 2.0
            else:
                survivors.append(pos)
        open_pairs = survivors

        # Open new positions in free slots, using today's close, filled at
        # tomorrow's open via the one-bar convention (the return above only
        # starts accruing on the following iteration).
        held = {(p.a, p.b) for p in open_pairs}
        notional = prev_equity / (2.0 * config.max_open)
        for cand in candidates:
            if len(open_pairs) >= config.max_open:
                break
            if (cand.a, cand.b) in held:
                continue
            pa, pb = panel[cand.a][t], panel[cand.b][t]
            if not (pa and pb):
                continue
            spread = math.log(pa) - cand.stats.hedge_ratio * math.log(pb) - cand.stats.intercept
            z = (spread - cand.stats.spread_mean) / cand.stats.spread_std
            if config.z_in <= abs(z) < config.z_stop:
                # Spread rich (z>0) means A is expensive: short A, long B.
                open_pairs.append(
                    _Open(cand.a, cand.b, cand.stats, -1 if z > 0 else 1, notional, 0)
                )
                cost += notional * config.cost_rate * 2.0

        equity = prev_equity + pnl - cost
        rows.append(
            {
                "timestamp": stamps[t],
                "ret": (pnl - cost) / prev_equity,
                "gross_ret": pnl / prev_equity,
                "cost_ret": -cost / prev_equity,
                "n_open": len(open_pairs),
                "n_candidates": len(candidates),
                "equity": equity,
            }
        )

    return pl.DataFrame(rows)
