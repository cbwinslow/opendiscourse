# Source contract and status

Each source contract must declare a stable dataset identifier, publisher,
approved selection, cadence, source-of-truth endpoint policy, storage/capacity
rules, lifecycle approval, and target layers. It may describe a generated
manifest, but it must not claim that a static YAML list is the factual download
record.

The status report joins these views:

| Question | Authority |
|---|---|
| What is approved to be collected? | `inventory/contracts/*.yaml` |
| What files were retained or failed? | `ingest.artifact` and its checksum/version fields |
| What source run wrote them? | `ingest.run` / run ledger |
| What reached stage and published tables? | Connector-specific evidence-linked row counts |
| What remains intentionally unavailable? | Explicit contract gaps |

Fallbacks are a small, source-specific ordered list at the provider boundary.
They apply only after a transient response—such as an HTTP 5xx, a retryable
network failure, or HTML returned for an expected binary file—and only after the
candidate is verified to be an official publisher URL for the same artifact.
