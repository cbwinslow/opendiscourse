"""Verified, atomic admission of bytes into checksum-addressed evidence storage."""

import os
import shutil
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


# Free space that must remain after a copy; retention fails closed instead of
# filling the volume the warehouse and lake share.
COPY_RESERVE_BYTES = 1024**3


def retained_path(path: Path, checksum: str) -> Path:
    """Return the checksum-specific retained location beside ``path``."""
    return path.with_name(f"{path.stem}.{checksum}{path.suffix}")


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
            "checksummed byte artifacts must be retained at a checksum-specific path "
            f"whose bytes match the supplied checksum ({path}). Retained evidence is "
            "never overwritten automatically: inspect the file, move it aside if it "
            "is damaged, then re-admit the bytes."
        )


def _require_space(directory: Path, needed: int) -> None:
    """Fail closed when a copy would leave the volume under its reserve."""
    free = shutil.disk_usage(directory).free
    if free < needed + COPY_RESERVE_BYTES:
        raise OSError(
            f"not enough free space in {directory} to retain {needed} bytes "
            f"({free} free, {COPY_RESERVE_BYTES} must remain)"
        )


def retain_artifact_bytes(
    path: Path,
    checksum_sha256: str,
    *,
    destination: Path | None = None,
    move: bool = False,
) -> Path:
    """Publish verified bytes at their checksum-specific path, never replacing evidence.

    ``move=True`` is for a private staging file whose checksum the caller just
    computed from these exact bytes (a finished download): it is published by an
    atomic hard link, so nothing is read or written a second time. Any other
    source (an external file we do not control) is copied, hashed while copying,
    and only then published.
    """
    retained = destination or retained_path(path, checksum_sha256)
    retained.parent.mkdir(parents=True, exist_ok=True)
    if retained.exists():
        # Already retained (a rerun, or a same-bytes refresh): one read to trust it.
        validate_retained(str(retained), checksum_sha256)
        if move and path != retained:
            path.unlink(missing_ok=True)
        return retained
    if move:
        try:
            os.link(path, retained)
        except FileExistsError:
            validate_retained(str(retained), checksum_sha256)
            path.unlink(missing_ok=True)
            return retained
        except OSError:
            pass  # e.g. another filesystem: fall back to a verified copy below
        else:
            path.unlink(missing_ok=True)
            return retained
    _require_space(retained.parent, path.stat().st_size)
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
            os.chmod(temporary, 0o644)
            try:
                os.link(temporary, retained)
            except FileExistsError:
                pass
            validate_retained(str(retained), checksum_sha256)
        finally:
            temporary.unlink(missing_ok=True)
    return retained
