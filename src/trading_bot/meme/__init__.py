"""Meme-coin research layer: Solana launch capture, features, economics.

Separate from the OHLCV research corpus on purpose. The instruments here have
a different lifecycle (minutes to hours, not months), a different cost regime
(percent-level round-trip drag, not basis points), and a different failure mode
(the token stops existing). Nothing in here shares the daily-bar assumptions
baked into ``trading_bot.backtesting``.
"""
