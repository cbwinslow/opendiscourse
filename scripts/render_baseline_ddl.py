"""Render the Alembic baseline as reviewable PostgreSQL DDL without writing a database."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASELINE_REVISION = "d207df35ca10"
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Write the exact offline SQL for the baseline revision to standard output."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", BASELINE_REVISION, "--sql"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)


if __name__ == "__main__":
    main()
