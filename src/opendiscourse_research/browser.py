"""Provider-neutral catalog, selection basket, and optional terminal browser."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Any

import yaml

from psycopg.types.json import Jsonb

from .config import settings
from .db import connect
from .ingestion.base import client, json_response
from .providers.fred import search as search_fred
from .repositories.catalog import resource_ids


def _acs_manifest(year: int) -> Path:
    path = Path(settings.data_root).resolve().parent / "meta" / "acs" / str(year) / "tables.json"
    if not path.is_file():
        raise FileNotFoundError(f"No ACS manifest for {year}; run `research-db ingest census-discover --year {year}` first")
    return path


def sync_acs(year: int) -> int:
    """Promote a discovered ACS table list into the reusable SQL catalog."""
    manifest = json.loads(_acs_manifest(year).read_text())
    with connect() as conn, conn.cursor() as cur:
        for table in manifest["tables"]:
            cur.execute(
                """INSERT INTO catalog.resource
                   (dataset_id, resource_key, resource_type, title, summary, universe, release_year, metadata)
                   VALUES ('census.acs_5', %(key)s, %(type)s, %(title)s, %(summary)s, %(universe)s, %(year)s, %(metadata)s)
                   ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
                     resource_type = EXCLUDED.resource_type, title = EXCLUDED.title,
                     summary = EXCLUDED.summary, universe = EXCLUDED.universe,
                     release_year = EXCLUDED.release_year, metadata = EXCLUDED.metadata, updated_at = now()""",
                {
                    "key": f"{year}:{table['id']}", "type": table.get("product") or "ACS table",
                    "title": table["title"], "summary": table["title"], "universe": table.get("universe"), "year": year,
                    "metadata": Jsonb({"table_id": table["id"], "one_year": table.get("one_year"), "five_year": table.get("five_year")}),
                },
            )
        cur.execute(
            """SELECT artifact_id, remote_url, checksum_sha256
               FROM ingest.artifact WHERE dataset_id = 'census.acs_5' AND artifact_key = %s""",
            (f"tables-{year}",),
        )
        artifact = cur.fetchone()
        if artifact is None or artifact["checksum_sha256"] is None:
            raise ValueError(f"ACS table-list artifact for {year} is not registered")
        cur.execute(
            """INSERT INTO catalog.snapshot (dataset_id, source_url, checksum_sha256, artifact_id, metadata)
               VALUES ('census.acs_5', %s, %s, %s, %s)
               ON CONFLICT (dataset_id, checksum_sha256) DO UPDATE SET artifact_id = EXCLUDED.artifact_id
               RETURNING snapshot_id""",
            (artifact["remote_url"], artifact["checksum_sha256"], artifact["artifact_id"], Jsonb({"year": year, "kind": "acs_table_list"})),
        )
        snapshot_id = cur.fetchone()["snapshot_id"]
        cur.execute(
            """INSERT INTO catalog.snapshot_resource (snapshot_id, resource_id)
               SELECT %s, resource_id FROM catalog.resource
               WHERE dataset_id = 'census.acs_5' AND release_year = %s
               ON CONFLICT DO NOTHING""",
            (snapshot_id, year),
        )
        conn.commit()
    return len(manifest["tables"])


def ensure_acs(year: int = 2024) -> int:
    """Make the current ACS catalog available with no separate user setup step."""
    if not _acs_manifest(year).is_file():
        from .ingestion.census import discover_acs_tables
        discover_acs_tables(year)
    return sync_acs(year)


def _fred_manifest() -> tuple[Path, list[dict[str, Any]]]:
    path = Path(__file__).resolve().parents[2] / "inventory" / "core_fred_series.yaml"
    return path, yaml.safe_load(path.read_text())["series"]


def _fred_metadata(series_id: str) -> tuple[dict[str, Any], str | None]:
    """Fetch descriptive FRED metadata only; observations are never requested."""
    if not settings.fred_api_key:
        return {}, None
    with client() as http:
        response = http.get(
            "https://api.stlouisfed.org/fred/series",
            params={"series_id": series_id, "api_key": settings.fred_api_key, "file_type": "json"},
        )
    try:
        series = json_response(response).get("seriess", [])
    except ValueError as exc:
        return {}, str(exc)
    return (series[0] if series else {}), None


def sync_fred(refresh: bool = False) -> dict[str, Any]:
    """Publish the deliberate FRED series allow-list to the local catalog.

    The manifest is the catalog's authoritative selection boundary. A refresh
    augments it with provider descriptions, but no observation data is acquired.
    """
    path, series = _fred_manifest()
    enrich = refresh and bool(settings.fred_api_key)
    issues: list[str] = []
    with connect() as conn, conn.cursor() as cur:
        for entry in series:
            remote, issue = _fred_metadata(entry["series_id"]) if enrich else ({}, None)
            if issue:
                issues.append(entry["series_id"])
            metadata = {
                "series_id": entry["series_id"], "category": entry["category"],
                "priority": entry["priority"], "notes": entry.get("notes"),
                "provider": {
                    key: remote[key] for key in (
                        "observation_start", "observation_end", "frequency",
                        "frequency_short", "units", "units_short",
                        "seasonal_adjustment", "last_updated",
                    ) if key in remote
                },
            }
            if issue:
                metadata["provider_error"] = issue
            cur.execute(
                """INSERT INTO catalog.resource
                   (dataset_id, resource_key, resource_type, title, summary, metadata)
                   VALUES ('fred.series', %(key)s, %(type)s, %(title)s, %(summary)s, %(metadata)s)
                   ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
                     resource_type = EXCLUDED.resource_type, title = EXCLUDED.title,
                     summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()""",
                {
                    "key": entry["series_id"], "type": entry["category"],
                    "title": remote.get("title", entry["label"]),
                    "summary": remote.get("notes", entry.get("notes") or entry["label"]),
                    "metadata": Jsonb(metadata),
                },
            )
        checksum = sha256(path.read_bytes()).hexdigest()
        cur.execute(
            """INSERT INTO catalog.snapshot (dataset_id, source_url, checksum_sha256, metadata)
               VALUES ('fred.series', %s, %s, %s)
               ON CONFLICT (dataset_id, checksum_sha256) DO UPDATE SET metadata = EXCLUDED.metadata
               RETURNING snapshot_id""",
            (
                "https://api.stlouisfed.org/fred/series", checksum,
                Jsonb({"kind": "curated_series_manifest", "path": str(path), "enriched": enrich}),
            ),
        )
        snapshot_id = cur.fetchone()["snapshot_id"]
        cur.execute(
            """INSERT INTO catalog.snapshot_resource (snapshot_id, resource_id)
               SELECT %s, resource_id FROM catalog.resource WHERE dataset_id = 'fred.series'
               ON CONFLICT DO NOTHING""",
            (snapshot_id,),
        )
        conn.commit()
    return {
        "resources": len(series), "state": "synced", "enriched": enrich,
        "issues": issues,
    }


def _fred_get(endpoint: str, **params: Any) -> dict[str, Any]:
    if not settings.fred_api_key:
        raise ValueError("FRED_API_KEY is required for full FRED catalog discovery")
    # Full catalog discovery makes many small requests. Back off on the
    # provider's explicit rate signal rather than retrying aggressively.
    for attempt in range(5):
        with client() as http:
            response = http.get(
                f"https://api.stlouisfed.org/fred/{endpoint}",
                params={**params, "api_key": settings.fred_api_key, "file_type": "json"},
            )
        if response.status_code != 429:
            return json_response(response)
        if attempt == 4:
            return json_response(response)
        retry_after = response.headers.get("retry-after")
        try:
            delay = min(float(retry_after), 30.0) if retry_after else float(2 ** attempt)
        except ValueError:
            delay = float(2 ** attempt)
        sleep(delay)
    raise AssertionError("unreachable")


def _fred_categories() -> list[dict[str, Any]]:
    """Walk the official category tree once; no series are acquired here."""
    seen: set[int] = {0}
    pending = [0]
    categories: list[dict[str, Any]] = []
    while pending:
        parent_id = pending.pop()
        for category in _fred_get("category/children", category_id=parent_id).get("categories", []):
            category_id = int(category["id"])
            if category_id in seen:
                continue
            seen.add(category_id)
            categories.append(category)
            pending.append(category_id)
    return categories


def preview_fred_full() -> dict[str, Any]:
    """Count category memberships before a potentially large metadata crawl."""
    categories = _fred_categories()
    memberships = 0
    for category in categories:
        payload = _fred_get("category/series", category_id=category["id"], limit=1, offset=0)
        memberships += int(payload.get("count", 0))
    return {"state": "preview", "categories": len(categories), "series_memberships": memberships,
            "note": "Memberships include duplicates because one series can belong to multiple categories. No series metadata was stored."}


def sync_fred_full() -> dict[str, Any]:
    """Index all discoverable FRED series metadata; never request observations."""
    categories = _fred_categories()
    series: dict[str, dict[str, Any]] = {}
    memberships = 0
    for category in categories:
        offset = 0
        while True:
            payload = _fred_get("category/series", category_id=category["id"], limit=1000, offset=offset)
            page = payload.get("seriess", [])
            memberships += len(page)
            for item in page:
                entry = series.setdefault(item["id"], {**item, "categories": []})
                entry["categories"].append({"id": category["id"], "name": category["name"]})
            offset += len(page)
            if not page or offset >= int(payload.get("count", 0)):
                break
    canonical = json.dumps(series, sort_keys=True, separators=(",", ":")).encode()
    with connect() as conn, conn.cursor() as cur:
        for series_id, item in series.items():
            metadata = {key: item.get(key) for key in ("observation_start", "observation_end", "frequency", "frequency_short", "units", "units_short", "seasonal_adjustment", "last_updated", "popularity")}
            metadata.update({"series_id": series_id, "categories": item["categories"], "scope": "full"})
            cur.execute(
                """INSERT INTO catalog.resource (dataset_id, resource_key, resource_type, title, summary, metadata)
                   VALUES ('fred.series', %s, 'series', %s, %s, %s)
                   ON CONFLICT (dataset_id, resource_key) DO UPDATE SET resource_type = EXCLUDED.resource_type,
                     title = EXCLUDED.title, summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()""",
                (series_id, item.get("title", series_id), item.get("notes"), Jsonb(metadata)),
            )
        checksum = sha256(canonical).hexdigest()
        cur.execute(
            """INSERT INTO catalog.snapshot (dataset_id, source_url, checksum_sha256, metadata)
               VALUES ('fred.series', %s, %s, %s)
               ON CONFLICT (dataset_id, checksum_sha256) DO UPDATE SET metadata = EXCLUDED.metadata
               RETURNING snapshot_id""",
            ("https://api.stlouisfed.org/fred/category/series", checksum,
             Jsonb({"kind": "full_category_catalog", "categories": len(categories), "memberships": memberships, "resources": len(series)})),
        )
        snapshot_id = cur.fetchone()["snapshot_id"]
        cur.execute("""INSERT INTO catalog.snapshot_resource (snapshot_id, resource_id)
                       SELECT %s, resource_id FROM catalog.resource WHERE dataset_id = 'fred.series'
                       ON CONFLICT DO NOTHING""", (snapshot_id,))
        conn.commit()
    return {"state": "synced", "categories": len(categories), "series_memberships": memberships, "resources": len(series)}


def search(dataset_id: str, text: str = "", limit: int = 100, year: int | None = None, product: str | None = None) -> list[dict[str, Any]]:
    query = text.strip()
    terms = f"%{query}%"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT resource_id, resource_key, resource_type, title, universe, release_year, metadata
               FROM catalog.resource
               WHERE dataset_id = %s AND (%s = '' OR resource_key ILIKE %s OR title ILIKE %s OR summary ILIKE %s OR metadata::text ILIKE %s OR
                 to_tsvector('english', concat_ws(' ', resource_key, title, summary, universe, resource_type, metadata::text)) @@ websearch_to_tsquery('english', %s))
                 AND (%s::integer IS NULL OR release_year = %s) AND (%s::text IS NULL OR resource_type = %s)
               ORDER BY resource_key LIMIT %s""",
            (dataset_id, query, terms, terms, terms, terms, query, year, year, product, product, limit),
        )
        return cur.fetchall()


