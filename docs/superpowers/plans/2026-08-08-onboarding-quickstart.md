# Onboarding & Provider-Scaffold Quickstart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a clean clone of OpenDiscourse runnable by a stranger in minutes, and give them a scaffold + checklist for adding a new data-source provider.

**Architecture:** No changes to existing provider/repository/ingestion code. Five additive, independently-testable pieces: (1) portable env/compose/config defaults, (2) a human-facing quickstart + CONTRIBUTING doc, (3) a pure-function provider scaffold generator module, (4) a thin Typer CLI command wrapping it, (5) a provider-checklist doc with a FRED walkthrough.

**Tech Stack:** Python 3.12, Typer (CLI), `unittest` (test runner — NOT pytest), PyYAML, Docker Compose, `uv`.

## Global Constraints

- Test runner is `unittest` via `python -m unittest discover -s tests -v`, not `pytest`. Run with `uv run --extra ingest --extra spatial python -m unittest discover -s tests -v` to match CI.
- Python requires `>=3.12` (`pyproject.toml`); use `from __future__ import annotations` in every new module, matching existing files.
- `ruff` is available (`ruff check src/`, `ruff format src/`) but is **not** a CI gate — don't add new violations, but a clean `ruff check` is not required to merge.
- No LICENSE file is added in this work — deferred by explicit decision.
- No shared Protocol/ABC/base class across providers — rejected by design; providers stay plain function modules with provider-specific shapes.
- `postgis/postgis` image version must match CI's `.github/workflows/test.yml`, which pins `postgis/postgis:17-3.5`.
- Compose/env defaults must never encode a maintainer-specific filesystem path (e.g. `/home/cbwinslow/...`); defaults must be project-relative (`./data-lake`).
- New Python modules/functions need concise docstrings, per `AGENTS.md`.

---

## Task 1: Portable environment configuration

