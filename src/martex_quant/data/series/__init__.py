"""Non-OHLCV series: canonical loading with provenance and integrity checks.

The Parquet lake (``data.store.parquet_store``) covers exchange OHLCV: it has
a canonical schema, a catalog, and validation that blocks a bad write. Every
OTHER series the research corpus depends on — funding rates, perp closes,
15-minute intraday panels, taker-buy imbalance, open interest, and the
derived equity streams — sits outside all of that as bare parquet files read
directly with ``pl.read_parquet`` at 18 call sites, with no schema check, no
provenance, and no catalog entry.

This package closes that gap WITHOUT changing any historical result: the
frames it returns are byte-identical to what the direct reads returned. What
it adds is knowing where a frame came from and refusing to hand back one that
has silently drifted.
"""
