"""Polite JSON-over-HTTP client for the free public endpoints we depend on.

Every source used by this layer is a free, keyless, rate-limited public API.
Getting throttled or banned costs us the dataset, so the client is deliberately
conservative: a hard minimum interval between calls, exponential backoff on
429/5xx, and a bounded retry count. stdlib only — no new dependency for what
``urllib`` already does.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_USER_AGENT = "martex-quant-research/1.0 (+solana meme cohort study)"

# Status codes worth retrying: throttling and transient server faults.
_RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class RateLimitedJsonClient:
    """Sequential JSON fetcher that never issues calls faster than a fixed rate.

    Args:
        min_interval_s: Floor on the wall-clock gap between two requests.
        max_retries: Attempts after the first before giving up.
        backoff_base_s: First backoff sleep; doubles per attempt.
        timeout_s: Per-request socket timeout.
        accept: Value for the ``Accept`` header. GeckoTerminal wants a version
            pin here; DexScreener is happy with plain JSON.
    """

    def __init__(
        self,
        min_interval_s: float = 2.2,
        max_retries: int = 4,
        backoff_base_s: float = 3.0,
        timeout_s: float = 25.0,
        accept: str = "application/json",
    ) -> None:
        self._min_interval_s = min_interval_s
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._timeout_s = timeout_s
        self._accept = accept
        self._last_call_at: float = 0.0

    def _throttle(self) -> None:
        gap = time.monotonic() - self._last_call_at
        if gap < self._min_interval_s:
            time.sleep(self._min_interval_s - gap)

    def get(self, url: str) -> Any:
        """Fetch ``url`` and return the decoded JSON body.

        Raises the last error if every attempt fails, so callers can decide
        whether a source being down is fatal or skippable.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._throttle()
            request = urllib.request.Request(
                url, headers={"User-Agent": _USER_AGENT, "Accept": self._accept}
            )
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                    self._last_call_at = time.monotonic()
                    payload: Any = json.loads(response.read())
                    return payload
            except urllib.error.HTTPError as exc:
                self._last_call_at = time.monotonic()
                last_error = exc
                if exc.code not in _RETRY_STATUS:
                    raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                self._last_call_at = time.monotonic()
                last_error = exc

            if attempt < self._max_retries:
                sleep_s = self._backoff_base_s * (2**attempt)
                logger.warning(
                    "GET %s failed (%s); retry %d/%d in %.1fs",
                    url,
                    last_error,
                    attempt + 1,
                    self._max_retries,
                    sleep_s,
                )
                time.sleep(sleep_s)

        assert last_error is not None  # loop always records one before exhausting
        raise last_error
