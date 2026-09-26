"""Shared Congress.gov HTTP entry: one key, one hourly allowance.

The Library of Congress README still says 5,000 requests an hour. api.data.gov
counts that hour on a rolling basis and reports the live ceiling in
``X-RateLimit-Limit``. This key has been answering 20,000, so that is the pace
until a response says otherwise. Every script that calls :func:`congress_gate`
or :func:`congress_get` shares one turnstile file under the data root.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from pathlib import Path

import httpx
from tenacity import Retrying, retry_if_exception_type, wait_none
from tenacity.stop import stop_base

from ..config import settings
from ..rate_gate import Clock, SharedRateGate, Sleeper

HOST = "api.congress.gov"
# Live header on this key. A response header replaces it, including a lower one.
FALLBACK_LIMIT = 20_000
WINDOW_SECONDS = 3600.0
SAFETY = 25
_SERVER_ATTEMPTS = 5
_THROTTLE_ATTEMPTS = 48


class CongressServerError(RuntimeError):
    """Congress.gov returned a server error after the retries were used up."""


class TransientCongressError(Exception):
    """Congress.gov failed in a way that is worth another try."""

    def __init__(self, message: str, *, delay: float = 0, throttle: bool = False) -> None:
        super().__init__(message)
        self.delay = delay
        self.throttle = throttle


class CongressRetryStop(stop_base):
    """Give a normal failure a few tries. A full hour may answer 429 many times."""

    def __call__(self, retry_state: object) -> bool:
        outcome = getattr(retry_state, "outcome", None)
        exc = outcome.exception() if outcome is not None else None
        limit = _THROTTLE_ATTEMPTS if getattr(exc, "throttle", False) else _SERVER_ATTEMPTS
        return int(getattr(retry_state, "attempt_number", 1)) >= limit


def congress_gate(
    *,
    path: Path | None = None,
    clock: Clock = time.time,
    sleep: Sleeper = time.sleep,
) -> SharedRateGate:
    """The turnstile every Congress.gov download on this machine shares."""
    directory = Path(settings.data_root) / "runtime" / "rate-gates"
    # One file per key, so two keys on this machine do not spend each other's hour.
    digest = hashlib.sha256((settings.congress_api_key or "").encode()).hexdigest()[:12]
    return SharedRateGate(
        path or directory / f"{HOST}.{digest}.json",
        fallback_limit=FALLBACK_LIMIT,
        window_seconds=WINDOW_SECONDS,
        safety=SAFETY,
        clock=clock,
        sleep=sleep,
    )


def congress_get(
    http: httpx.Client,
    url: str,
    *,
    params: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
    gate: SharedRateGate | None = None,
) -> httpx.Response:
    """GET one Congress.gov URL on the shared turnstile. The caller owns ``http``."""
    shared = gate or congress_gate()

    def once() -> httpx.Response:
        token = shared.acquire()
        try:
            response = http.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            shared.release(token)
            raise TransientCongressError(exc.__class__.__name__) from exc
        shared.observe(token, response.status_code, response.headers)
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientCongressError(
                f"HTTP {response.status_code}",
                throttle=response.status_code == 429,
            )
        return response

    try:
        for attempt in Retrying(
            retry=retry_if_exception_type(TransientCongressError),
            stop=CongressRetryStop(),
            wait=wait_none(),
            reraise=True,
        ):
            with attempt:
                return once()
    except TransientCongressError as exc:
        raise RuntimeError(f"Congress.gov did not answer {url.split('?', 1)[0]}: {exc}") from exc
