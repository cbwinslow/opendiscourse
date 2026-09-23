# Digest: regulatory, legal, and elections sources

Accessed 2026-09-23. Decision served: which complementary sources can be
introduced without weakening provenance, licensing, or identity controls.

- FederalRegister.gov offers public API endpoints without API keys, but its
  content is not itself the legal-notice copy; the official GovInfo edition must
  remain the evidentiary record for legal conclusions. Source: [Federal Register
  API documentation](https://www.federalregister.gov/developers/documentation/api/v1).
- Regulations.gov exposes GET endpoints for dockets, documents, and comments,
  and requires a normal API integration. Source: GSA, [Regulations.gov
  API](https://open.gsa.gov/api/regulationsgov/).
- CourtListener offers APIs, bulk-data guidance, webhooks, and database
  replication, but access and rate limits are membership-dependent. It is a
  later, separately scoped legal-data source; do not assume a free full-corpus
  load. Source: Free Law Project, [developer access
  overview](https://www.courtlistener.com/help/).
- OpenElections maintains standardized results built from official state/local
  sources and retains source files separately from converted data. It is an
  excellent coverage/normalization reference, not the project’s sole source of
  evidence. Source: [OpenElections GitHub organization](https://github.com/openelections).
- MIT Election Lab publishes research-oriented election data, including a 2024
  precinct project. It is a strong cross-check and methodology source, but
  should not bypass the project’s reviewed person-identifier gate. Sources:
  [MIT Election Lab](https://electionlab.mit.edu/) and [2024 Precinct Project
  method note](https://electionlab.mit.edu/articles/inside-2024-precinct-project).
- House disclosure data carries statutory use restrictions. Do not automate or
  promote it until the identity bridge, source terms, and a source-specific
  specification are reviewed. Source: [House Clerk disclosure
  search](https://disclosures-clerk.house.gov/FinancialDisclosure/ViewSearch).
