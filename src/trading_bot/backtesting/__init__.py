"""Event-driven backtesting: the source of truth for strategy evaluation.

Structurally look-ahead-free: strategies see market data only through the
History view, which cannot return bars past the current cursor.
"""
