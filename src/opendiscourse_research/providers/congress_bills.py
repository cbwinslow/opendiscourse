"""HTTP client for Congress.gov bill JSON. Nothing is read from disk."""

from __future__ import annotations

import json
import threading
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, wait_exponential

from ..config import settings
from ..rate_gate import SharedRateGate
from .congress_api import (
    CongressRetryStop,
    CongressServerError,
    TransientCongressError,
    congress_gate,
)

ORIGIN = "https://api.congress.gov/v3"
USER_AGENT = "opendiscourse-research/congress-bills"
PARTS = ("actions", "committees", "subjects", "summaries", "cosponsors", "text")
# 20,000 requests an hour is about 6 a second. A slow reply needs many of those
# in flight at once, or the hour never fills.
HTTP_CONNECTIONS = 64


class CongressBillClient:
    """GET bill list pages, one bill, and that bill's linked parts."""

    def __init__(
        self,
        *,
        origin: str = ORIGIN,
        http: httpx.Client | None = None,
        api_key: str | None = None,
        gate: SharedRateGate | None = None,
    ) -> None:
        self._origin = origin.rstrip("/")
        self._http = http
        self._owns = http is None
        self._api_key = api_key if api_key is not None else settings.congress_api_key
        self._gate = gate if gate is not None else (congress_gate() if self._owns else None)
        self._client_lock = threading.Lock()

    def close(self) -> None:
        """Close the client this object opened. A caller-supplied client stays open."""
        if self._owns and self._http is not None:
            self._http.close()
            self._http = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            with self._client_lock:
                if self._http is None:
                    self._http = httpx.Client(
                        timeout=60,
                        follow_redirects=True,
                        limits=httpx.Limits(
                            max_connections=HTTP_CONNECTIONS,
                            max_keepalive_connections=HTTP_CONNECTIONS,
                        ),
                    )
        return self._http

    def _get(self, url: str) -> bytes:
        if not self._api_key:
            raise RuntimeError(
                "CONGRESS_API_KEY is not set. Congress.gov requires a key from api.congress.gov."
            )
        path = url.split("?", 1)[0]
        backoff = wait_exponential(multiplier=1, min=1, max=30)

        def wait(retry_state: Any) -> float:
            # The turnstile already waits out a 429. Without one, honor Retry-After, else back off.
            exc = retry_state.outcome.exception() if retry_state.outcome else None
            if isinstance(exc, TransientCongressError) and exc.delay > 0:
                return exc.delay
            if self._gate is not None:
                return 0
            return float(backoff(retry_state))

        try:
            for attempt in Retrying(
                retry=retry_if_exception_type(TransientCongressError),
                stop=CongressRetryStop(),
                wait=wait,
                reraise=True,
            ):
                with attempt:
                    return self._attempt(url)
        except TransientCongressError as exc:
            message = f"Congress.gov did not answer {path}: {exc}"
            # 429 and a dropped connection stop the run. A 5xx is one page, and the caller can go on.
            if str(exc).startswith("HTTP 5"):
                raise CongressServerError(message) from exc
            raise RuntimeError(message) from exc

    def _attempt(self, url: str) -> bytes:
        token = self._gate.acquire() if self._gate is not None else None
        try:
            response = self._client().get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                    "X-Api-Key": self._api_key,
                },
            )
        except httpx.HTTPError as exc:
            if self._gate is not None and token is not None:
                self._gate.release(token)
            raise TransientCongressError(exc.__class__.__name__) from exc
        if self._gate is not None and token is not None:
            self._gate.observe(token, response.status_code, response.headers)
        if response.status_code == 200:
            return response.content
        path = url.split("?", 1)[0]
        if response.status_code == 429 or response.status_code >= 500:
            delay = 0.0
            if self._gate is None:
                raw = response.headers.get("retry-after", "")
                delay = float(raw) if str(raw).isdigit() else 0.0
            raise TransientCongressError(
                f"HTTP {response.status_code}",
                delay=delay,
                throttle=response.status_code == 429,
            )
        raise RuntimeError(f"Congress.gov refused {path}: HTTP {response.status_code}")

    def list_page(self, congress: int, offset: int, limit: int = 250) -> bytes:
        """One page of the bill list. The body is the evidence."""
        return self._get(
            f"{self._origin}/bill/{congress}?offset={offset}&limit={limit}&format=json"
        )

    def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
        """One bill JSON document. A long list is followed and kept as one file."""
        slug = bill_type.lower()
        if name == "detail":
            path = f"/bill/{congress}/{slug}/{number}"
        else:
            path = f"/bill/{congress}/{slug}/{number}/{name}"
        url: str | None = f"{self._origin}{path}?limit=250&format=json"
        pages: list[dict[str, Any]] = []
        while url and len(pages) < 40:
            pages.append(json.loads(self._get(url).decode("utf-8")))
            pagination = pages[-1].get("pagination")
            nxt = pagination.get("next") if isinstance(pagination, dict) else None
            url = nxt if isinstance(nxt, str) else None
        if len(pages) == 1:
            return json.dumps(pages[0]).encode()
        combined = dict(pages[0])
        for page in pages[1:]:
            for key, value in page.items():
                if isinstance(value, list) and isinstance(combined.get(key), list):
                    combined[key].extend(value)
        return json.dumps(combined).encode()

    @staticmethod
    def url_for(congress: int, bill_type: str, number: str, name: str, *, origin: str = ORIGIN) -> str:
        """The URL stored with the artifact. The API key is not part of it."""
        slug = bill_type.lower()
        path = f"/bill/{congress}/{slug}/{number}" if name == "detail" else f"/bill/{congress}/{slug}/{number}/{name}"
        return f"{origin.rstrip('/')}{path}?format=json"
