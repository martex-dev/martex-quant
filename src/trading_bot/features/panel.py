"""Canonical daily panel construction, consolidated from the research scripts.

Audit and evidence: docs/research/mi-layer1-panel-audit.md. Every shared
feature was compared element-wise across the historical builders on the full
lake and found bit-identical (max_abs_diff 0.0), which is why they may be
consolidated at all. What differed was assembly policy, and every difference
is an explicit parameter here.

The one measured NON-equivalence
--------------------------------
``vol_excl_current`` and ``vol_incl_current`` differ by up to 0.0214 on a
90-day window — the same order as the quantity itself. h24_32 used the
including-current convention for ``vol90``; h13_h14, h15_21 and h22_h23 used
the excluding-current convention. Neither is look-ahead (day t's return is
known at t's close); they are two features that were given the same name.

There is deliberately **no** ``volatility()`` or ``vol()`` function. Both
constructors require an explicit ``name``, so the emitted column keeps its
historical name while the convention is unmissable at the call site::

    vol_excl_current(30, name="vol30")   # h13_h14, h22_h23
    vol_incl_current(90, name="vol90")   # h24_32

Evaluation order is preserved
-----------------------------
``feature_stages`` is a sequence of stages, each becoming exactly one
``with_columns`` call, because some features read columns produced by an
earlier stage (``atr14`` needs ``tr``). Window functions run per symbol
inside the loop and the parts are concatenated afterwards — never ``.over()``
on a concatenated frame. Do not "optimise" either, unless a golden proves
exact equivalence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import polars as pl

from trading_bot.data.models import Interval
from trading_bot.data.store.parquet_store import ParquetStore

MissingSymbol = Literal["raise", "skip"]

# Daily return, close to close. Identical in all seven historical builders.
_RET = (pl.col("close") / pl.col("close").shift(1) - 1.0).alias("ret")

# The lake's canonical day precision is MILLISECONDS (data.models.TIMESTAMP_DTYPE).
# The funding / perp / stream caches under data/ were written at MICROSECOND
# precision, so any frame joined against them must be cast to match or the
# join silently produces zero rows.
#
# Both precisions are real and neither is "correct": ms is the lake's, us is
# the caches'. This is a provenance artifact (see correction candidate 4 in
# docs/research/mi-layer1-panel-audit.md), NOT something to normalise here.
CACHE_DAY_DTYPE = pl.Datetime("us", "UTC")


def align_day_to_cache_precision(frame: pl.DataFrame, column: str = "day") -> pl.DataFrame:
    """Cast a day column to the microsecond precision the caches were written at.

    Named rather than left as an inline ``.cast(pl.Datetime("us", "UTC"))`` so
    that a reader can see WHY the cast exists — cache alignment — and so the
    ms/us distinction is visible in the code instead of being an unexplained
    incantation repeated at four call sites (h08, h10, h22_h23's H23b,
    h33_40's H34).
    """
    return frame.with_columns(pl.col(column).cast(CACHE_DAY_DTYPE))


@dataclass(frozen=True)
class Feature:
    """One named column and the expression that produces it."""

    name: str
    expr: pl.Expr


# --- price / return features ---------------------------------------------------------


def momentum(window: int) -> Feature:
    """Trailing return over ``window`` bars. Emits ``r{window}``."""
    return Feature(f"r{window}", pl.col("close") / pl.col("close").shift(window) - 1.0)


def momentum_skip(window: int, skip: int) -> Feature:
    """Trailing return from ``window`` bars ago to ``skip`` bars ago —
    momentum with the most recent ``skip`` bars excluded (h24_32's H32).
    Emits ``r{window}skip{skip}``."""
    return Feature(
        f"r{window}skip{skip}",
        pl.col("close").shift(skip) / pl.col("close").shift(window) - 1.0,
    )


def forward_return(
    horizon: int,
    *,
    price_column: str = "close",
    name: str | None = None,
) -> Feature:
    """Return over the NEXT ``horizon`` bars: ``P[t+h] / P[t] - 1``.

    Endpoints are exclusive of *t* and inclusive of *t+h* in every historical
    implementation; the trailing ``horizon`` rows are null and are dropped by
    the caller, never filled.

    ``horizon`` counts BARS of whatever frame this is applied to — days on the
    daily panels, 15-minute bars on the intraday ones. The emitted name
    therefore cannot always be derived from it: h52/h53 call a 4-bar forward
    ``fwd1h`` and an 8-bar forward ``fwd2h``, while h44_50 calls the same
    8-bar forward ``fwd8``. Callers whose name is not ``fwd{horizon}`` pass
    ``name`` explicitly.

    ``price_column`` exists because the relative studies join two price
    series into one frame under names like ``eth``/``btc`` or ``btc``/``alt``.

    Applied to a SINGLE series. Every historical caller runs it inside a
    per-symbol loop or on an already-joined wide frame; none uses ``.over()``.
    """
    return Feature(
        name if name is not None else f"fwd{horizon}",
        pl.col(price_column).shift(-horizon) / pl.col(price_column) - 1.0,
    )


def relative_forward_return_ratio(
    horizon: int,
    *,
    numerator: str,
    denominator: str,
    name: str,
) -> Feature:
    """Ratio of two forward returns: ``(1 + r_a) / (1 + r_b) - 1``.

    The forward return of holding A funded by B — what a ratio/pairs trade
    actually earns. NOT the same quantity as
    :func:`relative_forward_return_difference`; see its docstring.

    Historical callers: h33_40's H35 pairs stat-arb (``fwd_ratio``, 7 days,
    close vs close_b) and h52_55_57's H56 intraday ETH/BTC reversion
    (``fwd2h``, 8 bars, eth vs btc).
    """
    return Feature(
        name,
        (pl.col(numerator).shift(-horizon) / pl.col(numerator))
        / (pl.col(denominator).shift(-horizon) / pl.col(denominator))
        - 1.0,
    )


def relative_forward_return_difference(
    horizon: int,
    *,
    minuend: str,
    subtrahend: str,
    name: str,
) -> Feature:
    """Difference of two forward returns: ``r_a - r_b``.

    Algebraically DISTINCT from :func:`relative_forward_return_ratio`::

        ratio      = (r_a - r_b) / (1 + r_b)
        difference =  r_a - r_b

    They agree only when ``r_b == 0``. At the 30-day horizon this caller uses,
    crypto ``r_b`` is routinely tens of percent, so the two differ materially.
    Both are preserved because both were published.

    Historical caller: v2_m1_killtest's dominance study (``fwd_rel``,
    30 days, BTC minus the alt basket).
    """
    return Feature(
        name,
        (pl.col(minuend).shift(-horizon) / pl.col(minuend) - 1.0)
        - (pl.col(subtrahend).shift(-horizon) / pl.col(subtrahend) - 1.0),
    )


# --- volatility: two conventions, never one ------------------------------------------


def vol_excl_current(window: int, *, name: str) -> Feature:
    """Rolling std of returns EXCLUDING the current bar (``ret.shift(1)``).

    ``name`` is required: the historical column name is ambiguous between
    the two conventions, so it must be stated rather than defaulted.
    Historical callers: h13_h14 (vol30, vol10), h15_21 (vol10),
    h22_h23 (vol30).
    """
    return Feature(name, pl.col("ret").shift(1).rolling_std(window))


def vol_incl_current(window: int, *, name: str) -> Feature:
    """Rolling std of returns INCLUDING the current bar.

    Differs from :func:`vol_excl_current` by up to 0.0214 at window=90 —
    a real difference, not rounding. Historical caller: h24_32 (vol90),
    which feeds ``riskadj`` (H24) and the low-vol ranking (H27).
    """
    return Feature(name, pl.col("ret").rolling_std(window))


# --- rolling statistics ---------------------------------------------------------------


def rolling_mean_close(window: int, *, name: str) -> Feature:
    """h15_21's ``ma90``."""
    return Feature(name, pl.col("close").rolling_mean(window))


