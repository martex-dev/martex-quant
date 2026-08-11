"""Point-in-time market state: what was knowable at an exact timestamp.

Layer 4 of the MI Lab. The guarantee is structural, mirroring
``backtesting.history.History``: a MarketState built as of ``t`` physically
cannot expose a value whose availability time is after ``t``, so look-ahead
is inexpressible rather than merely discouraged.
"""
