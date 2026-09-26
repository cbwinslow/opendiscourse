"""HTTP client for Congress.gov bill JSON. Nothing is read from disk."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..config import settings

ORIGIN = "https://api.congress.gov/v3"
USER_AGENT = "opendiscourse-research/congress-bills"
# Congress.gov allows 5,000 requests an hour. Stay under that.
PAUSE_SECONDS = 0.8
PARTS = ("actions", "committees", "subjects", "summaries", "cosponsors", "text")


class CongressBillClient:
    """GET bill list pages, one bill, and that bill's linked parts."""

    def __init__(self, *, origin: str = ORIGIN, http: httpx.Client | None = None, api_key: str | None = None) -> None:
        self._origin = origin.rstrip("/")
        self._http = http
        self._owns = http is None
        self._api_key = api_key if api_key is not None else settings.congress_api_key
        self._last = 0.0

    def close(self) -> None:
        """Close the client this object opened. A caller-supplied client stays open."""
        if self._owns and self._http is not None:
            self._http.close()
            self._http = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=60, follow_redirects=True)
        return self._http

    def _get(self, url: str) -> bytes:
        if not self._api_key:
            raise RuntimeError(
                "CONGRESS_API_KEY is not set. Congress.gov requires a key from api.congress.gov."
            )
        if self._owns:
            wait = PAUSE_SECONDS - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        last_error = "no response"
        for attempt in range(5):
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
                last_error = exc.__class__.__name__
                time.sleep(2 ** attempt)
                continue
            self._last = time.monotonic()
            if response.status_code == 200:
                return response.content
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                time.sleep(int(response.headers.get("retry-after", 2 ** attempt)))
                continue
            raise RuntimeError(f"Congress.gov refused {url.split('?', 1)[0]}: HTTP {response.status_code}")
        raise RuntimeError(f"Congress.gov did not answer {url.split('?', 1)[0]}: {last_error}")

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
