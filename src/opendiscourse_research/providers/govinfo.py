"""GovInfo BILLSTATUS bulk-data client: HTTP only (Story 9.5).

Three read-only, unauthenticated lookups against ``www.govinfo.gov/bulkdata``: the
Congress folders in the root manifest, one HEAD per Congress/bill-type zip (its size
and ``Last-Modified``, which is how a refresh is detected without downloading), and
the directory manifest that lists every XML file GovInfo publishes for a type.
Everything is paced and retried once on transport errors, 429 and 5xx; anything
else raises :class:`GovInfoError` so a caller never mistakes a failure for "no data".
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .paced import PacedClient, Send

USER_AGENT = "opendiscourse-research/0.1 (BILLSTATUS connector; polite, resumable)"
PACE_SECONDS = 1.0
BULK_ROOT = "https://www.govinfo.gov/bulkdata"
ROOT_MANIFEST = f"{BULK_ROOT}/json/BILLSTATUS"
TYPE_MANIFEST = ROOT_MANIFEST + "/{congress}/{bill_type}"
ZIP_URL = BULK_ROOT + "/BILLSTATUS/{congress}/{bill_type}/BILLSTATUS-{congress}-{bill_type}.zip"
BILL_TYPES: tuple[str, ...] = (
    "hconres",
    "hjres",
    "hr",
    "hres",
    "s",
    "sconres",
    "sjres",
    "sres",
)
# BILLSTATUS-118hr184.xml -> (118, "hr", 184). Backtracking resolves hr/hres, s/sres.
MEMBER_NAME = re.compile(
    r"^BILLSTATUS-(\d+)(hconres|hjres|hr|hres|s|sconres|sjres|sres)(\d+)\.xml$"
)


class GovInfoError(RuntimeError):
    """A GovInfo lookup failed or returned something unusable."""


class GovInfoNotFound(GovInfoError):
    """GovInfo answered 404: the object is not published (yet)."""


def _error(message: str, status: int | None) -> GovInfoError:
    return (GovInfoNotFound if status == 404 else GovInfoError)(message)


@dataclass(frozen=True)
class RemoteZip:
    """What GovInfo says about one BILLSTATUS zip, without downloading it."""

    congress: int
    bill_type: str
    url: str
    size: int
    last_modified: str


def _default_send(method: str, url: str) -> httpx.Response:
    """One request with the project's User-Agent; the manifests need a JSON Accept."""
    headers = {"User-Agent": USER_AGENT}
    if "/bulkdata/json/" in url:
        headers["Accept"] = "application/json"
    return httpx.request(method, url, headers=headers, timeout=60, follow_redirects=True)


def member_identity(name: str) -> tuple[int, str, int] | None:
    """Parse ``BILLSTATUS-<congress><type><number>.xml``; None for anything else."""
    match = MEMBER_NAME.match(name)
    return (int(match.group(1)), match.group(2), int(match.group(3))) if match else None


class GovInfoBillStatus:
    """Paced, retrying client for the GovInfo BILLSTATUS bulk-data service."""

    def __init__(
        self,
        send: Send = _default_send,
        pace_seconds: float = PACE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = PacedClient(send, pace_seconds, sleep, _error)

    def _request(self, method: str, url: str) -> httpx.Response:
        return self._client.request(method, url)

    def congresses(self) -> list[int]:
        """Congress folders listed in the BILLSTATUS root manifest, ascending."""
        try:
            files = self._request("GET", ROOT_MANIFEST).json()["files"]
            found = sorted(
                int(item["name"])
                for item in files
                if item.get("folder") and str(item.get("name", "")).isdigit()
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise GovInfoError(f"{ROOT_MANIFEST}: unreadable manifest ({exc})") from exc
        if not found:
            raise GovInfoError(f"{ROOT_MANIFEST}: no Congress folders listed")
        return found

    def zip_info(self, congress: int, bill_type: str) -> RemoteZip:
        """Size and ``Last-Modified`` of one zip. Unknown size fails closed."""
        url = ZIP_URL.format(congress=congress, bill_type=bill_type)
        headers = self._request("HEAD", url).headers
        length, modified = headers.get("content-length", ""), headers.get("last-modified")
        if not length.isdigit() or int(length) == 0 or not modified:
            raise GovInfoError(
                f"{url}: the server gave no usable size or Last-Modified "
                f"(content-length={length!r}, last-modified={modified!r})"
            )
        return RemoteZip(congress, bill_type, url, int(length), modified)

    def manifest_xml(self, congress: int, bill_type: str) -> frozenset[str]:
        """Every XML file name GovInfo lists for one Congress and bill type."""
        url = TYPE_MANIFEST.format(congress=congress, bill_type=bill_type)
        try:
            files = self._request("GET", url).json()["files"]
            names = frozenset(
                item["name"] for item in files if item.get("name", "").endswith(".xml")
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise GovInfoError(f"{url}: unreadable manifest ({exc})") from exc
        if not names:  # a degraded 200 must never become an authoritative zero
            raise GovInfoError(f"{url}: manifest lists no XML files")
        return names