def rolling_max_close(window: int, *, name: str) -> Feature:
    """h15_21's ``peak365``, h24_32's ``max365``, h33_40's ``hi30``."""
    return Feature(name, pl.col("close").rolling_max(window))


def rolling_mean_volume(window: int, *, name: str) -> Feature:
    """h15_21's ``v7`` / ``v30``."""
    return Feature(name, pl.col("volume").rolling_mean(window))


def rolling_max_return(window: int, *, name: str) -> Feature:
    """h24_32's ``maxret30`` (the MAX / lottery-effect ranking, H28)."""
    return Feature(name, pl.col("ret").rolling_max(window))


def rolling_mean_of(column: str, window: int, *, name: str) -> Feature:
    """Rolling mean of an earlier-stage column — h33_40's ``atr14`` over ``tr``."""
    return Feature(name, pl.col(column).rolling_mean(window))


def true_range() -> Feature:
    """Wilder true range. Emits ``tr``; h33_40 feeds it into ``atr14``."""
    return Feature(
        "tr",
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("close").shift(1)).abs(),
            (pl.col("low") - pl.col("close").shift(1)).abs(),
        ),
    )


def amihud_illiquidity(window: int, *, name: str) -> Feature:
    """h24_32's ``illiq30``: rolling mean of |ret| / (close * volume).

    Recorded as correction candidate 2 in the panel audit — whether the
    lake's ``volume`` is base or quote units decides if this matches the
    textbook Amihud measure. Preserved exactly as published.
    """
    return Feature(
        name, (pl.col("ret").abs() / (pl.col("close") * pl.col("volume"))).rolling_mean(window)
    )


