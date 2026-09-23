# Digest: economic source tooling

Accessed 2026-09-23. Decision served: when a maintained Python package saves
work without becoming a hidden data authority.

- `beaapi` is published by the U.S. BEA organization, supports dataset and
  parameter discovery, and is CC0. It is the clearest candidate to wrap as an
  optional acquisition adapter. It has a local metadata cache, so its cache
  location must be redirected into the configured data root or disabled.
  Source: [us-bea/beaapi](https://github.com/us-bea/beaapi).
- BLS itself publishes a small Python example for its API. That does not justify
  a new client dependency: a shared, well-tested HTTP adapter plus a source
  Connector is simpler and keeps raw responses and retry semantics under our
  control. Source: [BLS API Python guidance](https://www.bls.gov/developers/api_python.htm).
