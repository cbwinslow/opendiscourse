"""One paced, retrying HTTP transport for public read-only sources.

Shared by the official-count lookups and the GovInfo BILLSTATUS client so pacing,
``Retry-After`` handling and the retry rule live in one place. A request is sent at
most twice: transport errors, 429 and 5xx are retried once; any other client error is
permanent and fails at once. The caller says how a failure is reported by passing an
``error`` factory ``(message, status) -> Exception``; ``status`` is None for
transport errors.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

Send = Callable[[str, str], httpx.Response]
MAX_RETRY_AFTER_SECONDS = 30
ATTEMPTS = 2


def retry_after_seconds(value: str, now: datetime | None = None) -> float | None:
    """Seconds a ``Retry-After`` header asks for (delta or HTTP-date), capped; None if unusable."""
    value = value.strip()
    if value.isdigit():
        return float(min(int(value), MAX_RETRY_AFTER_SECONDS))
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    wait = (when - (now or datetime.now(UTC))).total_seconds()
    return min(max(wait, 0.0), float(MAX_RETRY_AFTER_SECONDS))


class PacedClient:
    """Send requests no faster than ``pace_seconds`` apart, retrying transient failures once."""

    def __init__(
        self,
        send: Send,
        pace_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        error: Callable[[str, int | None], Exception] = lambda message, status: RuntimeError(message),
    ) -> None:
        self._send = send
        self._pace = pace_seconds
        self._sleep = sleep
        self._error = error
        self._last = 0.0

    def request(self, method: str, url: str) -> httpx.Response:
        """Pace, send, retry once on a transient failure, raise ``error`` on a permanent one."""
        last_error: Exception | None = None
        last_status: int | None = None
        for attempt in range(ATTEMPTS):
            wait = self._pace - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            try:
                response = self._send(method, url)
                self._last = time.monotonic()
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                self._last = time.monotonic()
                last_error = exc
                last_status = (
                    exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                )
                if last_status is not None and last_status < 500 and last_status != 429:
                    break  # a permanent client error will not improve
                if last_status == 429 and attempt + 1 < ATTEMPTS:
                    asked = retry_after_seconds(exc.response.headers.get("Retry-After", ""))  # type: ignore[union-attr]
                    if asked:
                        self._sleep(asked)
        raise self._error(f"{url}: {last_error}", last_status)
