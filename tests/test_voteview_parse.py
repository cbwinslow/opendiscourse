"""Voteview number parsing. The database tests live in test_voteview_connector.py."""

from __future__ import annotations

import csv
import io

import pytest

from opendiscourse_research.ingestion.voteview import (
    _MEMBER_FIELDS,
    _PARTY_FIELDS,
    _whole,
    parse_members,
    parse_parties,
)
from opendiscourse_research.repositories.voteview import _batches


def _csv(fields: tuple[str, ...], row: dict[str, object]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    return buffer.getvalue().encode()


def _filled(fields: tuple[str, ...], **overrides: object) -> dict[str, object]:
    row: dict[str, object] = dict.fromkeys(fields, "")
    row.update(overrides)
    return row


def test_whole_accepts_a_trailing_decimal_zero_and_refuses_a_fraction() -> None:
    assert _whole("0.0", "district", required=False) == 0
    assert _whole("200.0", "party", required=True) == 200
    assert _whole(1.0, "session", required=False) == 1
    assert _whole("", "district", required=False) is None
    with pytest.raises(ValueError, match="must be an integer"):
        _whole("1.5", "district", required=False)
    with pytest.raises(ValueError, match="must be an integer"):
        _whole(1.5, "district", required=False)


def test_member_and_party_rows_keep_codes_voteview_wrote_as_decimals() -> None:
    members = parse_members(
        _csv(
            _MEMBER_FIELDS,
            _filled(
                _MEMBER_FIELDS,
                congress=103,
                chamber="President",
                icpsr=99909,
                state_icpsr=99,
                district_code="0.0",
                party_code="100.0",
                bioname="CLINTON, William Jefferson (Bill)",
                state_abbrev="USA",
            ),
        )
    )
    assert (members[0]["district_code"], members[0]["party_code"], members[0]["icpsr"]) == (
        0,
        100,
        "99909",
    )

    parties = parse_parties(
        _csv(
            _PARTY_FIELDS,
            _filled(
                _PARTY_FIELDS,
                congress=119,
                chamber="President",
                party_code="200.0",
                party_name="Republican",
            ),
        )
    )
    assert parties[0]["party_code"] == 200


def test_rows_are_split_before_a_database_value_gets_too_large() -> None:
    rows = [{"n": index, "record": "x" * 30} for index in range(5)]
    batches = _batches(rows, max_bytes=120)
    assert len(batches) > 1
    assert [row for batch in batches for row in batch] == rows
    oversized = [{"record": "x" * 200}]
    with pytest.raises(ValueError, match="cannot be stored"):
        _batches(oversized, max_bytes=80)
