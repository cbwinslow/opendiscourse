from __future__ import annotations

import json
from datetime import datetime
from html.parser import HTMLParser

from .base import IngestionRun, client


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = None


def _yield_table(html: str) -> tuple[list[str], list[list[str]]]:
    parser = _TableParser()
    parser.feed(html)
    for index, row in enumerate(parser.rows):
        if row and row[0].strip().lower() == "date":
            return row, [
                r
                for r in parser.rows[index + 1 :]
                if len(r) == len(row) and r[0][:1].isdigit()
            ]
    raise ValueError("Treasury page did not contain a recognizable rate table")


def ingest_yield_curve(
    year: int, curve_type: str = "daily_treasury_yield_curve"
) -> int:
    url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
    params = {"field_tdr_date_value": str(year), "type": curve_type}
    with (
        client() as http,
        IngestionRun(
            "treasury.yield_curve",
            {"year": year, "curve_type": curve_type},
            mode="backfill",
        ) as run,
    ):
        response = http.get(url, params=params)
        response.raise_for_status()
        headers, rows = _yield_table(response.text)
        payload = {
            "headers": headers,
            "rows": rows,
            "curve_type": curve_type,
            "year": year,
        }
        payload_id = run.store_payload(response, payload)
        for row in rows:
            record = dict(zip(headers, row, strict=True))
            observed = datetime.strptime(record.pop("Date"), "%m/%d/%Y").date()
            with run.conn.cursor() as cur:
                for tenor, raw in record.items():
                    if raw in {"", "N/A"}:
                        continue
                    try:
                        value = float(raw)
                    except ValueError:
                        continue
                    cur.execute(
                        """INSERT INTO fact.measurement (dataset_id, field_id, period_start, vintage_date, value_numeric, unit, flags, source_payload_id)
                           VALUES ('treasury.yield_curve', %s, %s, %s, %s, 'percent', %s, %s)
                           ON CONFLICT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date)
                           DO UPDATE SET value_numeric = EXCLUDED.value_numeric, flags = EXCLUDED.flags, source_payload_id = EXCLUDED.source_payload_id""",
                        (
                            tenor,
                            observed,
                            observed,
                            value,
                            json.dumps({"curve_type": curve_type}),
                            payload_id,
                        ),
                    )
                    run.record_count += 1
            run.conn.commit()
        return run.record_count
