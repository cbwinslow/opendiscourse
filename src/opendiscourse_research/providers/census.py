"""Census Data API catalog provider adapter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert

from ..db import session
from ..ingestion.base import IngestionRun, client, json_response
from ..models.catalog import CatalogSnapshot, Resource, SnapshotResource
from ..repositories.catalog import upsert_resource

CATALOG_URL = "https://api.census.gov/data.json"
ACS_TABLE_BASED_YEARS = (2021, 2022, 2023, 2024)
# Verified directly against the real Census directory listings.
CBP_YEARS = tuple(range(2009, 2024))
TIGER_YEARS = tuple(range(2016, 2026))
DHC_2020_URL = "https://www2.census.gov/programs-surveys/decennial/2020/data/demographic-and-housing-characteristics-file/National/us2020.dhc.zip"
ACS_PUMS_BASE_URL = "https://www2.census.gov/programs-surveys/acs/data/pums"
AHS_BASE_URL = "https://www2.census.gov/programs-surveys/ahs"
# These are the release directories currently published by Census. AHS was
# annual through 2005, then moved to odd-year releases; the early odd-year
# directories include metropolitan PUFs. This is the all-publisher-release
# list, not a national-series shortcut.
AHS_RELEASE_YEARS = (2001, 2002, 2003, 2004, 2005, *range(2007, 2024, 2))


class _DirectoryLinks(HTMLParser):
    """Minimal parser for the publisher's Apache-style directory indexes."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def census_directory_links(index_url: str, html: str) -> list[str]:
    """Return only safe same-directory official links from a Census index page."""
    parser = _DirectoryLinks()
    parser.feed(html)
    return sorted(
        {
            urljoin(index_url, href)
            for href in parser.links
            if href not in {"../", "./"} and urljoin(index_url, href).startswith("https://www2.census.gov/")
        }
    )


@dataclass(frozen=True)
class ArchiveIndex:
    """One official directory plus the release identity it describes."""

    url: str
    product: str
    period: str
    component: str
    version: str = "current"


def official_housing_archive_indexes() -> tuple[ArchiveIndex, ...]:
    """Return every official PUMS/AHS release directory in the approved scope.

    The list is intentionally generated from publication rules, rather than kept
    as a hand-edited sample.  Discovery still reads the publisher's directory
    and fails closed if a listed member has no byte count.
    """
    # The first four standard releases predate Census's product subfolders.
    # Their PUMS archives sit directly in the release-year directory; 2009
    # introduced the 1-Year/ and 5-Year/ layout.
    indexes = [
        ArchiveIndex(
            f"{ACS_PUMS_BASE_URL}/{year}/" if year < 2009 else f"{ACS_PUMS_BASE_URL}/{year}/1-Year/",
            "acs_pums_1",
            str(year),
            "all",
        )
        for year in range(2005, 2025)
        if year != 2020
    ]
    indexes.extend(
        ArchiveIndex(f"{ACS_PUMS_BASE_URL}/{year}/5-Year/", "acs_pums_5", f"{year - 4}-{year}", "all")
        for year in range(2009, 2025)
    )
    indexes.extend(
        ArchiveIndex(f"{AHS_BASE_URL}/{year}/", "ahs", str(year), "all")
        for year in AHS_RELEASE_YEARS
    )
    return tuple(indexes)


def _ahs_component(name: str) -> str:
    """Classify the two non-overlapping published AHS samples from a filename."""
    return "metropolitan" if "metropolitan" in name else "national"


def _ahs_version(name: str) -> tuple[int, int] | None:
    """Extract the publisher's PUF version where a release has revisions."""
    match = re.search(r"\bv(?:ersion)?\s*(\d+)\.(\d+)\b", name, re.IGNORECASE)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _is_html_family(content_type: str | None) -> bool:
    """Return whether a response declares an HTML or XHTML representation."""
    media_type = (content_type or "").split(";", 1)[0].strip().casefold()
    return (
        media_type in {"text/html", "application/xhtml+xml"}
        or media_type.endswith("+html")
    )


def _is_zip_family(content_type: str | None) -> bool:
    """Return whether a response declares a conventional ZIP binary media type."""
    media_type = (content_type or "").split(";", 1)[0].strip().casefold()
    return media_type in {
        "application/zip",
        "application/x-zip-compressed",
        "application/x-zip",
    }


def _positive_size(value: str | None) -> int | None:
    """Parse a positive publisher byte count without treating zero as evidence."""
    try:
        size = int(value) if value is not None else 0
    except ValueError:
        return None
    return size if size > 0 else None


