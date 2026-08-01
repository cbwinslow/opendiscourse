"""Provider-neutral catalog, selection basket, and optional terminal browser."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from psycopg.types.json import Jsonb

from .config import settings
from .db import connect


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
        conn.commit()
    return len(manifest["tables"])


def ensure_acs(year: int = 2024) -> int:
    """Make the current ACS catalog available with no separate user setup step."""
    if not _acs_manifest(year).is_file():
        from .ingestion.census import discover_acs_tables
        discover_acs_tables(year)
    return sync_acs(year)


def search(dataset_id: str, text: str = "", limit: int = 100, year: int | None = None, product: str | None = None) -> list[dict[str, Any]]:
    query = text.strip()
    terms = f"%{query}%"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT resource_id, resource_key, resource_type, title, universe, release_year, metadata
               FROM catalog.resource
               WHERE dataset_id = %s AND (%s = '' OR resource_key ILIKE %s OR
                 to_tsvector('english', concat_ws(' ', resource_key, title, universe, resource_type)) @@ websearch_to_tsquery('english', %s))
                 AND (%s::integer IS NULL OR release_year = %s) AND (%s::text IS NULL OR resource_type = %s)
               ORDER BY resource_key LIMIT %s""",
            (dataset_id, query, terms, query, year, year, product, product, limit),
        )
        return cur.fetchall()


def facets(dataset_id: str) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT release_year, count(*) AS count FROM catalog.resource WHERE dataset_id = %s GROUP BY release_year ORDER BY release_year DESC", (dataset_id,))
        years = cur.fetchall()
        cur.execute("SELECT resource_type, count(*) AS count FROM catalog.resource WHERE dataset_id = %s GROUP BY resource_type ORDER BY resource_type", (dataset_id,))
        products = cur.fetchall()
    # The ACS release choices are known even before each small table-list
    # workbook has been cached. Entering an uncached year can trigger metadata
    # discovery; it never downloads observations.
    if dataset_id == "census.acs_5":
        counts = {row["release_year"]: row["count"] for row in years}
        years = [{"release_year": year, "count": counts.get(year, 0)} for year in range(2024, 2004, -1)]
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


def launch(dataset_id: str = "census.acs_5", basket_name: str = "default", year: int | None = None, product: str | None = None) -> None:
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
            Binding("backspace", "back", "back"),
            Binding("c", "cart", "selection"),
            Binding("enter", "describe", "inspect fields"),
            Binding("r", "refresh", "refresh"),
            Binding("ctrl+q", "quit", "quit"),
        ]
        CSS = """
        #query { margin: 1 1 0 1; }
        #grid { height: 1fr; margin: 1; }
        #detail { height: 12; border: round $accent; padding: 1; overflow: auto; }
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

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Search IDs, titles, or universes…", id="query")
            yield DataTable(id="grid", cursor_type="row")
            yield Static("Loading catalog…", id="detail")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            self.load_level()

        def crumb(self) -> str:
            return " › ".join(item for item in [self.provider_id, self.dataset_id, str(self.year) if self.year else None, self.product, self.level] if item)

        def load_level(self) -> None:
            table = self.query_one(DataTable)
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
            self.query_one(Static).update(f"{self.crumb()} · selection {len(basket(basket_name))} · Enter to continue, Backspace to return.")

        def load_rows(self, query: str = "") -> None:
            table = self.query_one(DataTable)
            table.clear(columns=False)
            selected = {str(item["resource_id"]) for item in basket(basket_name)}
            self.rows = search(self.dataset_id or "", query, limit=500, year=self.year, product=self.product)
            for row in self.rows:
                metadata = row["metadata"]
                table.add_row("●" if str(row["resource_id"]) in selected else "", metadata.get("table_id", row["resource_key"]), row["resource_type"], row["title"], key=str(row["resource_id"]))
            self.query_one(Static).update(f"{len(self.rows)} resources. Space selects; Enter fetches field metadata for the highlighted resource.")

        def on_input_changed(self, event: Input.Changed) -> None:
            if self.level == "resource": self.load_rows(event.value)

        def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
            self.current_id = str(event.row_key.value)
            if self.level != "resource": return
            resource = get_resource(self.current_id)
            fields = resource["fields"]
            body = f"{resource['title']}\n{resource.get('universe') or 'Universe not published'}\n{resource['resource_type']} · {len(fields)} cached fields"
            self.query_one(Static).update(body)

        def action_toggle(self) -> None:
            if not self.current_id or self.level != "resource":
                return
            selected = toggle(basket_name, self.current_id)
            self.query_one(Static).update("Selected in basket." if selected else "Removed from basket.")
            self.load_rows(self.query_one(Input).value)

        def action_describe(self) -> None:
            if not self.current_id:
                return
            if self.level != "resource":
                if self.level == "provider": self.provider_id, self.level = self.current_id, "dataset"
                elif self.level == "dataset": self.dataset_id, self.level = self.current_id, "year"
                elif self.level == "year":
                    self.year, self.level = int(self.current_id), "product"
                    if self.dataset_id == "census.acs_5" and not _acs_manifest(self.year).is_file():
                        ensure_acs(self.year)
                elif self.level == "product": self.product, self.level = self.current_id, "resource"
                self.load_level(); return
            resource = get_resource(self.current_id)
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

        def action_all(self) -> None:
            if self.level != "resource": return
            if self.confirm != "all":
                self.confirm = "all"; self.query_one(Static).update(f"Press A again to select exactly {len(self.rows)} filtered resources."); return
            add_all(basket_name, [str(row["resource_id"]) for row in self.rows])
            self.confirm = None
            self.query_one(Static).update(f"Selected {len(self.rows)} currently filtered resources.")
            self.load_rows(self.query_one(Input).value)

        def action_draft(self) -> None:
            if self.confirm != "draft":
                self.confirm = "draft"; self.query_one(Static).update("Press G again to write a disabled draft contract."); return
            path = draft(basket_name)
            self.confirm = None
            self.query_one(Static).update(f"Wrote disabled draft: {path}")

        def action_back(self) -> None:
            previous = {"dataset": "provider", "year": "dataset", "product": "year", "resource": "product", "cart": "resource"}
            if self.level in previous: self.level = previous[self.level]; self.load_level()

        def action_cart(self) -> None:
            self.level = "cart"; self.load_level()

        def action_refresh(self) -> None:
            self.load_level()

    CatalogBrowser().run()
