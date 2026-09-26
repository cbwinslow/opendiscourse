"""Congress.gov bill JSON parsing. No database and no network."""

from __future__ import annotations

import json

import pytest

from opendiscourse_research.ingestion.congress_bills import (
    CongressBillConnector,
    assemble_bill,
    parse_list_page,
)


def test_list_page_reads_the_identity_and_the_next_offset() -> None:
    bills, nxt = parse_list_page(
        json.dumps(
            {
                "bills": [{"congress": 107, "type": "HR", "number": "1"}],
                "pagination": {"next": "https://api.congress.gov/v3/bill/107?offset=250&limit=250"},
            }
        ).encode()
    )
    assert bills == [{"congress": "107", "bill_type": "HR", "number": "1"}]
    assert nxt == 250


def test_detail_becomes_a_bill_with_sponsor_actions_and_subjects() -> None:
    parsed = assemble_bill(
        detail=json.dumps(
            {
                "bill": {
                    "congress": 107,
                    "type": "HR",
                    "number": "1",
                    "title": "A tax bill",
                    "introducedDate": "2001-01-03",
                    "latestAction": {"actionDate": "2001-02-01", "text": "Passed House."},
                    "sponsors": [{"bioguideId": "A000360", "fullName": "Smith, Bob"}],
                    "policyArea": {"name": "Taxation"},
                }
            }
        ).encode(),
        actions=json.dumps(
            {"actions": [{"actionDate": "2001-01-03", "text": "Introduced", "type": "IntroReferral"}]}
        ).encode(),
        subjects=json.dumps(
            {"subjects": {"policyArea": {"name": "Taxation"}, "legislativeSubjects": [{"name": "Income tax"}]}}
        ).encode(),
        cosponsors=json.dumps({"cosponsors": [{"bioguideId": "B000001", "fullName": "Lee, Ann"}]}).encode(),
    )
    assert (parsed["bill_type"], parsed["bill_number"], parsed["introduced_date"]) == ("hr", "1", "2001-01-03")
    assert parsed["sponsorships"][0]["role"] == "sponsor"
    assert parsed["sponsorships"][1]["role"] == "cosponsor"
    assert parsed["actions"][0]["description"] == "Introduced"
    assert parsed["subjects"][1]["label"] == "Income tax"
    assert parsed["record"]["bill"]["title"] == "A tax bill"


def test_congress_108_is_refused_so_govinfo_bills_stay_put() -> None:
    with pytest.raises(ValueError, match="108"):
        CongressBillConnector((108,), http=object())
