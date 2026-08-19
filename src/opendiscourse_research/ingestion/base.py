from __future__ import annotations

import json
from contextlib import AbstractContextManager
from hashlib import sha256
from typing import Any, Self

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from ..db import connect, session
from ..models.ingest import raw_payload_table, run_table


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
        table = run_table()
        with session() as active_session:
            self.run_id = active_session.execute(
                insert(table)
                .values(
                    dataset_id=self.dataset_id,
                    mode=self.mode,
                    status="running",
                    parameters=self.parameters,
                )
                .returning(table.c.run_id)
            ).scalar_one()
        return self

    def store_payload(self, response: httpx.Response, payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        table = raw_payload_table()
        statement = insert(table).values(
            run_id=self.run_id,
            source_url=str(response.url),
            http_status=response.status_code,
            content_type=response.headers.get("content-type"),
            checksum_sha256=sha256(canonical).hexdigest(),
            payload=payload,
        )
        with session() as active_session:
            payload_id = active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(table.c.run_id, table.c.checksum_sha256),
                    set_={"source_url": statement.excluded.source_url},
                ).returning(table.c.payload_id)
            ).scalar_one()
        return str(payload_id)

    def __exit__(self, exc_type, exc, tb) -> None:
        status = "failed" if exc else self.status_override or "succeeded"
        if exc:
            self.conn.rollback()
        else:
            self.conn.commit()
        table = run_table()
        with session() as active_session:
            active_session.execute(
                table.update()
                .where(table.c.run_id == self.run_id)
                .values(
                    status=status,
                    finished_at=func.now(),
                    record_count=self.record_count,
                    error_message=str(exc) if exc else None,
                )
            )
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
