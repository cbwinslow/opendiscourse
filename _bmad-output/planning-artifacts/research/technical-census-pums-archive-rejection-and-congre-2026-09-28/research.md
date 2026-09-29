# Census PUMS delivery rejection and Congress.gov recovery

Accessed: 2026-09-28

## Decision

Do not substitute third-party microdata or accept HTML error pages as data.
Report the reproducible Census delivery rejection to Census support, retain the
successful official artifacts, and resume the archive only after the original
endpoint returns a valid ZIP. Keep the two Congress 107 bills as proven
list-backed partial records until Congress.gov returns their detail responses.

## Findings

1. The 2019 five-year PUMS file is still part of Census's official PUMS
   publication. Census describes PUMS as untabulated person and housing-unit
   records and says PUMS is available through its FTP site; the 2019
   documentation page also lists 2015-2019 five-year PUMS materials.
   [1][2][3]
2. Direct probes on 2026-09-28 received an HTML page titled `Request Rejected`
   for both the 2019 `csv_hut.zip` and 2013 `csv_pdc.zip` primary URLs. The
   pages supplied support IDs `13427891563991649720` and
   `13427891564925662496`, respectively. This is a delivery/security rejection,
   not evidence that either dataset has been withdrawn.
3. Census tells people who receive a support ID to send the URL and support ID
   to Census support so it can investigate. Its ACS FTP page names
   `ftp2.census.gov` as the anonymous FTP server for the official directories,
   but the current project contract is HTTPS-only and therefore cannot switch
   transport without an explicit reviewed change. [4][5]
4. Census's Microdata API is not a practical substitute for a complete national
   archive: Census warns that raw-microdata queries with many variables or very
   large results can fail or time out, and recommends the FTP download for the
   full dataset. [6]
5. The two Congress 107 detail URLs continue to return HTTP 500 from the
   official Congress.gov API on 2026-09-28. The project has retained publisher
   list evidence and correctly leaves those bills partial rather than deriving
   details from another source.

## Options

| Option | Benefit | Risk / cost |
|---|---|---|
| Report Census support IDs and wait for the primary HTTPS ZIPs | Preserves the approved original-source and HTTPS evidence policy | Needs Census to correct its delivery block; transfer remains paused for blocked files. |
| Permit anonymous `ftp2.census.gov` for this archive after a contract change | Census itself documents that official server | Changes the approved HTTPS-only acquisition policy; must be separately reviewed, tested, and recorded. |
| Use Microdata API or data.census.gov as a replacement archive | May retrieve a narrow slice | Cannot prove a complete raw national archive and is unsuitable for the approved preservation goal. |
| Use a third-party mirror | Might be immediately available | Breaks the original-government-endpoint requirement; reject. |

Recommendation: report the two support IDs to Census and retain the approved
HTTPS policy while awaiting a response. Consider FTP only if Census confirms it
is the intended official remedy and the operator approves a reviewed contract
change. Do not use the API or a mirror as a silent replacement.

## Sources

| Ref | Source | Publisher | Accessed |
|---|---|---|---|
| [1] | [PUMS data access](https://www.census.gov/programs-surveys/acs/microdata/access.2022.html) | U.S. Census Bureau | 2026-09-28 |
| [2] | [2019 PUMS documentation](https://www.census.gov/programs-surveys/acs/microdata/documentation.2019.html) | U.S. Census Bureau | 2026-09-28 |
| [3] | [ACS data via FTP](https://www.census.gov/programs-surveys/acs/data/data-via-ftp.html) | U.S. Census Bureau | 2026-09-28 |
| [4] | [Census support-ID guidance](https://www.census.gov/help/topics/faq.when-i-tried-accessing-the-site-i-got-a-support-id.html) | U.S. Census Bureau | 2026-09-28 |
| [5] | [Census help center](https://www.census.gov/help.html) | U.S. Census Bureau | 2026-09-28 |
| [6] | [Microdata API limitations](https://www.census.gov/data/developers/guidance/microdata-api-user-guide/limitations-contact-us-and-appendix.html) | U.S. Census Bureau | 2026-09-28 |
