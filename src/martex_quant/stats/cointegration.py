"""Engle-Granger cointegration test, stdlib-only.

Written rather than imported because ``statsmodels`` is not a dependency of
this project and the standing rule is stdlib-first: a new runtime dependency
needs a reason, and sixty lines of well-tested linear algebra is not one.

THE TEST
--------
Two log price series are cointegrated if some linear combination of them is
stationary even though each is not. Engle-Granger is two steps:

1. Regress ``log_a`` on ``log_b`` with a constant. The slope is the hedge
   ratio; the residual is the spread.
2. Test that residual for a unit root with an Augmented Dickey-Fuller
   regression. If the residual reverts, the pair is cointegrated.

CRITICAL VALUES — the part that is easy to get wrong
----------------------------------------------------
The ADF statistic here may NOT be compared against ordinary t-distribution
quantiles, and may not even be compared against standard ADF critical
values. The residual being tested was *estimated* in step 1, which makes
rejection easier by construction, so Engle-Granger has its own (more
demanding) critical values.

The values below are MacKinnon's asymptotic critical values for the
no-trend, one-regressor case. They are asymptotic approximations, not exact
finite-sample values: with n=365 the true 5% value is slightly more
negative than -3.34, so this test is marginally permissive. That is
recorded rather than hidden, and it biases toward admitting pairs, which
the trading bars then have to survive anyway.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# MacKinnon asymptotic critical values, Engle-Granger residual ADF,
# constant, no trend, 2 variables (1 regressor).
EG_CRITICAL = {0.01: -3.90, 0.05: -3.34, 0.10: -3.04}

# Hard stop on the ADF lag order. One lag absorbs first-order residual
# autocorrelation, which daily crypto spreads reliably have; more lags
# would be another free parameter and this hypothesis declares none.
ADF_LAGS = 1


@dataclass(frozen=True)
class CointegrationResult:
    """Formation-window statistics. Everything here is frozen for trading."""

    hedge_ratio: float  # beta: units of B shorted per unit of A held
    intercept: float
    adf_stat: float
    spread_mean: float
    spread_std: float
    n_obs: int

    def is_cointegrated(self, alpha: float = 0.05) -> bool:
        return self.adf_stat < EG_CRITICAL[alpha]


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting. None if singular."""
    n = len(rhs)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col] / aug[col][col]
            for k in range(col, n + 1):
                aug[row][k] -= factor * aug[col][k]
    return [aug[i][n] / aug[i][i] for i in range(n)]


def _ols(y: Sequence[float], columns: Sequence[Sequence[float]]) -> tuple[list[float], float]:
    """Least squares via normal equations. Returns (coefficients, t-stat of
    the SECOND column), which is the only standard error this module needs.

    Returns an empty coefficient list if the system is singular.
    """
    k = len(columns)
    n = len(y)
    xtx = [
        [sum(columns[i][t] * columns[j][t] for t in range(n)) for j in range(k)] for i in range(k)
    ]
    xty = [sum(columns[i][t] * y[t] for t in range(n)) for i in range(k)]
    beta = _solve(xtx, xty)
    if beta is None or n <= k:
        return [], float("nan")

    resid = [y[t] - sum(beta[i] * columns[i][t] for i in range(k)) for t in range(n)]
    sigma2 = sum(r * r for r in resid) / (n - k)
    # Standard error of coefficient 1 needs that diagonal of (X'X)^-1.
    unit = [1.0 if i == 1 else 0.0 for i in range(k)]
    inv_col = _solve(xtx, unit)
    if inv_col is None or inv_col[1] <= 0 or sigma2 <= 0:
        return beta, float("nan")
    return beta, beta[1] / math.sqrt(sigma2 * inv_col[1])


def engle_granger(log_a: Sequence[float], log_b: Sequence[float]) -> CointegrationResult | None:
    """Test whether ``log_a`` and ``log_b`` are cointegrated.

    Returns None when the input is too short or degenerate (a constant
    series, a singular system). None means "cannot say", never "not
    cointegrated" — the caller must not treat them as the same thing.
    """
    n = len(log_a)
    if n != len(log_b) or n < 60:
        return None

    mean_b = sum(log_b) / n
    var_b = sum((x - mean_b) ** 2 for x in log_b)
    if var_b <= 0:
        return None
    mean_a = sum(log_a) / n
    beta = sum((log_a[t] - mean_a) * (log_b[t] - mean_b) for t in range(n)) / var_b
    alpha = mean_a - beta * mean_b
    spread = [log_a[t] - beta * log_b[t] - alpha for t in range(n)]

    # ADF on the spread: d[t] = c + gamma*s[t-1] + phi*d[t-1] + e
    start = 1 + ADF_LAGS
    y = [spread[t] - spread[t - 1] for t in range(start, n)]
    if len(y) < 30:
        return None
    const = [1.0] * len(y)
    lagged = [spread[t - 1] for t in range(start, n)]
    dlag = [spread[t - 1] - spread[t - 2] for t in range(start, n)]
    _, tstat = _ols(y, [const, lagged, dlag])
    if math.isnan(tstat):
        return None

    spread_mean = sum(spread) / n
    variance = sum((s - spread_mean) ** 2 for s in spread) / (n - 1)
    if variance <= 0:
        return None
    return CointegrationResult(
        hedge_ratio=beta,
        intercept=alpha,
        adf_stat=tstat,
        spread_mean=spread_mean,
        spread_std=math.sqrt(variance),
        n_obs=n,
    )
