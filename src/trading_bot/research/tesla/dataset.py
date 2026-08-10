"""Load TSLA daily bars and turn them into a causal, labelled tensor.

Two rules govern every line here:

1. **Causality.** A feature at index ``t`` may only use information known
   at the close of day ``t``. Any statistic used for scaling (vol, volume
   baseline) is computed over bars strictly BEFORE ``t``, so no sample can
   peek at its own normalisation constant.
2. **Stationarity.** Raw prices never enter the model. Every channel is a
   return, a ratio, or a z-score, so the test period lives in the same
   numeric range as the training period.

Labels use the triple-barrier method: from the close of day ``t`` we look
forward ``horizon`` days and record which volatility barrier the price
touches first. Barrier width scales with trailing volatility, so a "move"
means the same thing in calm 2015 and in violent 2020.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

# Label encoding. NEUTRAL means neither barrier was touched within the
# horizon: a real outcome, not a missing value, and one we refuse to trade.
DOWN: Final = 0
UP: Final = 1
NEUTRAL: Final = 2

CHANNEL_NAMES: Final = (
    "ret_scaled",  # log return / trailing vol
    "range_scaled",  # (high - low) / prev close / trailing vol
    "body",  # (close - open) / (high - low), bounded [-1, 1]
    "close_loc",  # where close sat inside the day's range, [-1, 1]
    "gap_scaled",  # overnight log gap / trailing vol
    "volume_z",  # log volume vs its own trailing mean/std
)
N_CHANNELS: Final = len(CHANNEL_NAMES)

_EPS: Final = 1e-12


@dataclass(frozen=True)
class Bars:
    """Raw daily OHLCV series, ascending by date."""

    dates: list[date]
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray

    def __len__(self) -> int:
        return len(self.dates)


@dataclass(frozen=True)
class Dataset:
    """Model-ready tensors.

    ``x[i]`` has shape ``(window, N_CHANNELS)`` and is built from bars up to
    and including ``origin_index[i]``. ``y[i]`` is the triple-barrier label
    resolved over the days AFTER that origin. ``date[i]`` is the origin's
    date — the last day whose information the sample is allowed to use.
    """

    x: FloatArray
    y: IntArray
    dates: list[date]
    origin_index: IntArray
    window: int
    horizon: int
    bars: Bars

    def __len__(self) -> int:
        return int(self.x.shape[0])

    @property
    def tradable(self) -> npt.NDArray[np.bool_]:
        """Mask of samples whose outcome was an actual barrier touch."""
        return np.asarray(self.y != NEUTRAL, dtype=np.bool_)


def load_bars(path: Path) -> Bars:
    """Read a TSLA CSV into ascending, validated daily bars.

    Accepts either layout found in ``data/Tesla`` — the leading unnamed
    index column of the V2 file and the ``Adj Close`` column of the other
    are both ignored. Raises on the data faults that would silently poison
    a study: duplicate or unsorted dates, non-positive prices, incoherent
    OHLC bars.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no data rows")

    required = ("Date", "Open", "High", "Low", "Close", "Volume")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise ValueError(f"{path} is missing column(s): {', '.join(missing)}")

    dates = [date.fromisoformat(r["Date"].strip()[:10]) for r in rows]
    if any(b <= a for a, b in zip(dates, dates[1:], strict=False)):
        raise ValueError(f"{path} dates are not strictly increasing (duplicates or out of order)")

    def column(name: str) -> FloatArray:
        return np.asarray([float(r[name]) for r in rows], dtype=np.float64)

    bars = Bars(
        dates=dates,
        open=column("Open"),
        high=column("High"),
        low=column("Low"),
        close=column("Close"),
        volume=column("Volume"),
    )

    prices = np.stack([bars.open, bars.high, bars.low, bars.close])
    if not np.all(prices > 0.0):
        raise ValueError(f"{path} contains non-positive prices")
    incoherent = (bars.high < np.maximum(bars.open, bars.close)) | (
        bars.low > np.minimum(bars.open, bars.close)
    )
    if bool(incoherent.any()):
        first = dates[int(np.argmax(incoherent))]
        raise ValueError(f"{path} has incoherent OHLC bars (first: {first})")
    if not np.all(bars.volume >= 0.0):
        raise ValueError(f"{path} contains negative volume")
    return bars


def trailing_volatility(close: FloatArray, span: int) -> FloatArray:
    """Std-dev of log returns over the ``span`` bars strictly before each index.

    ``out[t]`` uses returns from ``t-span`` .. ``t-1`` inclusive, so it is a
    constant that was already knowable at the open of day ``t``. Leading
    entries without a full window are NaN and their samples get dropped.
    """
    if span < 2:
        raise ValueError("span must be >= 2")
    n = close.size
    log_ret = np.full(n, np.nan, dtype=np.float64)
    log_ret[1:] = np.log(close[1:] / close[:-1])

    out = np.full(n, np.nan, dtype=np.float64)
    for t in range(span + 1, n):
        window = log_ret[t - span : t]
        out[t] = float(np.std(window, ddof=1))
    return out