def volume_shock(window: int, *, name: str) -> Feature:
    """h24_32's ``vshock``: today's volume over its rolling mean."""
    return Feature(name, pl.col("volume") / pl.col("volume").rolling_mean(window))


def up_day_share(window: int, *, name: str) -> Feature:
    """h24_32's ``upshare90``: fraction of up days (trend smoothness, H31)."""
    return Feature(name, (pl.col("ret") > 0).cast(pl.Float64).rolling_mean(window))


def ratio(numerator: str, denominator: str, *, name: str) -> Feature:
    """Plain column ratio — h24_32's ``hi52`` and ``riskadj``."""
    return Feature(name, pl.col(numerator) / pl.col(denominator))


# --- trailing percentile rank ---------------------------------------------------------


def trailing_percentile_rank(
    values: Sequence[float | None],
    *,
    window: int,
    skip_nulls: bool,
) -> list[float | None]:
    """Fraction of the trailing window at or below the current value.

    Consolidates six hand-rolled copies (h08, h10, h13_h14, h15_21 H18,
    h22_h23 H23b, h44_50 H47). All six rank against
    ``values[i - window : i + 1]`` — a **window + 1** observation span that
    includes the current value. That off-by-one is consistent across every
    copy and is preserved; it is recorded as correction candidate 3 in the
    panel audit because the naming implies otherwise.

    ``skip_nulls`` reproduces h13_h14's copy, the only one that filters
    ``None`` out of the window (changing the denominator) and returns
    ``None`` when the current value is itself ``None``. Every other copy
    ran on a series with no nulls and did neither.
    """
    out: list[float | None] = []
    for i, value in enumerate(values):
        if i < window or (skip_nulls and value is None):
            out.append(None)
            continue
        span = values[i - window : i + 1]
        if skip_nulls:
            span = [w for w in span if w is not None]
        assert value is not None
        out.append(sum(1 for w in span if w is not None and w <= value) / len(span))
    return out


# --- panel assembly -------------------------------------------------------------------


def daily_panel(
    store: ParquetStore,
    symbols: Sequence[str],
    *,
    base_columns: Sequence[str],
    feature_stages: Sequence[Sequence[Feature]],
    on_missing_symbol: MissingSymbol,
    drop_nulls: Sequence[str] | None = None,
    per_symbol_hook: Callable[[pl.DataFrame], pl.DataFrame] | None = None,
) -> pl.DataFrame:
    """Build a long (one row per symbol-day) daily panel from the lake.

    ``base_columns`` is the ORDERED set of columns surviving the initial
    select, after ``day``. The literal ``"ret"`` is expanded to the daily
    return expression; anything else is passed through from the lake. Order
    is honoured because the historical builders differ in it (h13_h14 has
    ``ret`` before ``close``; the others after).

    ``feature_stages``: each stage becomes one ``with_columns`` call, in
    order, so a feature may depend on a column an earlier stage produced.

    ``on_missing_symbol``: ``"skip"`` for the universe-wide builders, which
    tolerate symbols absent from the lake; ``"raise"`` for the LEGACY8
    builders, which let ``FileNotFoundError`` propagate.

    ``drop_nulls`` is applied ONCE to the concatenated panel. Placement is a
    real semantic difference — dropping earlier can remove whole days and so
    change a day-block bootstrap, not merely the sample size — so builders
    that dropped inside pass it here and builders that dropped at their call
    sites pass ``None``.

    ``per_symbol_hook`` runs after the stages and before the symbol tag, for
    the per-symbol work that is not a plain expression (h24_32's BTC join
    and beta chain, the trailing-percentile loops).
    """
    parts: list[pl.DataFrame] = []
    for symbol in symbols:
        try:
            frame = store.read(symbol, Interval.D1).sort("timestamp")
        except FileNotFoundError:
            if on_missing_symbol == "raise":
                raise
            continue
        frame = frame.select(
            pl.col("timestamp").alias("day"),
            *(_RET if column == "ret" else pl.col(column) for column in base_columns),
        )
        for stage in feature_stages:
            frame = frame.with_columns(**{feature.name: feature.expr for feature in stage})
        if per_symbol_hook is not None:
            frame = per_symbol_hook(frame)
        parts.append(frame.with_columns(pl.lit(symbol).alias("symbol")))

    panel = pl.concat(parts)
    return panel.drop_nulls(list(drop_nulls)) if drop_nulls is not None else panel