def _publisher_byte_size(http: httpx.Client, url: str) -> int | None:
    """Read an exact publisher byte count without downloading an archive."""
    is_zip = urlparse(url).path.casefold().endswith(".zip")
    try:
        head = http.head(url)
        if head.is_success and _is_html_family(head.headers.get("content-type")):
            return None
        if head.is_success and head.headers.get("content-length"):
            if is_zip:
                if not _is_zip_family(head.headers.get("content-type")):
                    return None
                return _positive_size(head.headers["content-length"])
            return int(head.headers["content-length"])
        # Some Census archive members omit Content-Length on HEAD. A one-byte
        # range response carries the complete object length in Content-Range;
        # stream it so a server that ignores Range cannot retain a full ZIP.
        with http.stream("GET", url, headers={"Range": "bytes=0-0"}) as probe:
            if not probe.is_success:
                return None
            if _is_html_family(probe.headers.get("content-type")):
                return None
            if is_zip and not _is_zip_family(probe.headers.get("content-type")):
                return None
            content_range = probe.headers.get("content-range")
            if content_range and (match := re.fullmatch(r"bytes \d+-\d+/(\d+)", content_range)):
                return _positive_size(match.group(1)) if is_zip else int(match.group(1))
            if probe.status_code == 200 and probe.headers.get("content-length"):
                return (
                    _positive_size(probe.headers["content-length"])
                    if is_zip
                    else int(probe.headers["content-length"])
                )
    except (httpx.HTTPError, ValueError):
        return None
    return None


def verified_acs_archive_fallback_size(url: str) -> tuple[str, int] | None:
    """Return the sole verified Census legacy alternate and its exact size.

    The alternate is deliberately a small provider-boundary policy.  The 2013
    five-year PUMS directory has a separately published legacy Census path;
    this probe is used only when the primary has no trustworthy binary size.
    It requires an official host, a binary one-byte range response, and a
    positive total length. A missing size or any failed probe is unsafe.
    """
    primary_prefix = (
        "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/"
    )
    if url != f"{primary_prefix}csv_pdc.zip":
        return None
    candidate = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    try:
        with client() as http, http.stream(
            "GET", candidate, headers={"Range": "bytes=0-0"}
        ) as response:
            content_range = response.headers.get("content-range", "")
            match = re.fullmatch(r"bytes 0-0/([1-9]\d*)", content_range)
            if (
                response.status_code != 206
                or urlparse(str(response.url)).scheme != "https"
                or urlparse(str(response.url)).hostname != "www2.census.gov"
                or not _is_zip_family(response.headers.get("content-type"))
                or match is None
            ):
                return None
    except httpx.HTTPError:
        return None
    return candidate, int(match.group(1))


def verified_acs_archive_fallback(url: str, expected_bytes: int | None) -> str | None:
    """Return the verified alternate only when it has the given positive size."""
    if not isinstance(expected_bytes, int) or expected_bytes <= 0:
        return None
    verified = verified_acs_archive_fallback_size(url)
    if verified is None:
        return None
    candidate, publisher_bytes = verified
    return candidate if publisher_bytes == expected_bytes else None


def discover_archive_index(index: ArchiveIndex) -> list[dict[str, Any]]:
    """Read one official Census directory into exact archive-manifest entries.

    This HTTP-only provider boundary deliberately does not guess absent files:
    an inaccessible index or a member with no published byte count is returned
    to the capacity gate as unknown and therefore cannot be transferred.
    """
    with client() as http:
        response = http.get(index.url)
        response.raise_for_status()
        links = census_directory_links(index.url, response.text)
        entries: list[dict[str, Any]] = []
        ahs_current: dict[str, tuple[int, int]] = {}
        if index.product == "ahs":
            for url in links:
                name = unquote(url.rsplit("/", 1)[-1])
                lowered = name.lower()
                if "puf" in lowered and "csv.zip" in lowered and "flat" not in lowered:
                    version = _ahs_version(name)
                    if version is None:
                        raise ValueError(f"AHS PUF has no parseable version: {url}")
                    component = _ahs_component(lowered)
                    ahs_current[component] = max(ahs_current.get(component, version), version)
        for url in links:
            name = unquote(url.rsplit("/", 1)[-1]).lower()
            if not name or name.endswith("/"):
                continue
            if index.product.startswith("acs_pums"):
                if name.startswith("csv_") and name.endswith(".zip"):
                    kind = "data"
                elif name.endswith((".pdf", ".txt", ".xlsx", ".xls", ".doc", ".docx")):
                    kind = "documentation"
                else:
                    continue
            elif index.product == "ahs" and "puf" in name and name.endswith("csv.zip"):
                kind = "data"
            elif name.endswith((".pdf", ".txt", ".xlsx", ".xls", ".doc", ".docx")):
                kind = "documentation"
            else:
                continue
            size = _publisher_byte_size(http, url)
            # The selected URL remains the logical artifact identity. Only this
            # documented one-file Census alternate may repair an untrustworthy
            # primary size, and its bytes are independently range-verified.
            if size is None and (fallback := verified_acs_archive_fallback_size(url)):
                _, size = fallback
            entry: dict[str, Any] = {
                "product": index.product,
                "period": index.period,
                "component": index.component,
                "kind": kind,
                "url": url,
                "bytes": size,
                "version": index.version,
            }
            if index.product == "ahs":
                entry["component"] = _ahs_component(name)
                if kind == "data":
                    version = _ahs_version(name)
                    if version is None:
                        raise ValueError(f"AHS PUF has no parseable version: {url}")
                    entry["representation"] = "flat" if "flat" in name else "relational"
                    entry["version"] = "current" if version == ahs_current.get(entry["component"]) else "superseded"
            entries.append(entry)
    return entries


