# Independent verification digest — round 1

Accessed: 2026-09-29. Researcher received no project context.

- **Verified:** GovInfo Developer Hub says Congressional Bill Status covers the
  108th Congress to present. It cannot be a structured 107th fallback.
  Sources: [GPO Developer Hub](https://www.govinfo.gov/developers) and
  [GPO release explanation](https://www.govinfo.gov/features/bill-status-xml-bulk-data).
- **Verified with qualification:** BILLS bulk XML begins at the 113th Congress.
  The Congressional Bills collection has published versions from the 103rd
  onward, but early availability must not be described as XML; GPO identifies
  PDF/HTML for the early period. Sources: [GPO Developer Hub](https://www.govinfo.gov/developers),
  [Congressional Bills collection](https://www.govinfo.gov/app/collection/bills/119/%7B%22pageSize%22%3A20%7D),
  [BILLS XML user guide](https://www.govinfo.gov/bulkdata/BILLS/resources/BILLS-XML_User-Guide-v2.pdf).
- **Verified:** THOMAS retired after transition to Congress.gov, so it is not a
  live official routine fallback. It does not prove that no historical capture
  exists anywhere. Source: [LOC announcement](https://www.loc.gov/item/prn-16-004/thomas-gov-to-retire-july-5/2016-04-28/).
- **Verified / design-policy distinction:** RFC 9110 supports that HTTP 500 is
  not proof of absence. Recording an official fallback as separate evidence is
  a project provenance decision, not a rule imposed by HTTP. Source:
  [RFC 9110 section 15.6.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.6.1).
