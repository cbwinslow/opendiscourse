# GovInfo official-source digest — round 1

Accessed: 2026-09-29. Researcher received no project context.

- **BILLSTATUS bulk XML is unavailable for Congress 107** (high confidence).
  GPO documents Congressional Bill Status as covering the 108th Congress to
  present, so it cannot provide a 107th structured fallback. Sources:
  [GPO Developer Hub](https://www.govinfo.gov/developers),
  [Bill Status XML user guide](https://github.com/usgpo/bill-status/blob/main/BILLSTATUS-XML_User_User-Guide.md),
  and [GPO's 2020 backfill announcement](https://www.govinfo.gov/features/bill-status-xml-bulk-data)
  (2020-12-08).
- **Individual GovInfo BILLS packages can supply official 107th bill text and
  selected metadata** (high confidence). GPO says published bill versions are
  available from the 103rd Congress; its bulk bill-text XML begins only at the
  113th, so 107 requires individual packages. Example:
  [BILLS-107hr1ih](https://www.govinfo.gov/app/details/BILLS-107hr1ih) and its
  [MODS XML](https://www.govinfo.gov/metadata/pkg/BILLS-107hr1ih/mods.xml).
  This is not a complete bill-status or dated cosponsor ledger.
- **History of Bills (HOB) is an official historical fallback for bill details,
  actions, sponsor/cosponsor references** (high confidence for availability and
  content; medium for automated structured extraction). GPO says HOB covers
  1983–present and contains bill number, title, summary, sponsor/cosponsor,
  and chronological actions; it is publication/index material, not BILLSTATUS.
  Source: [GPO HOB help](https://www.govinfo.gov/help/hob), updated 2024-03-11.
- **Recommendation:** for a 107th bill fallback, use an individual BILLS
  package for text/package metadata and HOB for historical sponsor/cosponsor
  evidence, retaining each source's own URL and page/citation. Do not expect
  BILLSTATUS or treat BILLS/HOB as equivalent to structured Congress.gov
  cosponsor data.