def facets(dataset_id: str) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT release_year, count(*) AS count FROM catalog.resource WHERE dataset_id = %s AND release_year IS NOT NULL GROUP BY release_year ORDER BY release_year DESC", (dataset_id,))
        years = cur.fetchall()
        cur.execute("SELECT resource_type, count(*) AS count FROM catalog.resource WHERE dataset_id = %s GROUP BY resource_type ORDER BY resource_type", (dataset_id,))
        products = cur.fetchall()
    # The ACS release choices are known even before each small table-list
    # workbook has been cached. Entering an uncached year can trigger metadata
    # discovery; it never downloads observations.
    if dataset_id == "census.acs_5":
        counts = {row["release_year"]: row["count"] for row in years}
        # Verified table-based catalog releases. Older ACS releases use a
        # different sequence-format catalog and need their own adapter.
        years = [{"release_year": year, "count": counts.get(year, 0)} for year in range(2024, 2021, -1)]
    return {"dataset": dataset_id, "years": years, "products": products}


def providers() -> list[dict[str, Any]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT provider_id, name FROM catalog.provider ORDER BY name")
        return cur.fetchall()


def datasets(provider_id: str) -> list[dict[str, Any]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT d.dataset_id, d.title, count(r.resource_id) AS resources
                     FROM catalog.dataset d LEFT JOIN catalog.resource r ON r.dataset_id = d.dataset_id
                     WHERE d.provider_id = %s GROUP BY d.dataset_id, d.title ORDER BY d.title""", (provider_id,))
        return cur.fetchall()


def get_resource(resource_id: str) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM catalog.resource WHERE resource_id = %s", (resource_id,))
        resource = cur.fetchone()
        if resource is None:
            raise ValueError(f"Unknown catalog resource {resource_id}")
        cur.execute("SELECT field_key, label, description, data_type, metadata FROM catalog.resource_field WHERE resource_id = %s ORDER BY field_key", (resource_id,))
        resource["fields"] = cur.fetchall()
        return resource


def upsert_fields(resource_id: str, fields: list[dict[str, Any]]) -> None:
    with connect() as conn, conn.cursor() as cur:
        for field in fields:
            cur.execute(
                """INSERT INTO catalog.resource_field (resource_id, field_key, label, description, data_type, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (resource_id, field_key) DO UPDATE SET label = EXCLUDED.label,
                     description = EXCLUDED.description, data_type = EXCLUDED.data_type, metadata = EXCLUDED.metadata,
                     discovered_at = now()""",
                (resource_id, field["id"], field.get("label"), field.get("concept"), field.get("type"), Jsonb({})),
            )
        conn.commit()


def _basket_id(name: str) -> str:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO catalog.basket (name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET updated_at = now()
               RETURNING basket_id""",
            (name,),
        )
        basket_id = str(cur.fetchone()["basket_id"])
        conn.commit()
        return basket_id


def toggle(name: str, resource_id: str) -> bool:
    """Toggle one resource in a persistent basket; return True when selected."""
    basket_id = _basket_id(name)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM catalog.basket_item WHERE basket_id = %s AND resource_id = %s", (basket_id, resource_id))
        if cur.fetchone():
            cur.execute("DELETE FROM catalog.basket_item WHERE basket_id = %s AND resource_id = %s", (basket_id, resource_id))
            selected = False
        else:
            cur.execute("INSERT INTO catalog.basket_item (basket_id, resource_id) VALUES (%s, %s)", (basket_id, resource_id))
            selected = True
        conn.commit()
        return selected


def basket(name: str) -> list[dict[str, Any]]:
    basket_id = _basket_id(name)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.resource_id, r.dataset_id, r.resource_key, r.resource_type, r.title, r.universe, r.release_year, b.added_at
               FROM catalog.basket_item b JOIN catalog.resource r ON r.resource_id = b.resource_id
               WHERE b.basket_id = %s ORDER BY r.dataset_id, r.resource_key""",
            (basket_id,),
        )
        return cur.fetchall()


def add_all(name: str, resource_ids: list[str]) -> int:
    basket_id = _basket_id(name)
    with connect() as conn, conn.cursor() as cur:
        for resource_id in resource_ids:
            cur.execute("INSERT INTO catalog.basket_item (basket_id, resource_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (basket_id, resource_id))
        conn.commit()
    return len(resource_ids)


def draft(name: str) -> Path:
    """Export a basket to a disabled, review-only contract draft in lake metadata."""
    items = basket(name)
    groups: dict[tuple[str, int | None, str], list[str]] = {}
    for item in items:
        groups.setdefault((item["dataset_id"], item["release_year"], item["resource_type"]), []).append(item["resource_key"])
    payload = {"version": 1, "state": "draft", "basket": name, "resources": [
        {"dataset": dataset, "year": year, "product": product, "keys": sorted(keys)}
        for (dataset, year, product), keys in sorted(groups.items())
    ], "next": "Review, resolve exact artifacts, pass storage preview, then create an approved version-controlled contract."}
    path = Path(settings.data_root).resolve().parent / "meta" / "drafts" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def launch(dataset_id: str = "census.acs_5", basket_name: str = "default", year: int | None = None, product: str | None = None, debug: bool = False) -> None:
    """Open the optional Textual UI, keeping the catalog API dependency-free."""
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.widgets import DataTable, Footer, Header, Input, Static
    except ImportError as exc:
        raise RuntimeError("Install the optional browser: `pip install -e '.[browser]'`") from exc

    class CatalogBrowser(App):
        TITLE = "OpenDiscourse Catalog"
        BINDINGS = [
            Binding("space", "toggle", "select / unselect"),
            Binding("a", "all", "select filtered"),
            Binding("g", "draft", "write draft"),
            Binding("p", "bulk_plan", "write bulk plan"),
            Binding("f", "fetch", "fetch provider search"),
            Binding("backspace", "back", "back"),
            Binding("c", "cart", "selection"),
            Binding("enter", "describe", "inspect fields"),
            Binding("o", "open", "open highlighted"),
            Binding("r", "refresh", "refresh"),
            Binding("ctrl+q", "quit", "quit"),
        ]
        CSS = """
        #query { margin: 1 1 0 1; }
        #grid { height: 1fr; margin: 1; }
        #detail { height: 12; border: round $accent; padding: 1; overflow: auto; }
        #help { height: 4; border: round $primary; padding: 0 1; margin: 0 1 1 1; }
        """

        def __init__(self) -> None:
            super().__init__()
            self.current_id: str | None = None
            self.rows: list[dict[str, Any]] = []
            self.level = "provider" if dataset_id is None else "resource"
            self.provider_id: str | None = None
            self.dataset_id: str | None = dataset_id
            self.year = year
            self.product = product
            self.confirm: str | None = None
            self.cart_origin = self.level
            self.trace_enabled = debug
            self.debug_path = Path(settings.data_root).resolve().parent / "meta" / "debug" / "tui.jsonl"

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Search IDs, titles, or universes…", id="query")
            yield DataTable(id="grid", cursor_type="row")
            yield Static("Loading catalog…", id="detail")
            yield Static("↑/↓ move  Enter or O open  Backspace back  Space select  C selection  F fetch FRED search  A select filtered  G write draft  R refresh  Ctrl+Q quit", id="help")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            table.focus()
            self.load_level()

        def _set_initial_row(self) -> None:
            """Focus the grid and make Enter useful before the first arrow key."""
            table = self.query_one(DataTable)
            if not self.rows:
                self.current_id = None
                return
            self.current_id = str(self.rows[0].get("resource_id") or self.rows[0].get("provider_id") or self.rows[0].get("dataset_id") or self.rows[0].get("release_year") or self.rows[0].get("resource_type"))
            table.move_cursor(row=0)
            table.focus()
            self._debug("screen_loaded", rows=len(self.rows))

        def _debug(self, event: str, **data: Any) -> None:
            """Append opt-in navigation diagnostics without recording search text."""
            if not self.trace_enabled:
                return
            self.debug_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"event": event, "level": self.level, "current_id": self.current_id, **data}
            with self.debug_path.open("a") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")

        def _help(self) -> str:
            """Render the controls relevant to the current navigation level."""
            common = "↑/↓ move  O or Enter open  Backspace back  C selection  R refresh  Ctrl+Q quit"
            if self.level in {"product", "year"}:
                return common + "  Space select highlighted group (press twice)"
            if self.level == "resource":
                extra = "Space select resource  A select filtered  G write draft  P bulk plan"
                if self.dataset_id == "fred.series":
                    extra += "  F focus FRED search; Enter fetches results"
                return common + "  " + extra
            return common

        def crumb(self) -> str:
            return " › ".join(item for item in [self.provider_id, self.dataset_id, str(self.year) if self.year else None, self.product, self.level] if item)

        def load_level(self) -> None:
            table = self.query_one(DataTable)
            query = self.query_one(Input)
            # Search is relevant only after a concrete dataset/product has
            # been chosen. Keeping it out of navigation makes the source-first
            # workflow immediately understandable.
            query.display = self.level == "resource"
            if self.level != "resource":
                query.value = ""
            self.query_one("#help", Static).update(self._help())
            table.clear(columns=True)
            self.rows = []
            if self.level == "provider":
                table.add_columns("Provider", "Name")
                self.rows = providers()
                for row in self.rows: table.add_row(row["provider_id"], row["name"], key=row["provider_id"])
            elif self.level == "dataset":
                table.add_columns("Dataset", "Title", "Cataloged")
                self.rows = datasets(self.provider_id or "")
                for row in self.rows: table.add_row(row["dataset_id"], row["title"], str(row["resources"]), key=row["dataset_id"])
            elif self.level == "year":
                table.add_columns("Year", "Resources")
                self.rows = catalog_years = facets(self.dataset_id or "")["years"]
                for row in catalog_years: table.add_row(str(row["release_year"]), str(row["count"]), key=str(row["release_year"]))
            elif self.level == "product":
                table.add_columns("Product", "Resources")
                self.rows = facets(self.dataset_id or "")["products"]
                for row in self.rows: table.add_row(row["resource_type"], str(row["count"]), key=row["resource_type"])
            elif self.level == "cart":
                table.add_columns("Dataset", "Key", "Product", "Title")
                self.rows = basket(basket_name)
                for row in self.rows: table.add_row(row["dataset_id"], row["resource_key"], row["resource_type"], row["title"], key=str(row["resource_id"]))
            else:
                table.add_columns("✓", "ID", "Product", "Title")
                self.load_rows()
                return
            self._set_initial_row()
            self.query_one(Static).update(f"{self.crumb()} · selection {len(basket(basket_name))} · Enter to continue, Backspace to return.")

        def load_rows(self, query: str = "") -> None:
            table = self.query_one(DataTable)
            table.clear(columns=False)
            selected = {str(item["resource_id"]) for item in basket(basket_name)}
            self.rows = search(self.dataset_id or "", query, limit=500, year=self.year, product=self.product)
            for row in self.rows:
                metadata = row["metadata"]
                table.add_row("●" if str(row["resource_id"]) in selected else "", metadata.get("table_id", row["resource_key"]), row["resource_type"], row["title"], key=str(row["resource_id"]))
            self._set_initial_row()
            self.query_one(Static).update(f"{len(self.rows)} resources. Space selects; Enter fetches field metadata for the highlighted resource.")

        def on_input_changed(self, event: Input.Changed) -> None:
            if self.level == "resource": self.load_rows(event.value)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Fetch an explicit FRED search only after the user submits text."""
            if self.level == "resource" and self.dataset_id == "fred.series":
                self._fetch_fred(event.value)

        def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
            self.current_id = str(event.row_key.value)
            self._debug("highlight")
            if self.level != "resource": return
            resource = get_resource(self.current_id)
            fields = resource["fields"]
            endpoint = resource["metadata"].get("endpoint")
            body = f"{resource['title']}\n{resource.get('universe') or 'Universe not published'}\n{resource['resource_type']} · {len(fields)} cached fields"
            if endpoint:
                body += f"\nAPI endpoint: {endpoint}"
            self.query_one(Static).update(body)

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            """Support mouse activation and terminals that route Enter to the grid."""
            self.current_id = str(event.row_key.value)
            self._debug("row_selected")
            self.action_describe()

        def action_toggle(self) -> None:
            if not self.current_id:
                return
            if self.level in {"year", "product"}:
                group_year = int(self.current_id) if self.level == "year" else self.year
                group_product = self.current_id if self.level == "product" else None
                ids = resource_ids(self.dataset_id or "", group_year, group_product)
                marker = f"group:{self.level}:{self.current_id}"
                if self.confirm != marker:
                    self.confirm = marker
                    self.query_one(Static).update(f"Press Space again to add all {len(ids)} resources in this {self.level} to the selection.")
                    return
                add_all(basket_name, ids)
                self.confirm = None
                self._debug("group_selected", count=len(ids), group=self.current_id)
                self.query_one(Static).update(f"Added {len(ids)} resources from this {self.level} to the selection.")
                return
            if self.level != "resource":
                return
            selected = toggle(basket_name, self.current_id)
            self._debug("resource_toggled", selected=selected)
            self.query_one(Static).update("Added to selection." if selected else "Removed from selection.")
            self.load_rows(self.query_one(Input).value)

        def action_describe(self) -> None:
            if not self.current_id:
                return
            self._debug("open")
            if self.level != "resource":
                if self.level == "provider": self.provider_id, self.level = self.current_id, "dataset"
                elif self.level == "dataset":
                    self.dataset_id = self.current_id
                    # Release years are meaningful for ACS, but a series
                    # catalog such as FRED goes directly to its categories.
                    self.level = "year" if facets(self.dataset_id)["years"] else "product"
                elif self.level == "year":
                    self.year, self.level = int(self.current_id), "product"
                    if self.dataset_id == "census.acs_5" and not _acs_manifest(self.year).is_file():
                        ensure_acs(self.year)
                elif self.level == "product": self.product, self.level = self.current_id, "resource"
                self.load_level(); return
            resource = get_resource(self.current_id)
            if resource["dataset_id"] == "census.api_catalog":
                metadata = resource["metadata"]
                lines = [resource["title"], "", resource.get("summary") or "No provider description published."]
                for label, key in (("API endpoint", "endpoint"), ("Variables", "variables_url"), ("Groups", "groups_url"), ("Geography", "geography_url")):
                    if metadata.get(key):
                        lines.extend(["", f"{label}: {metadata[key]}"])
                lines.extend(["", "Catalog metadata only — selection does not download data."])
                self.query_one(Static).update("\n".join(lines))
                return
            if resource["dataset_id"] != "census.acs_5":
                self.query_one(Static).update("Field discovery is not yet implemented for this provider.")
                return
            from .ingestion.census import describe_acs_table
            table_id = resource["metadata"]["table_id"]
            try:
                report = describe_acs_table(resource["release_year"], table_id)
                upsert_fields(self.current_id, report["fields"])
                lines = [f"{report['table']['id']} — {report['table']['title']}", report['table'].get('universe') or "Universe not published", "", "Fields:"]
                lines.extend(f"{field['id']}  {field['label']}" for field in report["fields"])
                self.query_one(Static).update("\n".join(lines))
            except Exception as exc:
                self.query_one(Static).update(f"Could not fetch field metadata: {exc}")

        def action_open(self) -> None:
            """Open the highlighted row with a reliable, visible keybinding."""
            self.action_describe()

        def action_all(self) -> None:
            if self.level != "resource": return
            if self.confirm != "all":
                self.confirm = "all"; self.query_one(Static).update(f"Press A again to select exactly {len(self.rows)} filtered resources."); return
            add_all(basket_name, [str(row["resource_id"]) for row in self.rows])
            self.confirm = None
            self.query_one(Static).update(f"Selected {len(self.rows)} currently filtered resources.")
            self.load_rows(self.query_one(Input).value)

        def action_fetch(self) -> None:
            """Focus FRED search, or fetch the already-entered query."""
            if self.level != "resource" or self.dataset_id != "fred.series":
                self.query_one(Static).update("Provider search is available after opening FRED resources.")
                return
            query = self.query_one(Input).value
            if len(query.strip()) < 2:
                self.query_one(Input).focus()
                self.query_one(Static).update("Type at least two characters, then press Enter to search official FRED metadata.")
                return
            self._fetch_fred(query)

        def _fetch_fred(self, query: str) -> None:
            """Cache one paced official FRED search page and return focus to results."""
            try:
                count = search_fred(query)
            except Exception as exc:
                self.query_one(Static).update(f"FRED search was not cached: {exc}")
                return
            self.load_rows(query)
            self.query_one(DataTable).focus()
            self._debug("fred_search_cached", count=count)
            self.query_one(Static).update(f"Cached {count} FRED search results. Space selects; G writes a disabled draft.")

        def action_draft(self) -> None:
            if self.confirm != "draft":
                self.confirm = "draft"; self.query_one(Static).update("Press G again to write a disabled draft contract."); return
            path = draft(basket_name)
            self.confirm = None
            self.query_one(Static).update(f"Wrote disabled draft: {path}")

        def action_bulk_plan(self) -> None:
            """Write a review-only Census bulk plan from one complete package."""
            if self.confirm != "bulk_plan":
                self.confirm = "bulk_plan"
                self.query_one(Static).update("Press P again to write an explicit, disabled Census bulk plan from one selected complete package.")
                return
            from .ingestion.acs_bulk import write_acs5_bulk_plan
            from .ingestion.cbp_bulk import write_cbp_bulk_plan
            from .ingestion.pep_bulk import write_pep_bulk_plan
            try:
                selected = basket(basket_name)
                datasets = {item["dataset_id"] for item in selected}
                if datasets == {"census.business_patterns"}:
                    path = write_cbp_bulk_plan(basket_name, selected)
                    command = "cbp-bulk-preview"
                elif datasets == {"census.population_estimates"}:
                    path = write_pep_bulk_plan(basket_name, selected)
                    command = "pep-bulk-preview"
                else:
                    path = write_acs5_bulk_plan(basket_name, selected)
                    command = "acs-bulk-preview"
            except Exception as exc:
                self.query_one(Static).update(f"Could not write Census bulk plan: {exc}")
                return
            self.confirm = None
            self._debug("census_bulk_plan_written", path=str(path), dataset=next(iter(datasets), None))
            self.query_one(Static).update(f"Wrote disabled Census bulk plan: {path}\nRun `research-db ingest {command} --plan {path}` to measure every artifact.")

        def action_back(self) -> None:
            previous = {"dataset": "provider", "year": "dataset", "product": "year", "resource": "product", "cart": "resource"}
            if self.level == "cart":
                self.level = self.cart_origin
            elif self.level == "product" and self.dataset_id and not facets(self.dataset_id)["years"]:
                self.level = "dataset"
            elif self.level in previous:
                self.level = previous[self.level]
            self.load_level()

        def action_cart(self) -> None:
            self.cart_origin = self.level
            self.level = "cart"; self.load_level()

        def action_refresh(self) -> None:
            self.load_level()

    CatalogBrowser().run()