**Files:**
- Modify: `src/opendiscourse_research/config.py`
- Modify: `.env.example`
- Modify: `compose.yaml`
- Modify: `.gitignore`
- Test: `tests/test_config.py` (new)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `Settings.model_fields["data_root"].default == "./data-lake/opendiscourse/raw"` — later tasks/docs reference this same `./data-lake` convention (Task 2's `docs/getting-started.md`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for portable default configuration."""

from __future__ import annotations

import unittest

from opendiscourse_research.config import Settings


class TestSettingsDefaults(unittest.TestCase):
    def test_data_root_default_is_project_relative_not_maintainer_specific(
        self,
    ) -> None:
        default = Settings.model_fields["data_root"].default
        self.assertFalse(default.startswith("/home/"))
        self.assertEqual(default, "./data-lake/opendiscourse/raw")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_config -v`
Expected: FAIL — `AssertionError: '/home/cbwinslow/workspace/data-lake/opendiscourse/raw' != './data-lake/opendiscourse/raw'`

- [ ] **Step 3: Fix the config default**

In `src/opendiscourse_research/config.py`, change:

```python
    data_root: str = "/home/cbwinslow/workspace/data-lake/opendiscourse/raw"
```

to:

```python
    data_root: str = "./data-lake/opendiscourse/raw"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_config -v`
Expected: PASS

- [ ] **Step 5: Update `.env.example`**

Change:

```
OD_LAKE_ROOT=/home/cbwinslow/workspace/data-lake
DATA_ROOT=/home/cbwinslow/workspace/data-lake/opendiscourse/raw
```

to:

```
# Spacious, persistent storage. Defaults to a folder inside this checkout so
# a clean clone works with zero edits; point real deployments at real
# spacious, backed-up storage instead (do not use the OS/root filesystem).
OD_LAKE_ROOT=./data-lake
DATA_ROOT=./data-lake/opendiscourse/raw
```

- [ ] **Step 6: Update `compose.yaml`**

In `compose.yaml`, change the image line:

```yaml
    image: postgis/postgis:16-3.4
```

to:

```yaml
    image: postgis/postgis:17-3.5
```

and change the volume line:

```yaml
      - ${OD_LAKE_ROOT:-/home/cbwinslow/workspace/data-lake}/opendiscourse/postgres:/var/lib/postgresql/data
```

to:

```yaml
      - ${OD_LAKE_ROOT:-./data-lake}/opendiscourse/postgres:/var/lib/postgresql/data
```

- [ ] **Step 7: Update `.gitignore`**

Add a `data-lake/` entry (the new default `OD_LAKE_ROOT` writes here; it must never be committed). Add it near the existing `data/` line:

```
data/
data-lake/
logs/
```

- [ ] **Step 8: Re-run the full existing test suite to confirm nothing broke**

Run: `uv run --extra ingest --extra spatial python -m unittest discover -s tests -v`
Expected: same pass/skip counts as before this task (no new failures).

- [ ] **Step 9: Commit**

```bash
git add src/opendiscourse_research/config.py .env.example compose.yaml .gitignore tests/test_config.py
git commit -m "fix: make data-lake defaults project-relative instead of maintainer-specific"
```

---

## Task 2: Newcomer quickstart and contributing docs

**Files:**
- Create: `docs/getting-started.md`
- Create: `CONTRIBUTING.md`
- Test: `tests/test_docs_crosslinks.py` (new)

**Interfaces:**
- Consumes: `./data-lake` convention from Task 1 (referenced in prose).
- Produces: `docs/getting-started.md` and `CONTRIBUTING.md`, both referenced by `docs/adding-a-provider.md` in Task 5 and checked by `tests/test_docs_crosslinks.py` (extended in Task 5).

- [ ] **Step 1: Write the failing test**

Create `tests/test_docs_crosslinks.py`:

```python
"""Regression checks that newcomer-facing docs exist and cross-link correctly."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDocsCrossLinks(unittest.TestCase):
    def test_getting_started_exists_and_links_to_reference_docs(self) -> None:
        text = (REPO_ROOT / "docs" / "getting-started.md").read_text()
        self.assertIn("README.md", text)
        self.assertIn("AGENTS.md", text)
        self.assertIn("CONTRIBUTING.md", text)

    def test_contributing_exists_and_links_to_getting_started(self) -> None:
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text()
        self.assertIn("docs/getting-started.md", text)
        self.assertIn("AGENTS.md", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_docs_crosslinks -v`
Expected: FAIL with `FileNotFoundError` (neither doc exists yet)

- [ ] **Step 3: Create `docs/getting-started.md`**

```markdown
# Getting Started

This is the fastest path to a working local OpenDiscourse database. It uses
the Docker Compose Postgres service, not the bare-metal production setup
described in `README.md`.

## 1. Clone and configure

```bash
git clone https://github.com/cbwinslow/opendiscourse.git
cd opendiscourse
cp .env.example .env
```

Open `.env` and point `DATABASE_URL` at the Docker Compose database instead
of the bare-metal default:

```
DATABASE_URL=postgresql://research:change-me@localhost:5433/research
```

Leave `POSTGRES_*`, `OD_LAKE_ROOT`, and `DATA_ROOT` at their defaults for a
first run — they already point at a `./data-lake` folder inside this
checkout, which Docker creates automatically.

## 2. Start Postgres

```bash
docker compose up -d
```

## 3. Install and initialize

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[analytics,spatial,ingest]'
research-db init-db
```

`init-db` only creates schema and seeds the catalog of *known* datasets — it
never contacts a provider or downloads data.

## 4. Explore

```bash
research-db status   # catalog-ready datasets vs. registered-but-unimplemented
research-db browse    # interactive catalog browser
```

## Next steps

- Full adapter-by-adapter command reference: `README.md`
- How to add a new data source: `docs/adding-a-provider.md`
- How to propose a change: `CONTRIBUTING.md`
- If you're using an AI coding assistant on this repo, read `AGENTS.md` and
  `CLAUDE.md` first — they describe conventions this quickstart doesn't
  repeat.
- Running this for real, not local exploration: see the bare-metal
  PostgreSQL setup in `README.md`. Docker Compose here is a development
  convenience only.
```

- [ ] **Step 4: Create `CONTRIBUTING.md`**

```markdown
# Contributing

## Setup

See `docs/getting-started.md` for the fastest path to a running database.

## Running tests

Tests use `unittest`, not `pytest`, and CI runs them against a real
`postgis/postgis:17-3.5` service container (`.github/workflows/test.yml`):

```bash
uv run --extra ingest --extra spatial python -m unittest discover -s tests -v

# Single file / class / test
uv run python -m unittest tests.test_govbackfill -v
```

Tests that touch a real database are skipped automatically unless
`OPENDISCOURSE_TEST_DATABASE_URL` is set — everything else runs against
fakes/mocks with no database required. Write tests alongside the code that
needs them, not after; see `AGENTS.md` for the full engineering standard.

## Lint/format

```bash
ruff check src/
ruff format src/
```

`ruff` is available but not a CI gate yet, and the tree is not currently
clean under it. Don't assume a passing `ruff check` is required to merge,
but don't add new violations either.

## Adding a new data source

Run `research-db new-provider <name>` to generate a starter provider
module, test stub, and a commented `inventory/sources.yaml` entry, then
follow `docs/adding-a-provider.md`, which lists the required behaviors and
walks through how the FRED provider implements each one.

## Commits and branches

Small, cohesive commits, one logical change each, with a concise imperative
subject line. See `AGENTS.md`'s "Git and GitHub workflow" section for the
full convention this project follows.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_docs_crosslinks -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add docs/getting-started.md CONTRIBUTING.md tests/test_docs_crosslinks.py
git commit -m "docs: add newcomer quickstart and contributing guide"
```

---

## Task 3: Provider scaffold generator

**Files:**
- Create: `src/opendiscourse_research/scaffold.py`
- Test: `tests/test_scaffold.py` (new)

**Interfaces:**
- Consumes: nothing from other tasks (pure filesystem logic, no DB).
- Produces:
  - `class ScaffoldError(ValueError)`
  - `def new_provider(name: str, repo_root: Path) -> dict[str, Path]` — returns `{"provider": Path, "test": Path, "sources_yaml": Path}` on success; raises `ScaffoldError` on an invalid name or a collision. Consumed by Task 4's CLI command.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scaffold.py`:

```python
"""Tests for the new-provider scaffold generator."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from opendiscourse_research.scaffold import ScaffoldError, new_provider


def _make_fake_repo(root: Path) -> None:
    (root / "src" / "opendiscourse_research" / "providers").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "inventory").mkdir(parents=True)
    (root / "inventory" / "sources.yaml").write_text(
        "version: 1\nproviders:\n  - id: fred\n    name: FRED\n"
    )


