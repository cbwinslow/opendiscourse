"""Roll-call vote Connectors by chamber, for ``research-db sync-votes`` (Stories 11.1 and 11.2).

A registry, not a dispatcher: the command never branches on a chamber. Adding a chamber is one entry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .house_votes import HouseVotesConnector
from .senate_votes import SenateVotesConnector

VOTE_CONNECTORS: dict[str, Callable[..., Any]] = {
    "house": HouseVotesConnector,
    "senate": SenateVotesConnector,
}
