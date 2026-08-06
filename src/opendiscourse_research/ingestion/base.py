from __future__ import annotations

import json
from contextlib import AbstractContextManager
from hashlib import sha256
from typing import Any, Self

import httpx

from ..db import connect


class IngestionRun(AbstractContextManager):
    def __init__(
        self, dataset_id: str, parameters: dict[str, Any], mode: str = "manual"
    ):
        self.dataset_id, self.parameters, self.mode = dataset_id, parameters, mode
        self.conn = None
        self.run_id = None
        self.record_count = 0
        self.status_override: str | None = None

    def mark_partial(self) -> None:
        """Record that this run completed against intentionally incomplete coverage."""
        self.status_override = "partial"

    def __enter__(self) -> Self:
        self.conn = connect()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest.run (dataset_id, mode, status, parameters) VALUES (%s, %s, 'running', %s) RETURNING run_id",
                (self.dataset_id, self.mode, json.dumps(self.parameters)),
            )
            self.run_id = cur.fetchone()["run_id"]
        self.conn.commit()
        return self

    def store_payload(self, response: httpx.Response, payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ingest.raw_payload (run_id, source_url, http_status, content_type, checksum_sha256, payload)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (run_id, checksum_sha256) DO UPDATE SET source_url = EXCLUDED.source_url
                   RETURNING payload_id""",
                (
                    self.run_id,
                    str(response.url),
                    response.status_code,
                    response.headers.get("content-type"),
                    sha256(canonical).hexdigest(),
                    json.dumps(payload),
                ),
            )
            payload_id = cur.fetchone()["payload_id"]
        self.conn.commit()
        return str(payload_id)

    def __exit__(self, exc_type, exc, tb) -> None:
        status = "failed" if exc else self.status_override or "succeeded"
        if exc:
            self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE ingest.run SET status = %s, finished_at = now(), record_count = %s, error_message = %s WHERE run_id = %s",
                (status, self.record_count, str(exc) if exc else None, self.run_id),
            )
        self.conn.commit()
        self.conn.close()


def client() -> httpx.Client:
    return httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "opendiscourse-research/0.1"},
    )


def json_response(response: httpx.Response) -> Any:
    """Reject provider HTML/error pages that incorrectly return a 2xx status."""
    # Provider clients commonly put API keys in query parameters. Never let an
    # httpx exception render the full request URL into a CLI traceback.
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        safe_url = str(response.url.copy_with(query=None))
        # Do not chain the original exception: httpx embeds the request URL in
        # it, which can include an API key.
        raise ValueError(
            f"Provider returned HTTP {response.status_code} for {safe_url}"
        ) from None
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        excerpt = response.text[:240].replace("\n", " ")
        raise ValueError(
            f"Expected JSON from {response.url}, got {content_type!r}: {excerpt}"
        )
    return response.json()
