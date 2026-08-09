"""Generate starter files for a new data-source provider.

See docs/adding-a-provider.md for the required behaviors a provider must
implement once this scaffold is filled in.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_PROVIDER_TEMPLATE = '''"""{name} provider: TODO one-line summary of what this ingests.

See docs/adding-a-provider.md before implementing this provider.
"""

from __future__ import annotations

from typing import Any

from ..config import settings
from ..ingestion.base import client, json_response


def sync() -> dict[str, Any]:
    """TODO: implement discovery/sync for {name}.

    Read docs/adding-a-provider.md for the required behaviors (provenance,
    pacing, missing-config errors) before filling this in. Delete the
    NotImplementedError below once sync() does real work.
    """
    raise NotImplementedError(
        "{name} provider is a scaffold stub; see docs/adding-a-provider.md"
    )
'''

_TEST_TEMPLATE = '''"""Tests for the {name} provider."""

from __future__ import annotations

import unittest


class Test{class_name}Provider(unittest.TestCase):
    def test_sync_is_not_yet_implemented(self) -> None:
        self.skipTest(
            "Scaffold stub: implement the {name} provider, then replace "
            "this placeholder with real tests before removing the skip."
        )
'''

_SOURCES_YAML_BLOCK = '''
# --- scaffold: fill in and uncomment before use (see docs/adding-a-provider.md) ---
#   - id: {name}
#     name: TODO full provider name
#     base_url: https://TODO
#     auth: api_key
#     datasets:
#       - id: {name}.TODO_dataset
#         title: TODO dataset title
#         access: TODO how data is retrieved
#         client: httpx
#         grain: TODO unit of a single row
#         identifiers: [TODO_id]
#         cadence: TODO refresh cadence
#         priority: 3
#         notes: TODO scope and caveats
'''


class ScaffoldError(ValueError):
    """Raised when a provider name is invalid or already scaffolded/registered."""


def _class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def new_provider(name: str, repo_root: Path) -> dict[str, Path]:
    """Create a provider module, test stub, and commented sources.yaml block for `name`.

    Raises ScaffoldError if `name` is not lowercase snake_case, if a
    provider module for it already exists, or if it already has a live
    entry in inventory/sources.yaml.
    """
    if not _NAME_RE.match(name):
        raise ScaffoldError(
            f"Provider name must be lowercase snake_case (letters, digits, "
            f"underscore, starting with a letter): {name!r}"
        )

    provider_path = repo_root / "src" / "opendiscourse_research" / "providers" / f"{name}.py"
    if provider_path.exists():
        raise ScaffoldError(f"Provider module already exists: {provider_path}")

    test_path = repo_root / "tests" / f"test_{name}_provider.py"
    if test_path.exists():
        raise ScaffoldError(f"Test file already exists: {test_path}")

    sources_yaml_path = repo_root / "inventory" / "sources.yaml"
    existing = yaml.safe_load(sources_yaml_path.read_text()) or {}
    if any(p.get("id") == name for p in existing.get("providers") or []):
        raise ScaffoldError(f"{name!r} already has an entry in inventory/sources.yaml")

    provider_path.write_text(_PROVIDER_TEMPLATE.format(name=name))
    test_path.write_text(_TEST_TEMPLATE.format(name=name, class_name=_class_name(name)))
    with sources_yaml_path.open("a") as handle:
        handle.write(_SOURCES_YAML_BLOCK.format(name=name))

    return {"provider": provider_path, "test": test_path, "sources_yaml": sources_yaml_path}
