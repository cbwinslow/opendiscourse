from __future__ import annotations

from pathlib import Path
import json
import typer

from .capacity import GiB, remote_size, storage_preview
from .catalog import sync_inventory, validate_inventory
from .browser import basket as catalog_basket, draft as catalog_draft, ensure_acs, facets as catalog_facets, launch as launch_browser, search as catalog_search, sync_acs
from .contracts import load_contracts, validate_contracts
from .db import apply_migrations
from .ingestion.census import STATE_FIPS, bootstrap_housing, describe_acs_table, discover_acs_tables, ingest_acs, plan_contract, review_bulk_contract, search_acs_tables
from .ingestion.congress import ingest_bill
from .ingestion.bulk import ArtifactSpec, register_local
from .ingestion.fred import ingest_manifest, ingest_series
from .ingestion.openstates import download_monthly_dump
from .ingestion.treasury import ingest_yield_curve
from .plans import due_plans, load_plans, run_plan
from .progress import load_progress, validate_progress

app = typer.Typer(help="Research database setup and ingestion commands.")
ingest_app = typer.Typer(help="Provider ingestion commands.")
bootstrap_app = typer.Typer(help="Resumable bulk download and bootstrap commands.")
catalog_app = typer.Typer(help="Browse provider offerings, select resources, and create review-only drafts.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(bootstrap_app, name="bootstrap")
app.add_typer(catalog_app, name="catalog")


@app.command("init-db")
def init_db() -> None:
    """Create schemas, extensions, and tables, then seed the dataset catalog."""
    errors = validate_inventory() + validate_progress() + validate_contracts()
    if errors:
        raise typer.BadParameter("Invalid inventory: " + "; ".join(errors))
    apply_migrations()
    sync_inventory()
    typer.echo("Database initialized and source inventory synchronized.")


@app.command("catalog-check")
def catalog_check() -> None:
    """Validate the version-controlled source inventory without connecting to Postgres."""
    errors = validate_inventory() + validate_progress() + validate_contracts()
    if errors:
        for error in errors:
            typer.echo(error)
        raise typer.Exit(1)
    typer.echo("Source inventory is valid.")


@app.command("progress-list")
def progress_list(state: str | None = typer.Option(None, help="Filter by progress state.")) -> None:
    """List the tracked dataset and legacy-artifact work register."""
    for item in load_progress()["items"]:
        if state is None or item["state"] == state:
            typer.echo(f"{item['id']}\t{item['state']}\t{item.get('dataset') or '-'}\t{item['next']}")


@app.command("progress-check")
def progress_check() -> None:
    """Validate the work register against the source catalog."""
    errors = validate_progress()
    if errors:
        for error in errors:
            typer.echo(error)
        raise typer.Exit(1)
    typer.echo("Progress register is valid.")


@app.command("contract-list")
def contract_list() -> None:
    """List short, version-controlled data selections."""
    for contract in load_contracts():
        typer.echo(f"{contract['id']}\t{contract['provider']}\t{contract['dataset']}\t{contract['target']}")


@app.command("storage-preview")
def storage_preview_command(
    url: list[str] = typer.Option(..., "--url", help="Remote artifact URL; repeat for every file in the planned batch."),
    stage_multiplier: float = typer.Option(1.0, min=0.0, help="Temporary stage size relative to downloads."),
    database_multiplier: float = typer.Option(1.5, min=0.0, help="Postgres size relative to downloads."),
    reserve_gib: int = typer.Option(100, min=1, help="Space that must remain free after the batch."),
) -> None:
    """Preview conservative raw, staging, and database space before a download."""
    report = storage_preview(
        [remote_size(item) for item in url],
        stage_multiplier=stage_multiplier,
        database_multiplier=database_multiplier,
        reserve_bytes=reserve_gib * GiB,
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))
    if not report["approved"]:
        raise typer.Exit(2)


@app.command("catalog-sync")
def catalog_sync(
    source: str = typer.Argument(..., help="Catalog adapter to sync; currently `acs`."),
    year: int = typer.Option(2024, min=2005),
) -> None:
    """Load a discovered provider catalog into reusable PostgreSQL resources."""
    if source != "acs":
        raise typer.BadParameter("Only `acs` is available today")
    typer.echo(f"Synchronized {sync_acs(year)} ACS resources.")


@app.command("catalog-search")
def catalog_search_command(
    text: str = typer.Option("", help="Search IDs, titles, and universes."),
    dataset: str = typer.Option("census.acs_5"),
    limit: int = typer.Option(50, min=1, max=500),
) -> None:
    """Search any synchronized provider catalog without contacting its provider."""
    typer.echo(json.dumps(catalog_search(dataset, text, limit), indent=2, sort_keys=True, default=str))