def build_features(bars: Bars, vol_span: int = 20, volume_span: int = 60) -> FloatArray:
    """Build the ``(n_bars, N_CHANNELS)` causal feature matrix.

    Rows whose scaling statistics are not yet defined come out as NaN and
    are excluded downstream — never imputed, because imputing a trailing
    statistic is a quiet way to smuggle in future information.
    """
    n = len(bars)
    vol = trailing_volatility(bars.close, vol_span)

    log_ret = np.full(n, np.nan, dtype=np.float64)
    log_ret[1:] = np.log(bars.close[1:] / bars.close[:-1])

    gap = np.full(n, np.nan, dtype=np.float64)
    gap[1:] = np.log(bars.open[1:] / bars.close[:-1])

    prev_close = np.full(n, np.nan, dtype=np.float64)
    prev_close[1:] = bars.close[:-1]

    day_range = bars.high - bars.low
    ret_scaled = log_ret / (vol + _EPS)
    gap_scaled = gap / (vol + _EPS)
    range_scaled = (day_range / (prev_close + _EPS)) / (vol + _EPS)
    body = (bars.close - bars.open) / (day_range + _EPS)
    close_loc = 2.0 * (bars.close - bars.low) / (day_range + _EPS) - 1.0

    log_volume = np.log(bars.volume + 1.0)
    volume_z = np.full(n, np.nan, dtype=np.float64)
    for t in range(volume_span + 1, n):
        window = log_volume[t - volume_span : t]
        sigma = float(np.std(window, ddof=1))
        volume_z[t] = (log_volume[t] - float(np.mean(window))) / (sigma + _EPS)

    features = np.stack([ret_scaled, range_scaled, body, close_loc, gap_scaled, volume_z], axis=1)
    return np.asarray(features, dtype=np.float64)


def triple_barrier_labels(
    bars: Bars, horizon: int, k_sigma: float, vol_span: int = 20
) -> tuple[IntArray, FloatArray]:
    """Label each bar by which volatility barrier is touched first.

    From the close of day ``t`` the barriers sit at ``close_t * exp(±k*sigma_t)``.
    Days ``t+1 .. t+horizon`` are scanned in order using each day's high and
    low. First touch wins; if a single day's range spans BOTH barriers we
    resolve it as NEUTRAL rather than guessing the intraday path, since the
    daily bar genuinely does not say which came first.

    Returns the labels and the barrier half-width used for each bar.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if k_sigma <= 0.0:
        raise ValueError("k_sigma must be > 0")

    n = len(bars)
    vol = trailing_volatility(bars.close, vol_span)
    width = k_sigma * vol
    labels = np.full(n, NEUTRAL, dtype=np.int64)

    for t in range(n):
        if not np.isfinite(width[t]) or t + horizon >= n:
            labels[t] = NEUTRAL
            continue
        upper = bars.close[t] * np.exp(width[t])
        lower = bars.close[t] * np.exp(-width[t])
        for s in range(t + 1, t + horizon + 1):
            hit_up = bars.high[s] >= upper
            hit_down = bars.low[s] <= lower
            if hit_up and hit_down:
                break  # ambiguous within one daily bar -> stays NEUTRAL
            if hit_up:
                labels[t] = UP
                break
            if hit_down:
                labels[t] = DOWN
                break
    return labels, width


def build_dataset(
    bars: Bars,
    window: int = 30,
    horizon: int = 5,
    k_sigma: float = 1.0,
    vol_span: int = 20,
    volume_span: int = 60,
) -> Dataset:
    """Assemble windows, labels and origin dates, dropping unusable rows.

    A sample at origin ``t`` needs: a complete finite feature window ending
    at ``t``, and ``horizon`` future bars in which its label could resolve.
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    features = build_features(bars, vol_span=vol_span, volume_span=volume_span)
    labels, _ = triple_barrier_labels(bars, horizon=horizon, k_sigma=k_sigma, vol_span=vol_span)

    n = len(bars)
    usable: list[int] = []
    for t in range(window - 1, n - horizon):
        block = features[t - window + 1 : t + 1]
        if np.all(np.isfinite(block)):
            usable.append(t)

    if not usable:
        raise ValueError("no usable samples: window/horizon too large for this series")

    origins = np.asarray(usable, dtype=np.int64)
    x = np.stack([features[t - window + 1 : t + 1] for t in usable]).astype(np.float64)
    y = labels[origins].astype(np.int64)
    return Dataset(
        x=x,
        y=y,
        dates=[bars.dates[t] for t in usable],
        origin_index=origins,
        window=window,
        horizon=horizon,
        bars=bars,
    )