def _offering_key(item: dict[str, Any]) -> str:
    """Return the stable Census identifier used as a catalog resource key."""
    return str(item.get("identifier") or item.get("@id") or item.get("title"))


def _endpoint(item: dict[str, Any]) -> str | None:
    """Extract the first JSON API distribution endpoint when it is published."""
    for distribution in item.get("distribution", []):
        if distribution.get("format") == "API" and distribution.get("accessURL"):
            return str(distribution["accessURL"])
    return None


def _offering_type(item: dict[str, Any]) -> str:
    """Classify an offering into a browser facet from its official API path."""
    path = "/".join(str(part).casefold() for part in item.get("c_dataset", []))
    description = " ".join(
        str(item.get(key) or "") for key in ("identifier", "title", "description")
    ).casefold()
    if path.startswith("acs5") or "/acs5" in path:
        return "ACS 5-Year"
    if path.startswith("acs1") or "/acs1" in path:
        return "ACS 1-Year"
    if path.startswith("acs"):
        return "ACS supplemental and special products"
    if path.startswith("dec") or "decennial" in description:
        return "Decennial Census"
    if path.startswith("pep") or "population estimates" in description:
        return "Population Estimates"
    if path.startswith("tiger") or "tiger/line" in description:
        return "TIGER geography"
    return "Census API offering"


def sync_catalog() -> dict[str, int | str]:
    """Index every published Census API offering without fetching observations."""
    with (
        client() as http,
        IngestionRun("census.api_catalog", {"action": "catalog"}, mode="plan") as run,
    ):
        response = http.get(CATALOG_URL)
        payload = json_response(response)
        payload_id = run.store_payload(response, payload)
        offerings = payload.get("dataset", [])
        if not isinstance(offerings, list):
            raise ValueError("Census data catalog did not contain a dataset list")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        resource_table = Resource.__table__
        snapshot_table = CatalogSnapshot.__table__
        with session() as active_session:
            for item in offerings:
                if not isinstance(item, dict):
                    continue
                key = _offering_key(item)
                endpoint = _endpoint(item)
                vintage = item.get("c_vintage")
                try:
                    release_year = int(vintage) if vintage is not None else None
                except (TypeError, ValueError):
                    release_year = None
                metadata = {
                    "identifier": item.get("identifier"),
                    "endpoint": endpoint,
                    "dataset_path": item.get("c_dataset"),
                    "available": item.get("c_isAvailable"),
                    "aggregate": item.get("c_isAggregate"),
                    "cube": item.get("c_isCube"),
                    "temporal": item.get("temporal"),
                    "keywords": item.get("keyword", []),
                    "variables_url": item.get("c_variablesLink"),
                    "groups_url": item.get("c_groupsLink"),
                    "geography_url": item.get("c_geographyLink"),
                    "source_payload_id": payload_id,
                }
                resource_statement = insert(resource_table).values(
                    dataset_id="census.api_catalog",
                    resource_key=key,
                    resource_type=_offering_type(item),
                    title=str(item.get("title") or key),
                    summary=item.get("description"),
                    release_year=release_year,
                    metadata=metadata,
                )
                excluded = resource_statement.excluded
                active_session.execute(
                    resource_statement.on_conflict_do_update(
                        index_elements=(resource_table.c.dataset_id, resource_table.c.resource_key),
                        set_={
                            "resource_type": excluded.resource_type,
                            "title": excluded.title,
                            "summary": excluded.summary,
                            "release_year": excluded.release_year,
                            "metadata": excluded.metadata,
                            "updated_at": func.now(),
                        },
                    )
                )
                run.record_count += 1
            snapshot_statement = insert(snapshot_table).values(
                dataset_id="census.api_catalog",
                source_url=CATALOG_URL,
                checksum_sha256=sha256(canonical).hexdigest(),
                metadata={"kind": "census_data_api_catalog", "offerings": run.record_count},
            )
            snapshot_id = active_session.execute(
                snapshot_statement.on_conflict_do_update(
                    index_elements=(snapshot_table.c.dataset_id, snapshot_table.c.checksum_sha256),
                    set_={"metadata": snapshot_statement.excluded.metadata},
                ).returning(snapshot_table.c.snapshot_id)
            ).scalar_one()
            active_session.execute(
                insert(SnapshotResource.__table__)
                .from_select(
                    ("snapshot_id", "resource_id"),
                    select(literal(snapshot_id), Resource.resource_id).where(
                        Resource.dataset_id == "census.api_catalog"
                    ),
                )
                .on_conflict_do_nothing()
            )
    return {"resources": run.record_count, "payload_id": payload_id}


