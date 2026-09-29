# Congress.gov official-source digest — round 1

Accessed: 2026-09-29. Researcher received no project context.

- **Congress.gov API v3 is the Library of Congress's documented machine
  interface for bill detail and cosponsors** (high confidence). Its documented
  routes include `GET /bill/{congress}/{billType}/{billNumber}` and
  `/cosponsors`. Sources: [Congress.gov API](https://api.congress.gov/),
  [LOC API repository](https://github.com/LibraryOfCongress/api.congress.gov),
  [OpenAPI document](https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/openapi.json),
  [bill endpoint documentation](https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/BillEndpoint.md).
- **Congress.gov public pages can be an emergency same-publisher fallback, not
  an independent source** (high confidence for the UI's data availability;
  medium for unattended HTML acquisition). A 107th bill page demonstrates
  historical details and a cosponsor count:
  [S. 2647, 107th Congress](https://www.congress.gov/bill/107th-congress/senate-bill/2647/all-actions?overview=closed).
  Retain exact URL, response headers, bytes, retrieval time, and checksum; later
  reconcile against API success.
- **THOMAS is not a live fallback** (high confidence). The Library retired it
  in 2016 following its transition to Congress.gov. Source:
  [LOC retirement announcement](https://www.loc.gov/item/prn-16-004/thomas-gov-to-retire-july-5/2016-04-28/),
  published 2016-04-28.
- **GovInfo is a useful but partial official fallback** (high confidence).
  It has 107th individual bill packages, but its own documentation says sponsor
  and cosponsor information is generally, not universally, present in bill
  actions. Do not use it to reconstruct a complete canonical 107th cosponsor
  roster. Source: [GovInfo bills help](https://www.govinfo.gov/help/bills),
  updated 2024-11-08.
