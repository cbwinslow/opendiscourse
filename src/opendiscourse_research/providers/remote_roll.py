"""What every official roll-call file source says about one file, and how it fails (Stories 11.1 and 11.2).

Both chambers publish one XML file per roll call. A provider tells the Connector, without downloading
the file, its URL, size and ``Last-Modified``; that pair is how a refreshed file is detected. A provider
that cannot get an answer raises :class:`RollFileError`; one whose origin says "not published"
raises :class:`RollFileNotFound`, which is the origin's state and not a failure.
"""

from __future__ import annotations

from dataclasses import dataclass


class RollFileError(RuntimeError):
    """A roll-call lookup failed or returned something unusable."""


class RollFileNotFound(RollFileError):
    """The origin does not publish that file (a listed but vacated roll, or a redirect to "not available")."""


@dataclass(frozen=True)
class RemoteRoll:
    """What the origin says about one roll-call file, without downloading it."""

    year: int
    number: int
    url: str
    size: int
    last_modified: str
