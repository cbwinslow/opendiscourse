"""The shared Congress.gov turnstile: pace, headers, and overlapping downloads."""

from __future__ import annotations

import threading
import time

import httpx
import pytest

from opendiscourse_research.ingestion.congress_bills import (
    download_parts,
    download_parts_best_effort,
)
from opendiscourse_research.providers.congress_api import CongressServerError
from opendiscourse_research.providers.congress_bills import CongressBillClient
from opendiscourse_research.rate_gate import SharedRateGate


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _gate(tmp_path, clock: _Clock, **kwargs) -> SharedRateGate:
    return SharedRateGate(
        tmp_path / "gate.json",
        fallback_limit=kwargs.pop("fallback_limit", 3600),
        window_seconds=kwargs.pop("window_seconds", 3600),
        safety=kwargs.pop("safety", 0),
        probe_gap=kwargs.pop("probe_gap", 30),
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )


def test_turns_are_spaced_at_the_full_allowance(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=3600, window_seconds=3600)
    gate.acquire()
    gate.acquire()
    assert clock.now == 1_001.0


def test_a_lower_header_replaces_the_starting_allowance(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=3600, window_seconds=3600)
    first = gate.acquire()
    gate.observe(first, 200, {"X-RateLimit-Limit": "1800", "X-RateLimit-Remaining": "1799"})
    gate.acquire()
    before = clock.now
    gate.acquire()
    assert clock.now - before == 2.0


def test_an_empty_remaining_count_waits_for_the_rolling_hour(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=10, window_seconds=100, safety=0, probe_gap=10_000)
    token = gate.acquire()
    gate.observe(token, 200, {"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "0"})
    before = clock.now
    gate.acquire()
    assert clock.now - before == 100.0


def test_too_many_requests_honors_retry_after(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=3600, window_seconds=3600)
    token = gate.acquire()
    gate.observe(token, 429, {"Retry-After": "15"})
    before = clock.now
    gate.acquire()
    assert clock.now - before == 15.0
    gate.acquire()
    # The follow-up is one try. The rest of the hour stays closed.
    assert clock.now == 4_600.0


def test_a_short_probe_does_not_reopen_a_spent_hour(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=10, window_seconds=100, safety=25, probe_gap=30)
    token = gate.acquire()
    gate.observe(token, 200, {"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "25"})
    before = clock.now
    gate.acquire()
    assert clock.now - before == 100.0


def test_a_wild_limit_header_cannot_remove_the_pause(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=3600, window_seconds=3600)
    token = gate.acquire()
    gate.observe(token, 200, {"X-RateLimit-Limit": "999999999", "X-RateLimit-Remaining": "100"})
    gate.acquire()
    before = clock.now
    gate.acquire()
    assert clock.now - before == pytest.approx(3600 / 1_000_000)


def test_a_broken_gate_file_does_not_spend_a_fresh_hour(tmp_path) -> None:
    clock = _Clock()
    path = tmp_path / "gate.json"
    path.write_text("{")
    gate = _gate(tmp_path, clock, safety=25)
    gate.acquire()
    before = clock.now
    gate.acquire()
    assert clock.now - before == 30.0


def test_two_gates_share_one_file(tmp_path) -> None:
    clock = _Clock()
    first = _gate(tmp_path, clock)
    second = _gate(tmp_path, clock)
    first.acquire()
    second.acquire()
    assert clock.now == 1_001.0


def test_a_lowered_limit_holds_turns_already_spent_in_the_hour(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=100, window_seconds=100, safety=0)
    token = ""
    for turn in range(3):
        token = gate.acquire()
        limit = "2" if turn == 2 else "100"
        gate.observe(token, 200, {"X-RateLimit-Limit": limit, "X-RateLimit-Remaining": "90"})
    gate.acquire()
    # Two of the three requests have to age out of the hour before another turn.
    assert clock.now == 1_101.0


def test_a_failed_part_keeps_the_bodies_already_returned() -> None:
    seen: list[str] = []

    class _Client:
        def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
            del congress, bill_type, number
            if name == "text":
                raise RuntimeError("text failed")
            return name.encode()

    with pytest.raises(RuntimeError, match="text failed"):
        download_parts(
            _Client(),
            106,
            "hr",
            "1",
            ("detail", "text"),
            workers=1,
            on_part=lambda name, body: seen.append(name),
        )
    assert seen == ["detail"]


def test_one_failed_part_keeps_the_parts_that_arrived() -> None:
    class _Client:
        def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
            del congress, bill_type, number
            if name == "cosponsors":
                raise CongressServerError("HTTP 500")
            return name.encode()

    found, errors = download_parts_best_effort(
        _Client(), 106, "sres", "218", ("detail", "actions", "cosponsors")
    )
    assert found["detail"] == b"detail"
    assert found["actions"] == b"actions"
    assert set(errors) == {"cosponsors"}
    assert "HTTP 500" in errors["cosponsors"]


def test_a_missing_key_is_not_a_skipped_part() -> None:
    class _Client:
        def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
            del congress, bill_type, number, name
            raise RuntimeError("CONGRESS_API_KEY is not set")

    with pytest.raises(RuntimeError, match="CONGRESS_API_KEY"):
        download_parts_best_effort(_Client(), 106, "sres", "218", ("detail", "cosponsors"))


def test_parts_download_overlap() -> None:
    current = 0
    peak = 0
    lock = threading.Lock()

    class _Client:
        def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
            nonlocal current, peak
            del congress, bill_type, number
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.05)
            with lock:
                current -= 1
            return name.encode()

    found = download_parts(_Client(), 106, "hr", "1", ("detail", "actions", "subjects", "text"))
    assert set(found) == {"detail", "actions", "subjects", "text"}
    assert peak >= 2


def test_a_server_error_is_not_the_same_as_a_refused_page() -> None:
    class _Gate:
        def acquire(self) -> str:
            return "turn"

        def release(self, token: str) -> None:
            del token

        def observe(self, token: str, status: int, headers: dict[str, str]) -> None:
            del token, status, headers

    def http(status: int) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, content=b"no", request=request)

        return httpx.Client(transport=httpx.MockTransport(handler))

    server = CongressBillClient(http=http(500), api_key="test", gate=_Gate())
    with pytest.raises(CongressServerError, match="HTTP 500"):
        server.part(106, "sres", "218", "cosponsors")
    refused = CongressBillClient(http=http(404), api_key="test", gate=_Gate())
    with pytest.raises(RuntimeError, match="refused"):
        refused.part(106, "sres", "218", "cosponsors")


def test_bill_client_follows_the_gate_instead_of_a_fixed_pause(tmp_path) -> None:
    clock = _Clock()
    gate = _gate(tmp_path, clock, fallback_limit=3600, window_seconds=3600)

    class _Http:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
            del url, headers
            self.calls += 1
            request = httpx.Request("GET", "https://api.congress.gov/v3/bill/106")
            return httpx.Response(
                200,
                content=b"{}",
                headers={"X-RateLimit-Limit": "3600", "X-RateLimit-Remaining": "3599"},
                request=request,
            )

        def close(self) -> None:
            return None

    http = _Http()
    client = CongressBillClient(http=http, api_key="test-key", gate=gate)
    client.list_page(106, 0)
    client.list_page(106, 250)
    assert http.calls == 2
    assert clock.now == 1_001.0
