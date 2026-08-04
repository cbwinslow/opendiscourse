from __future__ import annotations

from pathlib import Path
import json
import typer
import yaml

from .capacity import GiB, remote_size, storage_preview
from .catalog import sync_inventory, validate_inventory
from .browser import (
    basket as catalog_basket,
    draft as catalog_draft,
    ensure_acs,
    facets as catalog_facets,
    launch as launch_browser,
    search as catalog_search,
    sync_acs,
)
from .contracts import load_contracts, validate_contracts
from .db import apply_migrations
from .ingestion.acs_bulk import preview_acs5_bulk_plan, write_acs5_bulk_plan
from .ingestion.cbp_bulk import preview_cbp_bulk_plan, write_cbp_bulk_plan
from .ingestion.cbp_load import load_cbp, stage_cbp
from .ingestion.census import (
    STATE_FIPS,
    bootstrap_housing,
    describe_acs_table,
    discover_acs_tables,
    ingest_acs,
    plan_contract,
    review_bulk_contract,
    search_acs_tables,
)
from .ingestion.congress import ingest_bill
from .ingestion.bulk import ArtifactSpec, approve_plan, download_plan, register_local
from .ingestion.fred import ingest_manifest, ingest_series
from .ingestion.openstates import download_monthly_dump
from .ingestion.treasury import ingest_yield_curve
from .plans import due_plans, load_plans, run_plan
from .progress import load_progress, validate_progress
from .registry import status as registry_status, sync as registry_sync
from .feedback import (
    progress as render_progress,
    spinner as render_spinner,
    timed as render_timed,
)
from .audit import audit_leg
from .legvalidate import validate_billstatus
from .govplan import plan_billstatus_backfill
from .govbackfill import backfill_billstatus_missing
from .legreconcile import reconcile_billstatus
from .legload import load_billstatus
from .congresshealth import congressional_health, recover_stale_congressional_runs
from .votereconcile import reconcile_openstates_votes
from .peopleload import (
    load_openstates_federal_organizations,
    load_openstates_federal_people,
    load_openstates_votes,
)

app = typer.Typer(help="Research database setup and ingestion commands.")
ingest_app = typer.Typer(help="Provider ingestion commands.")
bootstrap_app = typer.Typer(help="Resumable bulk download and bootstrap commands.")
catalog_app = typer.Typer(
    help="Browse provider offerings, select resources, and create review-only drafts."
)
app.add_typer(ingest_app, name="ingest", hidden=True)
app.add_typer(bootstrap_app, name="bootstrap", hidden=True)
# Compatibility entry point for earlier scripts. The normal operator surface is
# intentionally just `browse`, `sync`, and `status`.
app.add_typer(catalog_app, name="catalog", hidden=True)


@app.command("init-db")
def init_db() -> None:
    """Create schemas, extensions, and tables, then seed the dataset catalog."""
    errors = validate_inventory() + validate_progress() + validate_contracts()
    if errors:
        raise typer.BadParameter("Invalid inventory: " + "; ".join(errors))
    apply_migrations()
    sync_inventory()
    typer.echo("Database initialized and source inventory synchronized.")


@app.command("catalog-check", hidden=True)
def catalog_check() -> None:
    """Validate the version-controlled source inventory without connecting to Postgres."""
    errors = validate_inventory() + validate_progress() + validate_contracts()
    if errors:
        for error in errors:
            typer.echo(error)
        raise typer.Exit(1)
    typer.echo("Source inventory is valid.")


@app.command("progress-list", hidden=True)
def progress_list(
    state: str | None = typer.Option(None, help="Filter by progress state."),
) -> None:
    """List the tracked dataset and legacy-artifact work register."""
    for item in load_progress()["items"]:
        if state is None or item["state"] == state:
            typer.echo(
                f"{item['id']}\t{item['state']}\t{item.get('dataset') or '-'}\t{item['next']}"
            )


@app.command("progress-check", hidden=True)
def progress_check() -> None:
    """Validate the work register against the source catalog."""
    errors = validate_progress()
    if errors:
        for error in errors:
            typer.echo(error)
        raise typer.Exit(1)
    typer.echo("Progress register is valid.")


