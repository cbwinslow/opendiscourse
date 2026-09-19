from __future__ import annotations

import json
import os
import subprocess
from contextlib import AbstractContextManager
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Self

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from ..db import session
from ..models.ingest import raw_payload_table, run_table, run_target_table

_REPO = Path(__file__).resolve().parents[3]


@lru_cache
def code_version(repo: Path = _REPO) -> str:
    """Identify the code that ran: git SHA, ``-dirty`` with tracked edits, else ``unknown``.

    ``OPENDISCOURSE_CODE_VERSION`` overrides it for installs without a checkout.
    """
    if override := os.environ.get("OPENDISCOURSE_CODE_VERSION"):
        return override

    def git(*args: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    sha = git("rev-parse", "HEAD")
    if not sha:
        return "unknown"
    return f"{sha}-dirty" if git("status", "--porcelain", "--untracked-files=no") else sha


class IngestionRun(AbstractContextManager):
    def __init__(
        self, dataset_id: str, parameters: dict[str, Any], mode: str = "manual"
    ):
        self.dataset_id, self.parameters, self.mode = dataset_id, parameters, mode
        self.run_id = None
        self.record_count = 0
        self.status_override: str | None = None

    def mark_partial(self) -> None:
        """Record that this run completed against intentionally incomplete coverage."""
        self.status_override = "partial"

    def __enter__(self) -> Self:
        table = run_table()
        with session() as active_session:
            self.run_id = active_session.execute(
                insert(table)
                .values(
                    dataset_id=self.dataset_id,
                    mode=self.mode,
                    status="running",
                    parameters=self.parameters,
                    code_version=code_version(),
                )
                .returning(table.c.run_id)
            ).scalar_one()
        return self

    def record_target(
        self,
        target: str,
        coverage_key: str = "",
        *,
        inserted: int = 0,
        updated: int = 0,
        skipped: int = 0,
        status: str = "succeeded",
    ) -> None:
        """Record what this run wrote to ``target`` for one coverage slice.

        ``coverage_key`` names the slice (``congress=118``, ``cycle=2024``); blank
        means the whole target. Recording the same key again replaces the counts,
        so a retried step never double-counts.
        """
        table = run_target_table()
        statement = insert(table).values(
            run_id=self.run_id,
            target=target,
            coverage_key=coverage_key,
            status=status,
            rows_inserted=inserted,
            rows_updated=updated,
            rows_skipped=skipped,
        )
        with session() as active_session:
            active_session.execute(
                statement.on_conflict_do_update(
                    constraint="run_target_run_key_unique",
                    set_={
                        "status": statement.excluded.status,
                        "rows_inserted": statement.excluded.rows_inserted,
                        "rows_updated": statement.excluded.rows_updated,
                        "rows_skipped": statement.excluded.rows_skipped,
                        "recorded_at": func.now(),
                    },
                )
            )

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