@app.command("catalog-basket")
def catalog_basket_command(
    name: str = typer.Option("default", help="Persistent selection basket name."),
) -> None:
    """Show resources selected in a persistent catalog basket."""
    typer.echo(json.dumps(catalog_basket(name), indent=2, sort_keys=True, default=str))


@app.command("catalog-options")
def catalog_options(dataset: str = typer.Option("census.acs_5")) -> None:
    """Show discovered years and product types before opening the browser."""
    typer.echo(json.dumps(catalog_facets(dataset), indent=2, sort_keys=True, default=str))


@app.command("catalog-draft")
def catalog_draft_command(name: str = typer.Option("default")) -> None:
    """Export a basket as a disabled, review-only contract draft."""
    typer.echo(catalog_draft(name))


@app.command("browse")
def browse(
    dataset: str | None = typer.Option(None, help="Start at one dataset, or omit to navigate providers."),
    basket: str = typer.Option("default", help="Persistent selection basket name."),
    year: int | None = typer.Option(None, help="Filter to one discovered release year."),
    product: str | None = typer.Option(None, help="Filter to one exact product type; see catalog-options."),
) -> None:
    """Open the keyboard catalog browser; Space selects and Enter inspects."""
    _catalog_ready()
    launch_browser(dataset, basket, year, product)


def _catalog_ready(year: int = 2024) -> None:
    """Small metadata bootstrap for the normal interactive path."""
    apply_migrations()
    sync_inventory()
    ensure_acs(year)


@catalog_app.command("browse")
def catalog_browse(
    basket: str = typer.Option("default", help="Persistent selection basket name."),
) -> None:
    """Open the source-first browser; current ACS metadata is prepared automatically."""
    _catalog_ready()
    launch_browser(None, basket)


@catalog_app.command("basket")
def catalog_basket_view(name: str = typer.Argument("default")) -> None:
    """Show one persistent selection basket."""
    typer.echo(json.dumps(catalog_basket(name), indent=2, sort_keys=True, default=str))


@catalog_app.command("draft")
def catalog_draft_view(name: str = typer.Argument("default")) -> None:
    """Write a disabled review-only draft from a basket."""
    typer.echo(catalog_draft(name))


@app.command("plan-list")
def plan_list() -> None:
    """List the small, version-controlled ingestion contracts."""
    for plan in load_plans():
        typer.echo(f"{plan['id']}\t{plan['cadence']}\t{plan['dataset']}\t{plan['handler']}")


@app.command("plan-run")
def plan_run(plan_id: str = typer.Argument(..., help="One-word plan ID from plan-list.")) -> None:
    """Execute one declared ingestion contract and retain its normal lineage."""
    typer.echo(f"Ingested {run_plan(plan_id)} records from {plan_id}.")


@app.command("plan-due")
def plan_due(dry_run: bool = typer.Option(False, help="Show due plans without contacting providers.")) -> None:
    """Run every contract due for refresh; intended for cron or a systemd timer."""
    plans = due_plans()
    if dry_run:
        for plan in plans:
            typer.echo(plan["id"])
        return
    for plan in plans:
        typer.echo(f"{plan['id']}: {run_plan(plan['id'])} records")


@ingest_app.command("census-acs")
def census_acs(
    year: int = typer.Option(...),
    state: str = typer.Option(..., help="Two-digit state FIPS code."),
    variables: str = typer.Option(..., help="Comma-separated Census variable IDs."),
    dataset: str = typer.Option("acs/acs5"),
) -> None:
    count = ingest_acs(year, state, variables.split(","), dataset)
    typer.echo(f"Ingested {count} ACS measurements.")


@ingest_app.command("census-plan")
def census_plan(
    contract: str = typer.Option(..., help="One-word Census contract ID, e.g. acshome."),
) -> None:
    """Discover selected Census metadata only; no observations are downloaded."""
    typer.echo(json.dumps(plan_contract(contract), indent=2, sort_keys=True))


@ingest_app.command("census-discover")
def census_discover(
    year: int = typer.Option(..., min=2005, help="ACS release year whose official table list should be cataloged."),
) -> None:
    """Catalog ACS table metadata and housing candidates; no ACS data is fetched."""
    typer.echo(json.dumps(discover_acs_tables(year), indent=2, sort_keys=True))


@ingest_app.command("census-review")
def census_review(
    contract: str = typer.Option(..., help="Draft ACS bulk contract ID, e.g. acshousing."),
) -> None:
    """Show the exact table IDs selected by a disabled ACS bulk contract."""
    typer.echo(json.dumps(review_bulk_contract(contract), indent=2, sort_keys=True))


@ingest_app.command("census-search")
def census_search(
    text: str = typer.Option(..., help="Words to find in the ID, title, universe, or product type."),
    year: int = typer.Option(2024, min=2005),
    product: str | None = typer.Option(None, help="Optional product filter, e.g. detailed or profile."),
    limit: int = typer.Option(50, min=1, max=500),
) -> None:
    """Search the local ACS table catalog without contacting Census."""
    typer.echo(json.dumps(search_acs_tables(year, text, product, limit), indent=2, sort_keys=True))


