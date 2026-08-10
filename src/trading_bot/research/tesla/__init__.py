"""CNN direction study on TSLA daily bars.

Question: can a 1D convolutional network, given a window of causal,
volatility-scaled bar features, predict whether TSLA hits an upper or a
lower volatility barrier first over the next H trading days?

The study is deliberately built so that a null result is trustworthy:
every feature is causal, every split is purged and embargoed, and every
model is scored against baselines that require no learning at all.
"""
