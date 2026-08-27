"""Cross-venue price dislocation signals (family F2).

The same asset quoted on a USD venue and on USDT venues does not carry
the same number. This module turns that into four signals, defined once
and shared by every trial in the family, so an info study and the
strategy built on it cannot silently drift apart.

Spec: docs/hypotheses/68-cross-venue-dislocation.md Section 4.3.

With all prices as natural logs — ``c`` Coinbase USD, ``b`` Binance USDT,
``o`` OKX USDT, ``g`` Bitfinex USDT/USD — a USDT venue's log-USD price is
``b + g``, and:

    s1_raw_premium  = c - b              the naive "Coinbase premium"
    s2_adj_premium  = c - (b + g)        the asset dislocation alone
    s3_dispersion   = sd{c, b+g, o+g}    how much the venues disagree
    s4_peg          = g                  the stablecoin alone

``s1 = s2 + s4`` exactly, which is the whole point: it separates an asset
dislocation from a stablecoin one.

Extracted from scripts/h68_cross_venue_killtest.py so H69 consumes the
*same rows* H68 measured rather than a second hand-rolled copy — the
defect the panel audit recorded when it found six independent copies of
the trailing-percentile helper.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from martex_quant.features.panel import forward_return, trailing_percentile_rank

VENUE_SUBDIR = Path("data/venues")
PEG_FILE = "peg_usdt_usd.parquet"
USDT_VENUES = ("binance", "okx")
USD_VENUE = "coinbaseexchange"

SIGNAL_NAMES = ("s1_raw_premium", "s2_adj_premium", "s3_dispersion", "s4_peg")


def _as_float(value: object) -> float:
    """Narrow a polars aggregate to float, treating an empty column as 0.0."""
    return 0.0 if value is None else float(value)  # type: ignore[arg-type]


def _read(root: Path, venue: str, symbol: str) -> pl.DataFrame | None:
    path = root / VENUE_SUBDIR / f"{venue}_{symbol}.parquet"
    if not path.exists():
        return None
    return pl.read_parquet(path).sort("timestamp")


def contiguous_segments(frame: pl.DataFrame, min_length: int) -> list[pl.DataFrame]:
    """Split a symbol's series at any break in consecutive daily bars.

    Coinbase suspended XRP/USD for 904 days over the SEC suit. Without
    this split, ``shift(-h)`` would pair 2021-01-19 with a date in 2023
    and report a two-and-a-half-year move as a 7-day forward return, and
    the trailing percentile window would rank against prices from before
    the delisting. Segments make both operations respect the hole.
    """
    gaps = frame.select(
        (pl.col("timestamp").diff().dt.total_days() > 1).fill_null(False).alias("brk")
    )["brk"].to_list()
    out: list[pl.DataFrame] = []
    start = 0
    for i, is_break in enumerate(gaps):
        if is_break:
            out.append(frame.slice(start, i - start))
            start = i
    out.append(frame.slice(start, frame.height - start))
    return [s for s in out if s.height > min_length]


def build_signal_panel(
    root: Path,
    *,
    pct_window: int,
    horizons: tuple[int, ...],
    volume_floor: float,
) -> tuple[pl.DataFrame, list[str], list[tuple[str, float]]]:
    """Join the three venues plus the peg, derive the four signals.

    Returns ``(panel, kept, rejected)``. ``panel`` carries one row per
    surviving symbol-day with the raw signals, their trailing percentile
    ranks (``pct_<signal>``), forward returns on the Binance close, and
    trailing 1d/7d returns. ``rejected`` lists symbols dropped by the
    liquidity floor and the median volume that failed it.

    The floor is applied to the MEDIAN quote volume of every venue leg
    over the symbol's full common history: below it, a daily "close" is a
    stale last trade rather than a price.
    """
    peg = (
        pl.read_parquet(root / VENUE_SUBDIR / PEG_FILE)
        .sort("timestamp")
        .select("timestamp", pl.col("close").log().alias("g"))
    )
    symbols = sorted(
        {p.stem.split("_", 1)[1] for p in (root / VENUE_SUBDIR).glob("binance_*.parquet")}
    )

    parts: list[pl.DataFrame] = []
    kept: list[str] = []
    rejected: list[tuple[str, float]] = []
    min_segment = pct_window + (max(horizons) if horizons else 0)

    for symbol in symbols:
        legs = {v: _read(root, v, symbol) for v in (*USDT_VENUES, USD_VENUE)}
        binance, okx, coinbase = legs["binance"], legs["okx"], legs[USD_VENUE]
        if binance is None or okx is None or coinbase is None:
            continue

        frame = (
            binance.select(
                "timestamp",
                pl.col("close").alias("binance_close"),
                pl.col("close").log().alias("b"),
                pl.col("quote_volume").alias("vb"),
            )
            .join(
                okx.select(
                    "timestamp",
                    pl.col("close").log().alias("o"),
                    pl.col("quote_volume").alias("vo"),
                ),
                on="timestamp",
                how="inner",
            )
            .join(
                coinbase.select(
                    "timestamp",
                    pl.col("close").log().alias("c"),
                    pl.col("quote_volume").alias("vc"),
                ),
                on="timestamp",
                how="inner",
            )
        )
        if frame.height == 0:
            continue

        # polars' median() is typed as a union over every dtype it could
        # hold, so narrow to float once rather than fighting it per use.
        floor = min(_as_float(frame[c].median()) for c in ("vb", "vo", "vc"))
        if floor < volume_floor:
            rejected.append((symbol, floor))
            continue

        frame = frame.join(peg, on="timestamp", how="inner").sort("timestamp")
        frame = frame.with_columns(
            s1_raw_premium=pl.col("c") - pl.col("b"),
            s2_adj_premium=pl.col("c") - (pl.col("b") + pl.col("g")),
            s4_peg=pl.col("g"),
        ).with_columns(
            s3_dispersion=pl.concat_list(
                pl.col("c"), pl.col("b") + pl.col("g"), pl.col("o") + pl.col("g")
            ).list.std()
        )

        for segment in contiguous_segments(frame, min_segment):
            piece = segment
            for name in SIGNAL_NAMES:
                ranks = trailing_percentile_rank(
                    piece[name].to_list(), window=pct_window, skip_nulls=False
                )
                piece = piece.with_columns(pl.Series(f"pct_{name}", ranks, dtype=pl.Float64))
            for h in horizons:
                feature = forward_return(h, price_column="binance_close")
                piece = piece.with_columns(**{feature.name: feature.expr})
            piece = piece.with_columns(
                trail1=pl.col("binance_close") / pl.col("binance_close").shift(1) - 1.0,
                trail7=pl.col("binance_close") / pl.col("binance_close").shift(7) - 1.0,
            )
            parts.append(piece.with_columns(pl.lit(symbol).alias("symbol")))
        kept.append(symbol)

    panel = pl.concat(parts).rename({"timestamp": "day"})
    return panel, kept, rejected