@app.command("contract-list", hidden=True)
def contract_list() -> None:
    """List short, version-controlled data selections."""
    for contract in load_contracts():
        typer.echo(
            f"{contract['id']}\t{contract['provider']}\t{contract['dataset']}\t{contract['target']}"
        )


@app.command("storage-preview", hidden=True)
def storage_preview_command(
    url: list[str] = typer.Option(
        ...,
        "--url",
        help="Remote artifact URL; repeat for every file in the planned batch.",
    ),
    stage_multiplier: float = typer.Option(
        1.0, min=0.0, help="Temporary stage size relative to downloads."
    ),
    database_multiplier: float = typer.Option(
        1.5, min=0.0, help="Postgres size relative to downloads."
    ),
    reserve_gib: int = typer.Option(
        100, min=1, help="Space that must remain free after the batch."
    ),
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


@app.command("catalog-sync", hidden=True)
def catalog_sync(
    source: str = typer.Argument(..., help="Catalog adapter to sync; currently `acs`."),
    year: int = typer.Option(2024, min=2005),
) -> None:
    """Load a discovered provider catalog into reusable PostgreSQL resources."""
    if source != "acs":
        raise typer.BadParameter("Only `acs` is available today")
    typer.echo(f"Synchronized {sync_acs(year)} ACS resources.")


@app.command("catalog-search", hidden=True)
def catalog_search_command(
    text: str = typer.Option("", help="Search IDs, titles, and universes."),
    dataset: str = typer.Option("census.acs_5"),
    limit: int = typer.Option(50, min=1, max=500),
) -> None:
    """Search any synchronized provider catalog without contacting its provider."""
    typer.echo(
        json.dumps(
            catalog_search(dataset, text, limit), indent=2, sort_keys=True, default=str
        )
    )


@app.command("catalog-basket", hidden=True)
def catalog_basket_command(
    name: str = typer.Option("default", help="Persistent selection name."),
) -> None:
    """Show resources selected in a persistent catalog basket."""
    typer.echo(json.dumps(catalog_basket(name), indent=2, sort_keys=True, default=str))


@app.command("catalog-options", hidden=True)
def catalog_options(dataset: str = typer.Option("census.acs_5")) -> None:
    """Show discovered years and product types before opening the browser."""
    typer.echo(
        json.dumps(catalog_facets(dataset), indent=2, sort_keys=True, default=str)
    )


@app.command("catalog-draft", hidden=True)
def catalog_draft_command(name: str = typer.Option("default")) -> None:
    """Export a basket as a disabled, review-only contract draft."""
    typer.echo(catalog_draft(name))


@app.command("browse")
def browse(
    dataset: str | None = typer.Option(
        None, help="Start at one dataset, or omit to navigate providers."
    ),
    selection: str = typer.Option(
        "default", "--selection", "--basket", help="Persistent selection name."
    ),
    year: int | None = typer.Option(
        None, help="Filter to one discovered release year."
    ),
    product: str | None = typer.Option(
        None, help="Filter to one exact product type; normally choose it interactively."
    ),
    debug: bool = typer.Option(
        False,
        help="Write opt-in navigation diagnostics to lake metadata; search text is excluded.",
    ),
) -> None:
    """Open the keyboard catalog browser; Space selects and Enter inspects."""
    _catalog_ready()
    launch_browser(dataset, selection, year, product, debug)


def _catalog_ready(year: int = 2024) -> None:
    """Small metadata bootstrap for the normal interactive path."""
    apply_migrations()
    sync_inventory()
    registry_sync()


@app.command("sync")
def sync_command(
    refresh: bool = typer.Option(
        False,
        help="Re-read implemented provider metadata even when a local snapshot exists.",
    ),
    source: list[str] = typer.Option(
        [],
        "--source",
        help="Limit sync to an implemented source: acs, census, fred, or congress.",
    ),
    full: bool = typer.Option(
        False, help="Use a provider's explicit full-catalog mode; currently FRED only."
    ),
    preview: bool = typer.Option(
        False, help="Count a full catalog without storing resources; requires --full."
    ),
    index: bool = typer.Option(
        False,
        help="Run a bounded, resumable metadata-index batch; currently FRED only.",
    ),
    pages: int = typer.Option(
        1, min=1, max=20, help="FRED release-series pages to index when using --index."
    ),
    minutes: int | None = typer.Option(
        None,
        min=1,
        max=720,
        help="Run FRED indexing for this time budget instead of a page count.",
    ),
) -> None:
    """Refresh every implemented provider metadata catalog; never download bulk data."""
    apply_migrations()
    sync_inventory()
    if preview and not full:
        raise typer.BadParameter("--preview requires --full")
    if full and set(source) != {"fred"}:
        raise typer.BadParameter("full catalog mode requires exactly --source fred")
    if index and set(source) != {"fred"}:
        raise typer.BadParameter("metadata indexing requires exactly --source fred")
    if index and (full or preview):
        raise typer.BadParameter("use either --index or --full, not both")
    if minutes is not None and not index:
        raise typer.BadParameter("--minutes requires --index")
    if index and minutes is not None:
        with render_timed("Indexing FRED metadata", minutes * 60) as report:
            result = registry_sync(
                refresh, set(source), full, preview, None, minutes * 60, report
            )
    elif index:
        with render_progress("Preparing FRED metadata index", pages) as report:
            result = registry_sync(
                refresh, set(source), full, preview, pages, None, report
            )
    else:
        result = registry_sync(refresh, set(source) or None, full, preview)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("status")
def status_command() -> None:
    """Show each provider/dataset and whether its browser adapter is ready."""
    apply_migrations()
    sync_inventory()
    typer.echo(json.dumps(registry_status(), indent=2, sort_keys=True, default=str))


@app.command("audit")
def audit_command(
    hashes: bool = typer.Option(
        False,
        "--hashes",
        help="Also calculate SHA-256 checksums; slower but still read-only.",
    ),
) -> None:
    """Inventory known Congressional/GovInfo legacy roots without changing source files."""
    with render_spinner("Scanning legislative legacy artifacts") as report:
        result = audit_leg(hash_files=hashes, report=report)
    typer.echo(
        json.dumps(
            {
                "summary": result["summary"],
                "roots": result["roots"],
                "report": result["report"],
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("validate")
def validate_command(
    dataset: str = typer.Argument(
        "billstatus", help="Read-only validator; currently billstatus."
    ),
    sample: int = typer.Option(
        2, min=1, max=20, help="XML files to parse from each archive."
    ),
    official: bool = typer.Option(
        False,
        help="Compare one Congress's cached listing files to live GovInfo directory JSON.",
    ),
    congress: int | None = typer.Option(
        None, min=1, max=119, help="Congress to compare when using --official."
    ),
    all_congresses: bool = typer.Option(
        False,
        "--all",
        help="Compare every Congress available in the local BILLSTATUS cache.",
    ),
) -> None:
    """Validate a legacy collection before any artifact admission or ingestion."""
    if dataset != "billstatus":
        raise typer.BadParameter("only billstatus is available today")
    if official and congress is None and not all_congresses:
        raise typer.BadParameter("--official requires --congress or --all")
    if (congress is not None or all_congresses) and not official:
        raise typer.BadParameter("--congress and --all require --official")
    if congress is not None and all_congresses:
        raise typer.BadParameter("choose either --congress or --all")
    congresses = (
        (congress,)
        if congress is not None
        else tuple(range(108, 120))
        if all_congresses
        else ()
    )
    with render_spinner("Validating legacy GovInfo BILLSTATUS") as report:
        result = validate_billstatus(
            sample=sample, official_congresses=congresses, report=report
        )
    output = {"summary": result["summary"], "report": result["report"]}
    if "official_comparison" in result:
        output["official_comparison"] = result["official_comparison"]
    typer.echo(json.dumps(output, indent=2, sort_keys=True))


@app.command("plan")
def plan_command(
    dataset: str = typer.Argument(
        "billstatus", help="Review-only planner; currently billstatus."
    ),
    congress: int = typer.Option(119, min=1, max=119),
) -> None:
    """Create an exact disabled bulk backfill plan; never download its files."""
    if dataset != "billstatus":
        raise typer.BadParameter("only billstatus is available today")
    with render_spinner("Planning GovInfo BILLSTATUS backfill") as report:
        result = plan_billstatus_backfill(congress=congress, report=report)
    storage = dict(result["storage"])
    storage["object_count"] = len(storage.pop("objects", []))
    typer.echo(
        json.dumps(
            {
                "contract": result["contract"],
                "congress": result["congress"],
                "files": len(result["files"]),
                "storage": storage,
                "report": result["report"],
                "next": result["next"],
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("backfill-billstatus")
def backfill_billstatus_command(
    congress: int = typer.Option(119, min=1, max=119),
) -> None:
    """Download approved official BILLSTATUS XML into local ZIP archives."""
    with render_spinner("Backfilling approved GovInfo BILLSTATUS files") as report:
        result = backfill_billstatus_missing(congress, report)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("reconcile")
def reconcile_command(
    dataset: str = typer.Argument(
        "billstatus", help="Read-only reconciler; currently billstatus."
    ),
    congress: int = typer.Option(118, min=1, max=119),
    limit: int | None = typer.Option(
        None,
        min=1,
        help="Inspect at most this many XML bills; omit for the complete Congress.",
    ),
) -> None:
    """Compare validated BILLSTATUS identities to canonical Postgres bill keys without loading facts."""
    if dataset != "billstatus":
        raise typer.BadParameter("only billstatus is available today")
    with render_spinner("Reconciling validated GovInfo BILLSTATUS") as report:
        result = reconcile_billstatus(congress=congress, limit=limit, report=report)
    typer.echo(
        json.dumps(
            {
                "congress": congress,
                "summary": result["summary"],
                "groups": result["groups"],
                "malformed": len(result["malformed"]),
                "report": result["report"],
                "next": result["next"],
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("reconcile-openstates-votes")
def reconcile_openstates_votes_command(
    congress: int = typer.Option(118, min=1, max=119),
) -> None:
    """Reconcile OpenStates vote-event coverage with canonical roll calls."""
    typer.echo(
        json.dumps(reconcile_openstates_votes(congress), indent=2, sort_keys=True)
    )


@app.command("load-billstatus")
def load_billstatus_command(
    congress: int = typer.Option(118, min=1, max=119),
    limit: int | None = typer.Option(
        None,
        min=1,
        help="Maximum XML bills to load; omit only after a successful smoke load.",
    ),
    batch_size: int = typer.Option(
        500,
        min=1,
        max=5000,
        help="Bills per committed transaction; reruns are idempotent.",
    ),
    allow_partial: bool = typer.Option(
        False,
        help="Allow a validated but incomplete local cache, such as the 119th Congress.",
    ),
) -> None:
    """Load validated local GovInfo BILLSTATUS relationships with artifact lineage."""
    try:
        with render_spinner("Loading validated GovInfo BILLSTATUS") as report:
            result = load_billstatus(
                congress=congress,
                limit=limit,
                batch_size=batch_size,
                allow_partial=allow_partial,
                report=report,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("load-openstates-people")
def load_openstates_people_command() -> None:
    """Seed canonical federal people from the provisioned OpenStates snapshot."""
    with render_spinner("Loading OpenStates federal people baseline"):
        result = load_openstates_federal_people()
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("load-openstates-organizations")
def load_openstates_organizations_command() -> None:
    """Seed canonical federal organizations from the provisioned OpenStates snapshot."""
    with render_spinner("Loading OpenStates federal organization baseline"):
        result = load_openstates_federal_organizations()
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("load-openstates-votes")
def load_openstates_votes_command(
    congress: int = typer.Option(118, min=1, max=119),
    limit: int = typer.Option(
        1, min=1, help="Vote events to load; begin with a smoke batch."
    ),
) -> None:
    """Load bounded OpenStates congressional roll calls and member positions."""
    with render_spinner("Loading OpenStates congressional votes"):
        result = load_openstates_votes(congress, limit)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("congress-health")
def congress_health_command() -> None:
    """Write one read-only source-aware congressional ingestion health report."""
    typer.echo(json.dumps(congressional_health(), indent=2, sort_keys=True, default=str))


@app.command("recover-stale-congress-runs")
def recover_stale_congress_runs_command(
    older_than: str = typer.Option("6 hours", help="PostgreSQL interval threshold."),
) -> None:
    """Mark abandoned congressional runs failed with an explicit recovery reason."""
    typer.echo(json.dumps(recover_stale_congressional_runs(older_than), indent=2, default=str))


@catalog_app.command("browse", hidden=True)
def catalog_browse(
    basket: str = typer.Option("default", help="Persistent selection name."),
) -> None:
    """Open the source-first browser; current ACS metadata is prepared automatically."""
    _catalog_ready()
    launch_browser(None, basket)


@catalog_app.command("basket", hidden=True)
def catalog_basket_view(name: str = typer.Argument("default")) -> None:
    """Show one persistent selection basket."""
    typer.echo(json.dumps(catalog_basket(name), indent=2, sort_keys=True, default=str))


@catalog_app.command("draft", hidden=True)
def catalog_draft_view(name: str = typer.Argument("default")) -> None:
    """Write a disabled review-only draft from a basket."""
    typer.echo(catalog_draft(name))


@app.command("plan-list", hidden=True)
def plan_list() -> None:
    """List the small, version-controlled ingestion contracts."""
    for plan in load_plans():
        typer.echo(
            f"{plan['id']}\t{plan['cadence']}\t{plan['dataset']}\t{plan['handler']}"
        )


@app.command("plan-run", hidden=True)
def plan_run(
    plan_id: str = typer.Argument(..., help="One-word plan ID from plan-list."),
) -> None:
    """Execute one declared ingestion contract and retain its normal lineage."""
    typer.echo(f"Ingested {run_plan(plan_id)} records from {plan_id}.")


@app.command("plan-due", hidden=True)
def plan_due(
    dry_run: bool = typer.Option(
        False, help="Show due plans without contacting providers."
    ),
) -> None:
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
    contract: str = typer.Option(
        ..., help="One-word Census contract ID, e.g. acshome."
    ),
) -> None:
    """Discover selected Census metadata only; no observations are downloaded."""
    typer.echo(json.dumps(plan_contract(contract), indent=2, sort_keys=True))


@ingest_app.command("census-discover")
def census_discover(
    year: int = typer.Option(
        ...,
        min=2005,
        help="ACS release year whose official table list should be cataloged.",
    ),
) -> None:
    """Catalog ACS table metadata and housing candidates; no ACS data is fetched."""
    typer.echo(json.dumps(discover_acs_tables(year), indent=2, sort_keys=True))


@ingest_app.command("census-review")
def census_review(
    contract: str = typer.Option(
        ..., help="Draft ACS bulk contract ID, e.g. acshousing."
    ),
) -> None:
    """Show the exact table IDs selected by a disabled ACS bulk contract."""
    typer.echo(json.dumps(review_bulk_contract(contract), indent=2, sort_keys=True))


@ingest_app.command("acs-bulk-plan")
def acs_bulk_plan(
    basket: str = typer.Option(
        "default", help="Catalog selection containing 2022+ ACS 5-year Detailed Tables."
    ),
) -> None:
    """Write a disabled ACS table-based bulk plan from a browser selection."""
    path = write_acs5_bulk_plan(basket, catalog_basket(basket))
    typer.echo(path)


@ingest_app.command("acs-bulk-preview")
def acs_bulk_preview(
    plan: Path = typer.Option(
        ...,
        exists=True,
        dir_okay=False,
        help="Draft plan produced by the browser or acs-bulk-plan.",
    ),
) -> None:
    """Measure every planned ACS artifact; never download its contents."""
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_progress(
        "Measuring ACS bulk artifacts", len(payload.get("artifacts", []))
    ) as update:
        report = preview_acs5_bulk_plan(plan, update)
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@ingest_app.command("acs-bulk-approve")
def acs_bulk_approve(
    plan: Path = typer.Option(..., exists=True, dir_okay=False),
    geography: list[str] = typer.Option(..., help="Canonical geography types to load; repeat this option."),
) -> None:
    """Approve a previewed ACS plan with an explicit canonical geography scope."""
    typer.echo(json.dumps(approve_plan(plan, {"geography_types": geography}), indent=2, sort_keys=True))


@ingest_app.command("acs-bulk-download")
def acs_bulk_download(plan: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Resumably download an approved ACS plan and register immutable artifacts."""
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_progress("Downloading ACS bulk artifacts", len(payload.get("artifacts", []))) as update:
        result = download_plan(plan, update)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@ingest_app.command("cbp-bulk-plan")
def cbp_bulk_plan(
    basket: str = typer.Option(
        "default", help="Catalog selection containing one CBP complete bundle."
    ),
) -> None:
    """Write a disabled County Business Patterns bulk plan from a browser selection."""
    typer.echo(write_cbp_bulk_plan(basket, catalog_basket(basket)))


@ingest_app.command("cbp-bulk-preview")
def cbp_bulk_preview(
    plan: Path = typer.Option(..., exists=True, dir_okay=False),
) -> None:
    """Measure every planned CBP artifact; never download its contents."""
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_progress(
        "Measuring CBP bulk artifacts", len(payload.get("artifacts", []))
    ) as update:
        report = preview_cbp_bulk_plan(plan, update)
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@ingest_app.command("cbp-bulk-approve")
def cbp_bulk_approve(
    plan: Path = typer.Option(..., exists=True, dir_okay=False),
    geography: list[str] = typer.Option(..., help="Canonical geography levels to load; repeat this option."),
    naics_prefix: list[str] = typer.Option([], help="Optional NAICS prefixes to retain; repeat this option."),
) -> None:
    """Approve a previewed CBP plan with explicit geography and industry scope."""
    scope = {"geography_levels": geography, "naics_prefixes": naics_prefix or ["all"]}
    typer.echo(json.dumps(approve_plan(plan, scope), indent=2, sort_keys=True))


@ingest_app.command("cbp-bulk-download")
def cbp_bulk_download(plan: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Resumably download an approved CBP plan and register immutable artifacts."""
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_progress("Downloading CBP bulk artifacts", len(payload.get("artifacts", []))) as update:
        result = download_plan(plan, update)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@ingest_app.command("cbp-bulk-stage")
def cbp_bulk_stage(plan: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Stage approved, downloaded CBP source rows without altering facts."""
    apply_migrations()
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_spinner("Staging CBP source rows") as update:
        count = stage_cbp(payload, update)
    typer.echo(f"Staged {count} CBP source rows.")


@ingest_app.command("cbp-bulk-load")
def cbp_bulk_load(plan: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Load staged CBP rows into artifact-linked canonical business facts."""
    apply_migrations()
    payload = yaml.safe_load(plan.read_text()) or {}
    with render_spinner("Loading CBP business facts") as update:
        count = load_cbp(payload, update)
    typer.echo(f"Loaded {count} CBP business facts.")


@ingest_app.command("census-search")
def census_search(
    text: str = typer.Option(
        ..., help="Words to find in the ID, title, universe, or product type."
    ),
    year: int = typer.Option(2024, min=2005),
    product: str | None = typer.Option(
        None, help="Optional product filter, e.g. detailed or profile."
    ),
    limit: int = typer.Option(50, min=1, max=500),
) -> None:
    """Search the local ACS table catalog without contacting Census."""
    typer.echo(
        json.dumps(
            search_acs_tables(year, text, product, limit), indent=2, sort_keys=True
        )
    )


@ingest_app.command("census-table")
def census_table(
    table_id: str = typer.Option(..., "--id", help="ACS table ID, e.g. B25003."),
    year: int = typer.Option(2024, min=2005),
    all_fields: bool = typer.Option(
        False,
        "--all",
        help="Include Census annotation fields in addition to estimates and MOEs.",
    ),
) -> None:
    """Show official field-level metadata for one Detailed, Profile, or Subject table."""
    typer.echo(
        json.dumps(
            describe_acs_table(year, table_id, include_annotations=all_fields),
            indent=2,
            sort_keys=True,
        )
    )


@ingest_app.command("fred")
def fred(series_id: str = typer.Option(...)) -> None:
    typer.echo(f"Ingested {ingest_series(series_id)} FRED observations.")


@ingest_app.command("congress-bill")
def congress_bill(
    congress: int = typer.Option(...),
    bill_type: str = typer.Option(...),
    bill_number: int = typer.Option(...),
) -> None:
    typer.echo(
        f"Ingested {ingest_bill(congress, bill_type, bill_number)} bill record(s)."
    )


@bootstrap_app.command("congress-bills")
def congress_bills(
    congress: int = typer.Option(..., min=1),
    max_records: int = typer.Option(
        250,
        min=1,
        help="Maximum bills to retrieve; use repeated runs for controlled backfills.",
    ),
    offset: int = typer.Option(
        0,
        min=0,
        help="Zero-based Congress.gov page offset; advance this for historical backfills.",
    ),
) -> None:
    """Ingest a bounded page sequence of Congress.gov bill metadata."""
    from .ingestion.congress import ingest_bills

    typer.echo(
        f"Ingested {ingest_bills(congress, max_records, offset=offset, mode='backfill')} bill records."
    )


@bootstrap_app.command("register")
def register(
    dataset: str = typer.Option(
        ..., help="Existing catalog dataset ID, e.g. congress.legislation."
    ),
    path: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    key: str = typer.Option(
        ..., help="Stable source-scoped artifact key; never reuse for a different file."
    ),
    origin: str | None = typer.Option(
        None, help="Original publisher URL, or omit to retain the file URI."
    ),
    note: str | None = typer.Option(
        None, help="Short provenance note; does not assert authenticity."
    ),
) -> None:
    """Checksum and register one existing local artifact without copying or parsing it."""
    resolved = path.resolve()
    spec = ArtifactSpec(
        dataset_id=dataset,
        artifact_key=key,
        url=origin or resolved.as_uri(),
        filename=resolved.name,
        metadata={"admission": "local", "note": note}
        if note
        else {"admission": "local"},
    )
    typer.echo(register_local(spec, resolved))


@bootstrap_app.command("treasury-curve")
def treasury_curve(
    year: int = typer.Option(..., min=1990),
    curve_type: str = typer.Option("daily_treasury_yield_curve"),
) -> None:
    """Ingest every published tenor in a Treasury curve for one calendar year."""
    typer.echo(
        f"Ingested {ingest_yield_curve(year, curve_type)} Treasury curve measurements."
    )


@bootstrap_app.command("fred-core")
def fred_core(
    category: str | None = typer.Option(
        None, help="One manifest category, e.g. inflation or commodities."
    ),
    max_priority: int = typer.Option(1, min=1, max=3),
) -> None:
    """Backfill curated FRED macro, rate, market, commodity, and FX series."""
    results = ingest_manifest(category=category, priority=max_priority)
    typer.echo(
        f"Ingested {len(results)} FRED series and {sum(results.values())} observations."
    )


@bootstrap_app.command("acs-housing")
def acs_housing(
    year: int = typer.Option(..., min=2009),
    states: str = typer.Option(
        "", help="Comma-separated state FIPS codes; omit only with --nationwide."
    ),
    nationwide: bool = typer.Option(
        False, help="Load all state/territory counties; this is a large job."
    ),
) -> None:
    """Bootstrap the curated ACS 5-year county housing table groups."""
    if nationwide:
        selected = list(STATE_FIPS)
    elif states:
        selected = [state.strip() for state in states.split(",") if state.strip()]
    else:
        raise typer.BadParameter(
            "Pass --states 24,51 or explicitly choose --nationwide"
        )
    typer.echo(
        f"Ingested {bootstrap_housing(year, selected)} ACS housing measurements."
    )


@bootstrap_app.command("openstates-dump")
def openstates_dump(
    year: int = typer.Option(..., min=2010),
    month: int = typer.Option(..., min=1, max=12),
    schema: bool = typer.Option(
        True, help="Also download the matching schema archive."
    ),
    data: bool = typer.Option(
        False, help="Download the large public data archive as well."
    ),
) -> None:
    """Download and checksum the official OpenStates dump; do not restore it."""
    if not schema and not data:
        raise typer.BadParameter("Choose at least one of --schema or --data")
    for path in download_monthly_dump(
        year, month, include_schema=schema, include_data=data
    ):
        typer.echo(path)


if __name__ == "__main__":
    app()
