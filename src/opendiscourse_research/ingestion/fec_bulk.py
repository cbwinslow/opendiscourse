"""FEC bulk campaign-finance file discovery, registration, and staging.

Covers the FEC's own pre-aggregated pipe-delimited bulk files (one archive
per two-year cycle per family: individual contributions, committee-to-
committee/candidate transfers, operating expenditures, and other
transactions). This is a distinct product from the per-filing ``.fec``
format; it has no street-address detail but is the right shape for
district-level contribution/spending joins.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from psycopg.types.json import Jsonb

from ..capacity import RemoteObject, storage_preview
from ..db import connect
from .bulk import ArtifactSpec, register_local

DATASET_ID = "fec.campaign_finance"

# Confirmed live 2026-08-07 against the official mirror
# (https://www.fec.gov/files/bulk-downloads/{cycle}/{family}{yy}.zip):
# column counts have been stable across every 2000-2024 cycle checked for
# each family. oppexp.txt rows end with a trailing "|", which turns a naive
# split into 26 fields; the 26th is always empty, not a real column -- FEC's
# own file-description page lists 25 named columns.
FIELDS: dict[str, tuple[str, ...]] = {
    "indiv": (
        "cmte_id",
        "amndt_ind",
        "rpt_tp",
        "transaction_pgi",
        "image_num",
        "transaction_tp",
        "entity_tp",
        "name",
        "city",
        "state",
        "zip_code",
        "employer",
        "occupation",
        "transaction_dt",
        "transaction_amt",
        "other_id",
        "tran_id",
        "file_num",
        "memo_cd",
        "memo_text",
        "sub_id",
    ),
    "oth": (
        "cmte_id",
        "amndt_ind",
        "rpt_tp",
        "transaction_pgi",
        "image_num",
        "transaction_tp",
        "entity_tp",
        "name",
        "city",
        "state",
        "zip_code",
        "employer",
        "occupation",
        "transaction_dt",
        "transaction_amt",
        "other_id",
        "tran_id",
        "file_num",
        "memo_cd",
        "memo_text",
        "sub_id",
    ),
    "pas2": (
        "cmte_id",
        "amndt_ind",
        "rpt_tp",
        "transaction_pgi",
        "image_num",
        "transaction_tp",
        "entity_tp",
        "name",
        "city",
        "state",
        "zip_code",
        "employer",
        "occupation",
        "transaction_dt",
        "transaction_amt",
        "other_id",
        "cand_id",
        "tran_id",
        "file_num",
        "memo_cd",
        "memo_text",
        "sub_id",
    ),
    "oppexp": (
        "cmte_id",
        "amndt_ind",
        "rpt_yr",
        "rpt_tp",
        "image_num",
        "line_num",
        "form_tp_cd",
        "sched_tp_cd",
        "name",
        "city",
        "state",
        "zip_code",
        "transaction_dt",
        "transaction_amt",
        "transaction_pgi",
        "purpose",
        "category",
        "category_desc",
        "memo_cd",
        "memo_text",
        "entity_tp",
        "sub_id",
        "file_num",
        "tran_id",
        "back_ref_tran_id",
    ),
}
INNER_MEMBER = {
    "indiv": "itcont.txt",
    "oth": "itoth.txt",
    "pas2": "itpas2.txt",
    "oppexp": "oppexp.txt",
}

# Legacy local cache: 50 official FEC bulk archives (~19.7 GiB), already
# downloaded, unregistered (see inventory/progress.yaml id `fecbulk`).
LEGACY_ROOT = Path("/mnt/storage/data-lake/government/fec_bulk_data")

_CYCLE_FILE = re.compile(r"^([a-z0-9]+?)(\d{2})\.zip$")


def parse_row(family: str, fields: list[str]) -> dict[str, str]:
    """Map one pipe-split bulk row onto its named schema, by family."""
    schema = FIELDS[family]
    if len(fields) not in (len(schema), len(schema) + 1):
        raise ValueError(
            f"{family} row has {len(fields)} fields, expected {len(schema)} "
            f"(or {len(schema) + 1} with a trailing empty artifact)"
        )
    return dict(zip(schema, fields, strict=False))


def discover_family(family: str, root: Path = LEGACY_ROOT) -> list[dict[str, Any]]:
    """List local cycle archives for one family, without opening or parsing them."""
    if family not in FIELDS:
        raise ValueError(f"Unknown FEC bulk family: {family!r}")
    found = []
    for path in sorted(root.glob(f"{family}[0-9][0-9].zip")):
        match = _CYCLE_FILE.match(path.name)
        if match is None or match.group(1) != family:
            continue
        yy = int(match.group(2))
        cycle = 2000 + yy
        found.append(
            {
                "family": family,
                "cycle": cycle,
                "path": path,
                "bytes": path.stat().st_size,
                "url": f"https://www.fec.gov/files/bulk-downloads/{cycle}/{path.name}",
            }
        )
    return found


def preview_family(family: str, root: Path = LEGACY_ROOT) -> dict[str, Any]:
    """Run the standard capacity gate against this family's local archives.

    No download happens (the files are already on disk); this measures the
    staging/database growth cost the same way a fresh bulk plan would.
    """
    entries = discover_family(family, root)
    objects = [RemoteObject(entry["url"], entry["bytes"], "local") for entry in entries]
    return storage_preview(objects, stage_multiplier=1.0, database_multiplier=1.5)


def register_family(
    family: str, root: Path = LEGACY_ROOT, update: Callable[[str], None] | None = None
) -> list[str]:
    """Checksum and register every local cycle archive for one family."""
    registered = []
    for entry in discover_family(family, root):
        if update:
            update(f"Registering FEC {family} {entry['cycle']}")
        spec = ArtifactSpec(
            dataset_id=DATASET_ID,
            artifact_key=f"fec-{family}-{entry['cycle']}",
            url=entry["url"],
            filename=f"{family}/{entry['path'].name}",
            metadata={"family": family, "cycle": entry["cycle"], "admission": "local"},
        )
        register_local(spec, entry["path"])
        registered.append(spec.artifact_key)
    return registered


def _registered_artifacts(conn: Any, family: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT artifact_id, local_path, metadata FROM ingest.artifact "
            "WHERE dataset_id = %s AND metadata->>'family' = %s AND status IN ('downloaded', 'skipped') "
            "ORDER BY (metadata->>'cycle')::int",
            (DATASET_ID, family),
        )
        return cur.fetchall()


def stage_family(family: str, update: Callable[[str], None] | None = None) -> int:
    """Parse every registered artifact for one family into stage.fec_row."""
    if family not in FIELDS:
        raise ValueError(f"Unknown FEC bulk family: {family!r}")
    preview = preview_family(family)
    if not preview["approved"]:
        raise ValueError(
            f"FEC {family!r} capacity preview not approved: {preview['reason']}"
        )
    member = INNER_MEMBER[family]
    total = 0
    with connect() as conn:
        artifacts = _registered_artifacts(conn, family)
        if not artifacts:
            raise ValueError(
                f"No registered FEC {family!r} artifacts; run register_family first"
            )
        for artifact in artifacts:
            cycle = int(artifact["metadata"]["cycle"])
            if update:
                update(f"Staging FEC {family} {cycle}")
            rows: list[tuple[Any, ...]] = []
            with (
                ZipFile(Path(artifact["local_path"])) as archive,
                archive.open(member) as binary,
            ):
                for ordinal, raw_line in enumerate(binary, start=1):
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                    if not line:
                        continue
                    parsed = parse_row(family, line.split("|"))
                    rows.append(
                        (artifact["artifact_id"], family, cycle, ordinal, Jsonb(parsed))
                    )
                    if len(rows) == 5_000:
                        _insert(conn, rows)
                        total += len(rows)
                        rows = []
                if rows:
                    _insert(conn, rows)
                    total += len(rows)
            conn.commit()
    return total


def _insert(conn: Any, rows: list[tuple[Any, ...]]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO stage.fec_row (artifact_id, family, cycle, source_ordinal, raw) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
