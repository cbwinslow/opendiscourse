"""Roll-call vote Connectors by chamber, for ``research-db sync-votes`` (Story 11.1).

The House is here; the Senate (Story 11.2) adds one entry. A registry, not a dispatcher: the command
never branches on a chamber.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .house_votes import HouseVotesConnector

VOTE_CONNECTORS: dict[str, Callable[..., Any]] = {"house": HouseVotesConnector}