@ingest_app.command("census-table")
def census_table(
    table_id: str = typer.Option(..., "--id", help="ACS table ID, e.g. B25003."),
    year: int = typer.Option(2024, min=2005),
    all_fields: bool = typer.Option(False, "--all", help="Include Census annotation fields in addition to estimates and MOEs."),
) -> None:
    """Show official field-level metadata for one Detailed, Profile, or Subject table."""
    typer.echo(json.dumps(describe_acs_table(year, table_id, include_annotations=all_fields), indent=2, sort_keys=True))


@ingest_app.command("fred")
def fred(series_id: str = typer.Option(...)) -> None:
    typer.echo(f"Ingested {ingest_series(series_id)} FRED observations.")


@ingest_app.command("congress-bill")
def congress_bill(
    congress: int = typer.Option(...),
    bill_type: str = typer.Option(...),
    bill_number: int = typer.Option(...),
) -> None:
    typer.echo(f"Ingested {ingest_bill(congress, bill_type, bill_number)} bill record(s).")


@bootstrap_app.command("congress-bills")
def congress_bills(
    congress: int = typer.Option(..., min=1),
    max_records: int = typer.Option(250, min=1, help="Maximum bills to retrieve; use repeated runs for controlled backfills."),
    offset: int = typer.Option(0, min=0, help="Zero-based Congress.gov page offset; advance this for historical backfills."),
) -> None:
    """Ingest a bounded page sequence of Congress.gov bill metadata."""
    from .ingestion.congress import ingest_bills
    typer.echo(f"Ingested {ingest_bills(congress, max_records, offset=offset, mode='backfill')} bill records.")


@bootstrap_app.command("register")
def register(
    dataset: str = typer.Option(..., help="Existing catalog dataset ID, e.g. congress.legislation."),
    path: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, readable=True),
    key: str = typer.Option(..., help="Stable source-scoped artifact key; never reuse for a different file."),
    origin: str | None = typer.Option(None, help="Original publisher URL, or omit to retain the file URI."),
    note: str | None = typer.Option(None, help="Short provenance note; does not assert authenticity."),
) -> None:
    """Checksum and register one existing local artifact without copying or parsing it."""
    resolved = path.resolve()
    spec = ArtifactSpec(
        dataset_id=dataset,
        artifact_key=key,
        url=origin or resolved.as_uri(),
        filename=resolved.name,
        metadata={"admission": "local", "note": note} if note else {"admission": "local"},
    )
    typer.echo(register_local(spec, resolved))


@bootstrap_app.command("treasury-curve")
def treasury_curve(
    year: int = typer.Option(..., min=1990),
    curve_type: str = typer.Option("daily_treasury_yield_curve"),
) -> None:
    """Ingest every published tenor in a Treasury curve for one calendar year."""
    typer.echo(f"Ingested {ingest_yield_curve(year, curve_type)} Treasury curve measurements.")


@bootstrap_app.command("fred-core")
def fred_core(
    category: str | None = typer.Option(None, help="One manifest category, e.g. inflation or commodities."),
    max_priority: int = typer.Option(1, min=1, max=3),
) -> None:
    """Backfill curated FRED macro, rate, market, commodity, and FX series."""
    results = ingest_manifest(category=category, priority=max_priority)
    typer.echo(f"Ingested {len(results)} FRED series and {sum(results.values())} observations.")


@bootstrap_app.command("acs-housing")
def acs_housing(
    year: int = typer.Option(..., min=2009),
    states: str = typer.Option("", help="Comma-separated state FIPS codes; omit only with --nationwide."),
    nationwide: bool = typer.Option(False, help="Load all state/territory counties; this is a large job."),
) -> None:
    """Bootstrap the curated ACS 5-year county housing table groups."""
    if nationwide:
        selected = list(STATE_FIPS)
    elif states:
        selected = [state.strip() for state in states.split(",") if state.strip()]
    else:
        raise typer.BadParameter("Pass --states 24,51 or explicitly choose --nationwide")
    typer.echo(f"Ingested {bootstrap_housing(year, selected)} ACS housing measurements.")


@bootstrap_app.command("openstates-dump")
def openstates_dump(
    year: int = typer.Option(..., min=2010),
    month: int = typer.Option(..., min=1, max=12),
    schema: bool = typer.Option(True, help="Also download the matching schema archive."),
    data: bool = typer.Option(False, help="Download the large public data archive as well."),
) -> None:
    """Download and checksum the official OpenStates dump; do not restore it."""
    if not schema and not data:
        raise typer.BadParameter("Choose at least one of --schema or --data")
    for path in download_monthly_dump(year, month, include_schema=schema, include_data=data):
        typer.echo(path)


if __name__ == "__main__":
    app()
