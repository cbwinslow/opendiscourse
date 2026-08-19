from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert

from ..db import session
from ..models.core import measurement_table
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
        measurement = measurement_table()
        for row in data_rows:
            record = dict(zip(headers, row, strict=True))
            observed = datetime.strptime(record.pop("Date"), "%m/%d/%Y").date()
            with session() as active_session:
                for tenor, raw in record.items():
                    if raw in {"", "N/A"}:
                        continue
                    try:
                        value = float(raw)
                    except ValueError:
                        continue
                    statement = insert(measurement).values(
                        dataset_id="treasury.yield_curve",
                        field_id=tenor,
                        geography_id=None,
                        period_start=observed,
                        period_end=None,
                        vintage_date=observed,
                        value_numeric=value,
                        unit="percent",
                        flags={"curve_type": curve_type},
                        source_payload_id=payload_id,
                    )
                    active_session.execute(
                        statement.on_conflict_do_update(
                            index_elements=(
                                measurement.c.dataset_id,
                                measurement.c.field_id,
                                measurement.c.geography_id,
                                measurement.c.period_start,
                                measurement.c.period_end,
                                measurement.c.vintage_date,
                            ),
                            set_={
                                "value_numeric": statement.excluded.value_numeric,
                                "flags": statement.excluded.flags,
                                "source_payload_id": statement.excluded.source_payload_id,
                            },
                        )
                    )
                    run.record_count += 1
        return run.record_count