class TestNewProvider(unittest.TestCase):
    def test_rejects_non_snake_case_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            with self.assertRaisesRegex(ScaffoldError, "lowercase snake_case"):
                new_provider("FEC-Bulk", root)

    def test_rejects_existing_provider_module(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            (root / "src" / "opendiscourse_research" / "providers" / "fec.py").write_text(
                "# already here\n"
            )
            with self.assertRaisesRegex(ScaffoldError, "already exists"):
                new_provider("fec", root)

    def test_rejects_existing_sources_yaml_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            with self.assertRaisesRegex(ScaffoldError, "already has an entry"):
                new_provider("fred", root)

    def test_creates_provider_test_and_sources_yaml_stub(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            created = new_provider("fec_bulk", root)

            provider_text = created["provider"].read_text()
            self.assertIn("from ..config import settings", provider_text)
            self.assertIn("from ..ingestion.base import client, json_response", provider_text)
            self.assertIn("def sync()", provider_text)
            self.assertIn("NotImplementedError", provider_text)
            self.assertIn("docs/adding-a-provider.md", provider_text)

            test_text = created["test"].read_text()
            self.assertIn("class TestFecBulkProvider(unittest.TestCase)", test_text)
            self.assertIn("self.skipTest(", test_text)

            sources_text = created["sources_yaml"].read_text()
            self.assertIn("id: fec_bulk", sources_text)
            marker = "# --- scaffold:"
            marker_index = sources_text.index(marker)
            appended = sources_text[marker_index:]
            self.assertTrue(
                all(
                    line.strip().startswith("#") or not line.strip()
                    for line in appended.splitlines()
                ),
                "appended block must stay commented out until filled in",
            )
            # Original content must still be intact and still parse.
            parsed = yaml.safe_load(sources_text[:marker_index])
            self.assertEqual(parsed["providers"][0]["id"], "fred")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest tests.test_scaffold -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'opendiscourse_research.scaffold'`

- [ ] **Step 3: Implement `src/opendiscourse_research/scaffold.py`**

```python
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

    sources_yaml_path = repo_root / "inventory" / "sources.yaml"
    existing = yaml.safe_load(sources_yaml_path.read_text()) or {}
    if any(p.get("id") == name for p in existing.get("providers", [])):
        raise ScaffoldError(f"{name!r} already has an entry in inventory/sources.yaml")

    test_path = repo_root / "tests" / f"test_{name}_provider.py"

    provider_path.write_text(_PROVIDER_TEMPLATE.format(name=name))
    test_path.write_text(_TEST_TEMPLATE.format(name=name, class_name=_class_name(name)))
    with sources_yaml_path.open("a") as handle:
        handle.write(_SOURCES_YAML_BLOCK.format(name=name))

    return {"provider": provider_path, "test": test_path, "sources_yaml": sources_yaml_path}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_scaffold -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/opendiscourse_research/scaffold.py tests/test_scaffold.py
git commit -m "feat: add provider scaffold generator"
```

---

## Task 4: Wire `research-db new-provider` CLI command

**Files:**
- Modify: `src/opendiscourse_research/cli.py`

**Interfaces:**
- Consumes: `ScaffoldError`, `new_provider(name, repo_root) -> dict[str, Path]` from Task 3.
- Produces: `research-db new-provider <name>` CLI command (no other task depends on this programmatically — it's a terminal user entry point).

- [ ] **Step 1: Add the import**

In `src/opendiscourse_research/cli.py`, add near the other same-package imports (alphabetically close to the existing `from .db import apply_migrations` line):

```python
from .scaffold import ScaffoldError, new_provider
```

- [ ] **Step 2: Add the command**

Add near `init_db` (top of the command list is fine, it's a dev/contributor-facing command like `init-db`):

```python
@app.command("new-provider")
def new_provider_command(
    name: str = typer.Argument(
        ..., help="New provider id in lowercase snake_case, e.g. fec_bulk."
    ),
) -> None:
    """Scaffold a new provider module, test stub, and sources.yaml entry."""
    repo_root = Path(__file__).resolve().parents[2]
    try:
        created = new_provider(name, repo_root)
    except ScaffoldError as exc:
        raise typer.BadParameter(str(exc)) from None
    for label, path in created.items():
        typer.echo(f"{label}: {path}")
    typer.echo("Next: fill in the TODOs, then read docs/adding-a-provider.md.")
```

`Path` is already imported in `cli.py` (`from pathlib import Path`) — no new import needed for that.

- [ ] **Step 3: Manual smoke test**

Run from the repo root:

```bash
uv run research-db new-provider demo_smoke_test
```

Expected: prints three created paths ending in `.../providers/demo_smoke_test.py`, `.../tests/test_demo_smoke_test_provider.py`, and `.../inventory/sources.yaml`, plus the "Next:" line. Confirm the files look right, then verify collision handling:

```bash
uv run research-db new-provider demo_smoke_test
```

Expected: non-zero exit and an error message containing "already exists".

Clean up the smoke-test artifacts (these are not meant to be committed):

```bash
rm src/opendiscourse_research/providers/demo_smoke_test.py \
   tests/test_demo_smoke_test_provider.py
git checkout -- inventory/sources.yaml
git status
```

Expected: `git status` shows no pending changes from the smoke test.

- [ ] **Step 4: Re-run the full existing test suite to confirm nothing broke**

Run: `uv run --extra ingest --extra spatial python -m unittest discover -s tests -v`
Expected: same pass/skip counts as after Task 3, plus no import errors from `cli.py`.

- [ ] **Step 5: Commit**

```bash
git add src/opendiscourse_research/cli.py
git commit -m "feat: add research-db new-provider CLI command"
```

---

## Task 5: Provider checklist doc, final cross-link coverage, and end-to-end verification

**Files:**
- Create: `docs/adding-a-provider.md`
- Modify: `tests/test_docs_crosslinks.py`

**Interfaces:**
- Consumes: `docs/getting-started.md`, `CONTRIBUTING.md` (Task 2); `research-db new-provider` (Task 4) referenced in prose only.
- Produces: nothing consumed by other tasks — this is the last task.

- [ ] **Step 1: Extend the failing test**

Add to `tests/test_docs_crosslinks.py` (inside `TestDocsCrossLinks`):

```python
    def test_adding_a_provider_exists_and_names_the_scaffold_command(self) -> None:
        text = (REPO_ROOT / "docs" / "adding-a-provider.md").read_text()
        self.assertIn("research-db new-provider", text)
        self.assertIn("fred.py", text)

    def test_contributing_links_to_adding_a_provider(self) -> None:
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text()
        self.assertIn("docs/adding-a-provider.md", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_docs_crosslinks -v`
Expected: FAIL — `FileNotFoundError` for `docs/adding-a-provider.md` (the `CONTRIBUTING.md` assertion already passes since Task 2 wrote that link ahead of time)

- [ ] **Step 3: Create `docs/adding-a-provider.md`**

```markdown
# Adding a Provider

A provider is a plain Python module under
`src/opendiscourse_research/providers/` that talks to one external data
source. Providers intentionally do **not** share a common base class or
function signature — FRED, Census, and Congress each expose different
shapes (paced search plus resumable indexing; multi-dataset bulk-package
sync; one-shot sync) because their upstream APIs are genuinely different.
See `AGENTS.md`: "keep provider-specific behavior explicit at the adapter
boundary."

Run `research-db new-provider <name>` first — it creates:

- `src/opendiscourse_research/providers/<name>.py`
- `tests/test_<name>_provider.py`
- a commented starter block in `inventory/sources.yaml`

Then fill in each of the required behaviors below.

## Required behaviors

1. **Record provenance through the repository layer, not inline SQL.** Call
   the existing functions in `src/opendiscourse_research/repositories/`
   (e.g. `catalog.py`) to persist results. *FRED example:*
   `providers/fred.py`'s `search()` and `index_batch()` call
   `repositories/catalog.py`'s `cache_fred_search()` and
   `cache_fred_records()` rather than touching the database directly.

2. **Respect the provider's pacing/rate limits**, if it has any. *FRED
   example:* `providers/fred.py` tracks `_last_request` with `monotonic()`
   and sleeps to enforce `PACE_SECONDS = 1.0` before every request.

3. **Raise a clear `ValueError` on missing required config**, instead of
   letting a request fail opaquely. *FRED example:* `providers/fred.py`'s
   `_get()` raises `ValueError("FRED_API_KEY is required for live FRED
   discovery")` up front when `settings.fred_api_key` is unset.

4. **Never contact a live provider from `init-db`.** `init-db` (`cli.py`'s
   `init_db()`) only applies migrations and syncs the version-controlled
   catalog in `inventory/sources.yaml` — it must stay that way. Discovery
   and sync are separate, explicit CLI commands.

5. **Use the shared HTTP client and response guard.** Call
   `ingestion.base.client()` for the `httpx.Client` (it sets a timeout and
   `User-Agent`) and wrap responses in `ingestion.base.json_response()`,
   which rejects non-JSON/error responses without leaking API keys into
   error messages. *FRED example:* `providers/fred.py`'s `_get()` does
   exactly this.

## Worked example: FRED end to end

- `src/opendiscourse_research/providers/fred.py` — `search()` runs one
  paced metadata search; `index_batch()` resumes a cursor-based crawl of
  every FRED release/series, checkpointing progress via
  `repositories/catalog.py`'s `claim_discovery()`/`save_discovery()` so a
  stopped run resumes instead of restarting.
- `src/opendiscourse_research/repositories/catalog.py` — owns the actual
  `INSERT`s (`cache_fred_records()`, `cache_fred_search()`); the provider
  module never writes SQL itself.
- `inventory/sources.yaml` — the `fred` provider block declares the
  `fred.series` dataset (grain, identifiers, cadence, priority) that
  `research-db status`/`browse` read.
- Register a new dataset in `inventory/sources.yaml` before writing any
  code for it, then see `docs/framework.md` for the full
  register → contract → discovery → staging → canonical-transform sequence
  this project follows once a provider goes beyond metadata discovery.

Note: FRED does not yet have a dedicated `tests/test_fred*.py` file. For a
worked example of this project's actual test style (real
`unittest.TestCase` classes, `unittest.mock.patch`, temp directories, no
live network calls), read `tests/test_census_bulk.py` or
`tests/test_openstates_refresh.py` instead.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_docs_crosslinks -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run the complete test suite**

Run: `uv run --extra ingest --extra spatial python -m unittest discover -s tests -v`
Expected: all tests pass or skip (skips are expected for DB-touching tests without `OPENDISCOURSE_TEST_DATABASE_URL` set); zero failures/errors.

- [ ] **Step 6: Clean-clone Docker smoke test (validates Task 1 end to end)**

From a scratch directory (not this checkout):

```bash
git clone /home/cbwinslow/projects/opendiscourse /tmp/opendiscourse-smoke-test
cd /tmp/opendiscourse-smoke-test
cp .env.example .env
# Edit .env: set DATABASE_URL=postgresql://research:change-me@localhost:5433/research
docker compose up -d
python -m venv .venv && source .venv/bin/activate
pip install -e '.[analytics,spatial,ingest]'
research-db init-db
research-db status
```

Expected: every command succeeds with no manual path edits beyond the
documented `DATABASE_URL` override. Then clean up:

```bash
docker compose down -v
cd /home/cbwinslow/projects/opendiscourse
rm -rf /tmp/opendiscourse-smoke-test
```

- [ ] **Step 7: Commit**

```bash
git add docs/adding-a-provider.md tests/test_docs_crosslinks.py
git commit -m "docs: add provider checklist and FRED worked example"
```
