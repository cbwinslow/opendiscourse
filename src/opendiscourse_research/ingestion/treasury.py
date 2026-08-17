from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from .base import IngestionRun, client

# The HTML TextView page only ever renders the current ~2 years of data for
# a given `field_tdr_date_value`; requesting an older year returns Treasury's
# generic site-landing markup instead of an error, which a naive HTML-table
# scrape can't distinguish from "no data". The site's own CSV export,
# advertised via a <link rel="alternate" type="text/csv"> on that page,
# serves the full published history (verified back to 1995) for the same
# `field_tdr_date_value`/`type` query, so use that directly instead of
# scraping rendered HTML.
CSV_URL_TEMPLATE = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)


def ingest_yield_curve(
    year: int, curve_type: str = "daily_treasury_yield_curve"
) -> int:
    url = CSV_URL_TEMPLATE.format(year=year)
    params = {
        "field_tdr_date_value": str(year),
        "type": curve_type,
        "page": "",
        "_format": "csv",
    }
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
        rows = list(csv.reader(io.StringIO(response.text)))
        if not rows or rows[0][0].strip().lower() != "date":
            raise ValueError(
                f"Treasury CSV for {year} did not contain a recognizable rate table"
            )
        headers = rows[0]
        data_rows = [row for row in rows[1:] if row and row[0].strip()]
        payload = {
            "headers": headers,
            "rows": data_rows,
            "curve_type": curve_type,
            "year": year,
        }
        payload_id = run.store_payload(response, payload)
        for row in data_rows:
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
