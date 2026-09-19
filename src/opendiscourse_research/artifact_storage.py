"""Verified, atomic admission of bytes into checksum-addressed evidence storage."""

import os
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


def file_checksum(path: Path) -> str:
    """Hash files incrementally, including bulk archives larger than memory."""
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_retained(path: str, checksum: str) -> None:
    """Reject missing or unverified byte evidence; explicit virtual URIs are exempt."""
    if path.startswith("virtual://"):
        return
    candidate = Path(path)
    if (
        not candidate.is_file()
        or checksum not in candidate.name
        or file_checksum(candidate) != checksum
    ):
        raise ValueError(
            "checksummed byte artifacts must be retained at a checksum-specific path whose bytes match the supplied checksum"
        )


def retain_artifact_bytes(
    path: Path, checksum_sha256: str, *, destination: Path | None = None
) -> Path:
    """Publish a verified private copy atomically without replacing any retained file."""
    retained = destination or path.with_name(
        f"{path.stem}.{checksum_sha256}{path.suffix}"
    )
    retained.parent.mkdir(parents=True, exist_ok=True)
    # Copy first: linking a mutable source would let later source edits alter evidence.
    with NamedTemporaryFile(
        dir=retained.parent, prefix=".retain-", delete=False
    ) as output:
        temporary = Path(output.name)
        try:
            digest = sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
            if digest.hexdigest() != checksum_sha256:
                raise ValueError(f"artifact checksum changed during retention: {path}")
            try:
                os.link(temporary, retained)
            except FileExistsError:
                pass
            validate_retained(str(retained), checksum_sha256)
        finally:
            temporary.unlink(missing_ok=True)
    return retained
