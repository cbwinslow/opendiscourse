"""Delete the lake areas that `research-db lake inventory` marks `prune`.

Dry run by default. With --yes it deletes, after re-checking that no area holds a
registered artifact and that every path stays inside its root, and writes a manifest
of what was removed next to the inventory report. Run `research-db lake inventory`
first; this reads its latest report.

    uv run python scripts/ops/prune_lake.py          # list what would go
    uv run python scripts/ops/prune_lake.py --yes    # delete it
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from opendiscourse_research.config import settings
from opendiscourse_research.lake import resolve_roots
from opendiscourse_research.repositories.artifacts import registered_local_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="actually delete")
    args = parser.parse_args()
    meta = Path(settings.data_root).expanduser().resolve().parent / "meta" / "inventory"
    report = json.loads((meta / "latest.json").read_text())
    roots = resolve_roots()
    registered = registered_local_paths()
    deleted = []
    total = 0
    for area in (a for a in report["areas"] if a["disposition"] == "prune"):
        base = roots.get(area["root"])
        if base is None or ".." in area["path"].split("/"):
            continue
        path = base / area["path"]
        if not (path.exists() or path.is_symlink()):
            continue
        if not path.is_symlink() and not path.resolve().is_relative_to(base.resolve()):
            raise SystemExit(f"refusing: {path} escapes its root")
        prefix = str(path) + "/"
        if any(item == str(path) or item.startswith(prefix) for item in registered):
            raise SystemExit(f"refusing: {path} contains registered artifacts")
        size = area["size_bytes"] or 0
        total += size
        print(f"{'DELETE' if args.yes else 'WOULD DELETE'} {size / 1e9:8.2f} GB  {area['root']}:{area['path']}")
        if args.yes:
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            deleted.append(
                {k: area[k] for k in ("root", "path", "size_bytes", "files", "reason")}
                | {"deleted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            )
    if args.yes:
        stamp = time.strftime("%Y-%m-%d")
        (meta / f"pruned-{stamp}.json").write_text(json.dumps(deleted, indent=1))
    print(f"{'deleted' if args.yes else 'would delete'} {total / 1e9:.1f} GB in {len(deleted) or 'n/a'} areas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
