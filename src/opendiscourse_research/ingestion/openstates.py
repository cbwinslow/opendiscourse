from __future__ import annotations

from datetime import date

from .bulk import ArtifactSpec, download


def download_monthly_dump(year: int, month: int, *, include_schema: bool = True, include_data: bool = False) -> list[str]:
    """Fetch the official OpenStates public pg_dump artifacts without restoring them."""
    period = date(year, month, 1)
    stamp = period.strftime("%Y-%m")
    specs = []
    if include_data:
        specs.append(ArtifactSpec(
            dataset_id="openstates.dump",
            artifact_key=f"data-{stamp}",
            url=f"https://data.openstates.org/postgres/monthly/{stamp}-public.pgdump",
            filename=f"openstates/{stamp}-public.pgdump",
            period_start=period,
            metadata={"kind": "data", "format": "pg_dump", "provider": "OpenStates"},
        ))
    if include_schema:
        specs.insert(0, ArtifactSpec(
            dataset_id="openstates.dump",
            artifact_key=f"schema-{stamp}",
            url=f"https://data.openstates.org/postgres/schema/{stamp}-schema.pgdump",
            filename=f"openstates/{stamp}-schema.pgdump",
            period_start=period,
            metadata={"kind": "schema", "format": "pg_dump", "provider": "OpenStates"},
        ))
    return [str(download(spec)) for spec in specs]
