"""A shared turnstile for one web host.

Download scripts ask for a turn before each request. The turnstile reads the
server's rate-limit headers and hands out start times at the fastest even pace
that stays inside that allowance. A lock file lets several scripts share one
allowance, the way a load balancer shares one pipe.

Congress.gov's allowance is a rolling hour (api.data.gov): requests spread
evenly across the hour keep flowing, while a burst spends the hour and then
sits idle. The pace is ``window / limit``. The remaining-count header is a
brake when this key was already used. A 429 waits for ``Retry-After``.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from pathlib import Path

Clock = Callable[[], float]
Sleeper = Callable[[float], None]
PROBE_GAP = 30.0
RESERVATION_TTL = 180.0
# A garbage header must not collapse the pause to zero.
MAX_LIMIT = 1_000_000
MAX_SLEEP = 5.0


def leading_int(value: str | None) -> int | None:
    """The first whole number in a rate-limit header, ignoring ``w=`` notes."""
    if not value:
        return None
    token = value.strip().split(",", 1)[0].split(";", 1)[0].strip()
    return int(token) if token.isdigit() else None


def retry_after_seconds(value: str | None, *, now: float) -> float | None:
    """Seconds to wait from ``Retry-After`` (a count or an HTTP date)."""
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        return None
    return max(0.0, when.timestamp() - now)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target and value is not None:
            return str(value)
    return None


class SharedRateGate:
    """Hand out one host's request turns to every script that shares ``path``."""

    def __init__(
        self,
        path: Path,
        *,
        fallback_limit: int,
        window_seconds: float = 3600,
        safety: int = 25,
        probe_gap: float = PROBE_GAP,
        clock: Clock = time.time,
        sleep: Sleeper = time.sleep,
    ) -> None:
        if fallback_limit < 1:
            raise ValueError("fallback_limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.path = path
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._fallback_limit = fallback_limit
        self._window_seconds = window_seconds
        self._safety = safety
        self._probe_gap = probe_gap
        self._clock = clock
        self._sleep = sleep
        self._thread = threading.Lock()
        self._cache: dict | None = None
        self._since_flush = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self) -> str:
        """Block until the next request may start. Return the turn's id."""
        while True:
            with self._exclusive():
                now = self._clock()
                state = self._current()
                self._prune(state, now)
                wait = self._wait(state, now)
                if wait > 0:
                    self._save(state)
                if wait <= 0:
                    token = uuid.uuid4().hex
                    state["reservations"].append({"id": token, "expires": now + RESERVATION_TTL})
                    state["next_start"] = now + self._interval(state)
                    if self._budget(state) <= 0:
                        # The empty-bucket probe is spent. Everyone else waits.
                        state["allow_probe"] = False
                        state["next_probe"] = now + self._probe_gap
                    self._save(state)
                    return token
            self._sleep(min(wait, MAX_SLEEP))

    def observe(self, token: str, status: int, headers: Mapping[str, str]) -> None:
        """Record one finished response so the next turn follows its headers."""
        with self._exclusive():
            now = self._clock()
            state = self._current()
            self._prune(state, now)
            state["reservations"] = [item for item in state["reservations"] if item["id"] != token]
            state["sent"].append(now)
            limit = leading_int(_header(headers, "x-ratelimit-limit"))
            if limit is not None and limit > 0:
                state["limit"] = min(limit, MAX_LIMIT)
            remaining = leading_int(_header(headers, "x-ratelimit-remaining"))
            if remaining is not None:
                state["remaining"] = remaining
            if status == 429:
                delay = retry_after_seconds(_header(headers, "retry-after"), now=now)
                if delay is None:
                    delay = self._interval(state)
                delay = min(delay, float(state["window_seconds"]))
                state["cooldown_until"] = max(float(state["cooldown_until"]), now + delay)
                state["allow_probe"] = True
                if remaining is None:
                    state["remaining"] = 0
            elif state["remaining"] is not None and int(state["remaining"]) > int(state["safety"]):
                state["allow_probe"] = False
                state["next_probe"] = 0
            self._save(state)

    def release(self, token: str) -> None:
        """Give back a turn whose request never reached the server."""
        with self._exclusive():
            state = self._current()
            state["reservations"] = [item for item in state["reservations"] if item["id"] != token]
            # A timeout may already have been counted by the server. Count it here too.
            state["sent"].append(self._clock())
            self._save(state)

    def _wait(self, state: dict, now: float) -> float:
        pace = max(0.0, float(state["next_start"]) - now, float(state["cooldown_until"]) - now)
        return max(pace, self._deficit_wait(state, now), self._self_cap_wait(state, now))

    def _budget(self, state: dict) -> int:
        remaining = state["remaining"]
        if remaining is None:
            return 10**9
        return int(remaining) - len(state["reservations"]) - int(state["safety"])

    def _deficit_wait(self, state: dict, now: float) -> float:
        """How long a nearly empty remaining-count holds the next turn.

        A cooldown already covers a 429. Once none of our own requests are still
        inside the window, the stored remaining count is stale and one new turn
        is allowed so the next response can refresh it.
        """
        if self._budget(state) > 0:
            state["clear_at"] = 0.0
            return 0.0
        if float(state["cooldown_until"]) > now:
            return 0.0
        # One follow-up after Retry-After. It does not reopen the whole hour.
        if state["allow_probe"]:
            return 0.0
        sent: list[float] = state["sent"]
        if sent:
            clear_at = min(sent) + float(state["window_seconds"])
            state["clear_at"] = clear_at
            return max(0.0, clear_at - now)
        clear_at = float(state["clear_at"])
        if clear_at and now >= clear_at:
            state["clear_at"] = 0.0
            return 0.0
        probe_at = float(state["next_probe"])
        if probe_at > now:
            return probe_at - now
        return 0.0

    def _self_cap_wait(self, state: dict, now: float) -> float:
        """Stop this process from sending more than ``limit`` in one window."""
        sent: list[float] = state["sent"]
        if len(sent) + len(state["reservations"]) < int(state["limit"]):
            return 0.0
        if not sent:
            return float(state["window_seconds"])
        return max(0.0, min(sent) + float(state["window_seconds"]) - now)

    def _interval(self, state: dict) -> float:
        return float(state["window_seconds"]) / max(int(state["limit"]), 1)

    def _prune(self, state: dict, now: float) -> None:
        window = float(state["window_seconds"])
        state["sent"] = [stamp for stamp in state["sent"] if stamp > now - window]
        state["reservations"] = [item for item in state["reservations"] if float(item["expires"]) > now]

    def _current(self) -> dict:
        """The turnstile state for this process.

        The request log stays in memory. Rewriting thousands of timestamps on
        every request was slower than the hour's own pace.
        """
        if self._cache is None:
            self._cache = self._load()
        return self._cache

    def _load(self) -> dict:
        if not self.path.is_file():
            return self._fresh()
        try:
            loaded = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return self._closed()
        if not isinstance(loaded, dict):
            return self._closed()
        fresh = self._fresh()
        fresh.update({key: loaded[key] for key in fresh if key in loaded})
        try:
            fresh["limit"] = min(max(int(fresh["limit"]), 1), MAX_LIMIT)
            fresh["next_start"] = float(fresh["next_start"])
            fresh["cooldown_until"] = float(fresh["cooldown_until"])
            fresh["next_probe"] = float(fresh["next_probe"])
            fresh["clear_at"] = float(fresh["clear_at"])
            fresh["allow_probe"] = bool(fresh["allow_probe"])
            fresh["sent"] = [float(item) for item in fresh["sent"]]
            fresh["reservations"] = [
                {"id": str(item["id"]), "expires": float(item["expires"])} for item in fresh["reservations"]
            ]
            if fresh["remaining"] is not None:
                fresh["remaining"] = int(fresh["remaining"])
        except (TypeError, ValueError, KeyError):
            return self._closed()
        # The hour length and the cushion come from this code, not an old file.
        fresh["window_seconds"] = self._window_seconds
        fresh["safety"] = self._safety
        return fresh

    def _closed(self) -> dict:
        """An unreadable file starts closed, so a crash cannot spend a fresh hour."""
        state = self._fresh()
        state["remaining"] = self._safety
        return state

    def _fresh(self) -> dict:
        return {
            "limit": self._fallback_limit,
            "window_seconds": self._window_seconds,
            "safety": self._safety,
            "next_start": 0.0,
            "cooldown_until": 0.0,
            "next_probe": 0.0,
            "clear_at": 0.0,
            "allow_probe": False,
            "remaining": None,
            "sent": [],
            "reservations": [],
        }

    def _save(self, state: dict) -> None:
        payload = dict(state)
        self._since_flush += 1
        # The pace and the remaining count are small. The timestamp log is not.
        if len(state["sent"]) >= 50 and self._since_flush < 25:
            payload["sent"] = []
        else:
            self._since_flush = 0
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload))
        os.replace(temporary, self.path)

    def _exclusive(self):
        gate = self

        class _Hold:
            def __enter__(self) -> None:
                gate._thread.acquire()
                self._handle = None
                try:
                    gate._lock_path.parent.mkdir(parents=True, exist_ok=True)
                    self._handle = gate._lock_path.open("a+")
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
                except Exception:
                    if self._handle is not None:
                        self._handle.close()
                    gate._thread.release()
                    raise

            def __exit__(self, *exc: object) -> None:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                self._handle.close()
                gate._thread.release()

        return _Hold()