def sync_acs_bulk_packages() -> int:
    """Publish one clear, complete ACS Summary File download per modern release."""
    for year in ACS_TABLE_BASED_YEARS:
        base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
        upsert_resource(
            "census.acs_5_bulk",
            f"full:{year}",
            "Full Detailed Tables",
            f"{year} ACS 5-Year — full Detailed Tables summary file",
            "One official bulk package containing every Detailed Table, estimates, margins of error, and published geography for this ACS 5-year release.",
            year,
            {
                "package": "full_summary_file",
                "url": f"{base}/data/5YRData/5YRData.zip",
                "geography_url": f"{base}/documentation/Geos{year}5YR.txt",
                "table_shells_url": f"{base}/documentation/ACS{year}5YR_Table_Shells.txt",
            },
        )
    return len(ACS_TABLE_BASED_YEARS)


def sync_cbp_bulk_packages() -> int:
    """Publish one official complete CBP annual bundle per available release year."""
    for year in CBP_YEARS:
        upsert_resource(
            "census.business_patterns",
            f"full:{year}",
            "Complete CSV bundle",
            f"{year} County Business Patterns — complete CSV bundle",
            "Official U.S., state, and county CBP/ZBP files for one annual release.",
            year,
            {
                "package": "complete_csv_bundle",
                "source_page": f"https://www.census.gov/data/datasets/{year}/econ/cbp/{year}-cbp.html",
            },
        )
    return len(CBP_YEARS)


PEP_VINTAGE_SERIES = {
    "2020-2025": 2025,
    "2010-2020": 2020,
}


def sync_pep_bulk_packages() -> int:
    """Publish one complete, no-mixing PEP package per available vintage series.

    The pre-fix resource_key format ("vintage:2025") is left registered but
    orphaned rather than deleted -- it may already be referenced by a saved
    basket selection, and the current parser
    (ingestion/pep_bulk.py::_series) simply won't match it, so selecting it
    fails clearly ("select exactly one PEP vintage") rather than silently
    doing the wrong thing.
    """
    for series, end_year in PEP_VINTAGE_SERIES.items():
        upsert_resource(
            "census.population_estimates",
            f"vintage:{series}",
            "National, state, and county totals",
            f"{series} Population Estimates — national, state, and county totals",
            f"Complete {series} PEP vintage series for national/state/county totals. Never combine it with another vintage.",
            end_year,
            {"package": "national_state_county_totals", "vintage": series},
        )
    return len(PEP_VINTAGE_SERIES)


def sync_dhc_bulk_packages() -> int:
    """Publish the one complete 2020 DHC archive without disguising segments as tables."""
    upsert_resource(
        "census.decennial",
        "dhc:2020:national",
        "Complete DHC national archive",
        "2020 Decennial DHC — complete national archive",
        "Official 2020 Demographic and Housing Characteristics archive. Geographic headers and segmented records remain source-shaped until an explicit LOGRECNO-aware loader is approved.",
        2020,
        {"package": "complete_national_dhc", "url": DHC_2020_URL},
    )
    return 1


def sync_tiger_bulk_packages() -> int:
    """Publish a small, complete national boundary package per available TIGER vintage."""
    for year in TIGER_YEARS:
        upsert_resource(
            "census.tiger",
            f"national:{year}:core-boundaries",
            "National core boundary layers",
            f"{year} TIGER/Line — national core boundary layers",
            "Official nationwide state, county, CBSA, and ZCTA boundary archives. State-partitioned tract, block-group, and block layers stay separate to keep package sizes and scope clear.",
            year,
            {
                "package": "national_core_boundaries",
                "base_url": f"https://www2.census.gov/geo/tiger/TIGER{year}",
            },
        )
    return len(TIGER_YEARS)
