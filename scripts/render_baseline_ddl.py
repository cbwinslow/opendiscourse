"""Render the Alembic baseline as reviewable PostgreSQL DDL without writing a database."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

BASELINE_REVISION = "d207df35ca10"
BASELINE_SHA256 = "1507862b64c97aae328685c70770a3a7264d5a0047dfbca97b0c4f3af76565b6"
ROOT = Path(__file__).resolve().parents[1]


def render() -> str:
    """Return the exact offline SQL for the baseline revision."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", BASELINE_REVISION, "--sql"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
        text=True,
    )
    return result.stdout


def fingerprint(ddl: str) -> str:
    """Hash baseline DDL while normalizing independent index declaration order."""
    statements = ddl.split(";\n\n")
    indexes = sorted(statement for statement in statements if statement.startswith("CREATE INDEX"))
    other_statements = [
        statement for statement in statements if not statement.startswith("CREATE INDEX")
    ]
    return sha256(";\n\n".join([*other_statements, *indexes]).encode()).hexdigest()


def main() -> None:
    """Render baseline DDL or verify its reviewed fingerprint."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated baseline DDL differs from the reviewed fingerprint",
    )
    arguments = parser.parse_args()
    ddl = render()
    digest = fingerprint(ddl)
    if arguments.check:
        if digest != BASELINE_SHA256:
            raise SystemExit(
                f"Baseline DDL fingerprint changed: expected {BASELINE_SHA256}, got {digest}"
            )
        return
    sys.stdout.write(ddl)


if __name__ == "__main__":
    main()
