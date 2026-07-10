"""Data subsystem: collectors -> validation -> Parquet store.

Everything downstream (backtests, strategies, risk) inherits the quality of
this layer, so it is built and tested first.
"""
