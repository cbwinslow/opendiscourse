# Digest: public finance and influence sources

Accessed 2026-09-23. Decision served: whether OpenDiscourse should adopt
third-party tooling or retain direct-source Connectors for its next public-policy
sources.

- CBO publishes basic cost-estimate metadata in XML back to the 105th Congress.
  Its existing BILLSTATUS record already supplies links for the currently scoped
  bill estimates. Use that existing record first; a separate downloader is not
  justified until it adds something measurable. Source: CBO, [Cost Estimates -
  XML](https://www.cbo.gov/cost-estimates/xml).
- FEC offers both a nightly-updated REST API and transaction-level bulk downloads.
  Bulk data remains the correct history and evidence path; the API is useful for
  discovery and reconciliation. Source: FEC, [OpenFEC developer
  documentation](https://api.open.fec.gov/developers).
- LDA.gov provides the official REST API for LD-1, LD-2, and LD-203 filings.
  A direct HTTP Connector is enough; an R client is not a useful foundation for
  this Python project. Source: LDA.gov, [Download API](https://lda.gov/api/).
- USAspending exposes its official API and a large official open-source service.
  The government service's own repository has Docker, database, and search
  dependencies, so it is not a dependency candidate. A small third-party Python
  client can be evaluated as an optional request adapter, but its responses must
  still be retained by our Connector. Sources: [USAspending
  API](https://api.usaspending.gov/), [government API
  repository](https://github.com/fedspendingtransparency/usaspending-api), and
  [usaspending-orm](https://github.com/planetary-society/usaspending-orm).
