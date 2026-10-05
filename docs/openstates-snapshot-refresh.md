# OpenStates monthly snapshot refresh

Status: design, not implemented. Approved direction, 2026-10-05.
Does not authorize a political-core migration, a state-data promotion, or a
change to issue #100 / draft PR #107.

## What this is for

`openstates` is a replaceable read-only copy of the publisher's PostgreSQL
dump. `opendiscourse` is our warehouse. Congress, GovInfo, House, and Senate
rows are never written into `openstates`. Researchers query `opendiscourse`.

The July 2026 audit did not prove which file created the database that is
named `openstates` today. That gap stays unresolved history. It is not waived.
This design replaces that database as the active baseline only after
OpenDiscourse itself records the download, the checksum, the restore, and the
fingerprint of a newer snapshot. The first target is the October 2026 public
dump. The month name is not the identity. The SHA-256 of the bytes is.

## What already exists

- Download, without restore: `ingestion/openstates.py` `download_monthly_dump`.
  The data URL is `https://data.openstates.org/postgres/monthly/YYYY-MM-public.pgdump`.
  The schema URL is `https://data.openstates.org/postgres/schema/YYYY-MM-schema.pgdump`.
  On 2026-10-05 those URLs answered HTTP 200 for 2026-08, 2026-09, and 2026-10.
  The registered copy is still `data-2026-07`.
- The downloader keeps a checksum-named file and registers an artifact version.
  `bootstrap openstates-dump` now checks the publisher headers on every run.
  The official page (https://open.pluralpolicy.com/data, retrieved 2026-10-05)
  says to build the address as
  `https://data.openstates.org/postgres/monthly/YYYY-MM-public.pgdump`,
  that the file updates through the month, and that the link can be missing
  at the start of a month. The same ETag, last-modified time, and size reuse
  the saved file. Any difference downloads again, appends an artifact version,
  and keeps the old bytes. `data-2026-10` is a label, not the identity.
- The live reader is the foreign-data server `openstates_local` on database
  `opendiscourse`, port 5434. It points at `dbname=openstates` through the
  local socket, with each remote session started as `openstates_fdw`.
  Imported tables live in schema `openstates_source`. Application roles can
  read them. They cannot create the server or the login.
- `pg_restore` into the live `openstates` database, and any change to that
  foreign server, are outside issue #100. That issue forbids source writes
  and reader changes. Implementation of this design is a separate story.

## Identity of a snapshot

Every acquired snapshot records all of these. The checksum is the identity.

| Fact | Where it lives |
| --- | --- |
| Official URL | artifact `remote_url` |
| Requested year and month | artifact key `data-YYYY-MM` plus metadata |
| Retrieval time | artifact `downloaded_at` |
| Byte size | `bytes_downloaded` |
| SHA-256 | `checksum_sha256` |
| HTTP status, content type, and final URL | artifact metadata |
| Artifact id | `ingest.artifact.artifact_id` |
| `pg_restore --list` manifest and its SHA-256 | artifact metadata, saved beside the dump |
| Database fingerprint after restore | relation names, columns, row counts, and a hash of that structure |

The schema dump for the same month is a second artifact, `schema-YYYY-MM`,
with its own checksum. It is not a substitute for the data dump.

## Stages

The active database name stays `openstates` until the last step. The reader
keeps pointing at that name. A half-restored database is never that name.

1. **Discover.** Resolve the requested month, defaulting to the newest month
   whose data URL and schema URL both exist. Record the URLs. Do not guess a
   month from the database that is already loaded.
2. **Capacity.** Fail before the transfer if the disk cannot hold the download,
   the restored candidate, and the previous snapshot together. The July file
   is about 10.7 GB compressed. The database now named `openstates` is about
   38 GB. October will be the same order of size. The capacity gate fails
   closed on an unknown size.
3. **Download.** Use the existing artifact downloader. Re-request the current
   month even when a file for that key is already saved. If the new checksum
   matches a saved version, reuse that version. If it differs, append a new
   artifact version and keep the old bytes. Never overwrite a retained file.
4. **Validate the archive.** Require a stable checksum of the retained file,
   a non-empty `pg_restore --list`, and the expected archive members for the
   public Open Civic Data tables used by the audit. Reject HTML, a short
   file, or a list that does not contain `opencivicdata_bill`,
   `opencivicdata_person`, and `opencivicdata_voteevent`.
5. **Restore the candidate.** Create a new database whose name includes the
   month and the first 12 hex characters of the checksum, for example
   `openstates_202610_<sha12>`. Restore only into that name. Do not restore
   into `opendiscourse` or into `openstates`. The restore role may create
   that database. It may not own `opendiscourse` objects.
6. **Fingerprint the candidate.** Connect to the candidate directly, not
   through `openstates_source`. Save the relation and column manifest, nested
   JSON paths the audit already knows how to measure, row counts, and the
   structural hash. Store that fingerprint on the artifact.
7. **Drift.** Compare that fingerprint with the last approved promotion
   baseline. The July audit is not that baseline, because its restore was
   never proven. The first October snapshot that passes this workflow becomes
   the new baseline. A later month fails closed when a relation, column, or
   nested path used by the approved mapping appears, disappears, or changes
   type. New unused publisher tables are reported and do not by themselves
   activate a promotion. They do block a silent change to a mapped field.
8. **Activate.** Only after steps 4 through 7 pass:
   - revoke new connections to `openstates` for `openstates_fdw`;
   - terminate existing backends connected to `openstates`;
   - rename `openstates` to `openstates_previous_<sha12>` (or
     `openstates_previous_unattested` when the current database has no
     recorded checksum);
   - rename the candidate to `openstates`;
   - grant connect back.
   Rename is a catalog change, not a copy. The foreign server keeps
   `dbname=openstates`, so the reader follows the new database without an
   imported-table rewrite when the mapped columns still match. If a mapped
   column changed, activation stops and the foreign tables are not altered
   inside this story; that is a separate reader approval.
   `RENAME DATABASE` cannot run inside a transaction. The critical section is
   the revoke, terminate, two renames, and grant. If the second rename fails,
   rename the previous database back to `openstates` before granting connect.
9. **Rollback.** Keep the renamed previous database until the new snapshot
   has been read successfully through `openstates_source` and its fingerprint
   has been stored. Rollback is the same rename sequence in reverse. Do not
   delete the previous database in the activating run. Do not delete the
   dump file.

## What activation does not do

- It does not promote state bills, people, or votes into `core`.
- It does not create `bill_federal_identity` or the new identifier tables.
- It does not fabricate federal bill type or number.
- It does not edit draft PR #107 or mark issue #100 complete.
- It does not rewrite the July audit to claim a restore proof that was not
  recorded.

After October is active, the read-only audit command is run again against
that exact artifact id and database fingerprint. If the relation, column, and
nested-field fingerprint matches the July audit, record the match and reuse
the field review only where the structures are the same. If it differs,
regenerate the affected dispositions and leave them unapproved. Human approval
has to name this snapshot, not the unresolved July one.

## Identifier link, measured and not yet written

`openstateslink.py` matches rows only by identifier. It was run read-only on
2026-10-05 against the database currently named `openstates`. That database
is still the unattested historical copy, not the October baseline. No owned
row was inserted or updated.

| Link | Result |
| --- | --- |
| BioGuide people | 722 OpenStates BioGuide ids, 722 matched an owned person, 0 missing, 0 conflicts |
| Federal bills | 70,880 United States bills, all 70,880 matched Congress + type + number |
| Federal votes | 1,828 OpenStates events grouped into 1,827 official keys, all 1,827 keys matched; one key has two events |

State bills such as `HB 264` are not given a federal type or number. Twitter,
Facebook, YouTube, Instagram, email, phone, fax, office address, links,
names, and every other non-empty person column are kept as contact records.
Only BioGuide selects an owned person. A handle shared by two OpenStates
people is stored on both and does not merge them. The same function will be
run again after the October snapshot is activated, and only that rerun may
attach new identifier assertions.

The contact tables in the publisher database are `opencivicdata_person`
(including `email`, `extras`, and `current_role`),
`opencivicdata_personidentifier` (`scheme`, `identifier`),
`opencivicdata_personlink`, `opencivicdata_personname`,
`opencivicdata_personsource`, and `openstates_personoffice` (`address`,
`voice`, `fax`, `name`, `classification`). None of these columns is a reason
to skip a row. Owned tables that require a BioGuide id
(`core.person_social_account`, `core.district_office`) can receive the
federal rows after the BioGuide link is clean. State people who have no
BioGuide id keep the same fields on the OpenStates person. They are not
discarded, and they are not copied onto a different person because the
handle looks familiar.

## How the two datasets stay one warehouse

Promotion is a later story. The rules below are the contract that story must
implement. This workflow only prepares the snapshot.

- An OpenStates id that already points at one of our rows updates that same
  row's id. It does not allocate a second person, bill, or vote.
- A new assertion about a name or a title is stored with this snapshot's
  artifact id. Older assertions stay. Display uses the precedence rules.
  The losing value is kept.
- An id missing from a later dump does not delete our row. Record that this
  snapshot did not contain it, including a last-seen snapshot id. Do not set
  an end date, a death, a resignation, a repeal, or a deletion unless the
  source states that fact.
- A person matches only by an identifier an auditable crosswalk states.
  BioGuide and an OpenStates person id may name the same person only when
  that crosswalk says so. Name, party, district, office, biography, email,
  phone, and Twitter do not. Those values are still stored.
- From one month to the next, the same OpenStates id keeps the same owned
  row. A new phone number or handle is a new assertion with that snapshot's
  checksum. The old value stays. The displayed value follows precedence.
  An id that is absent from the new dump is marked not seen in that snapshot.
  It is not deleted, and the absence does not set an end date.
- A state bill's identity is jurisdiction + legislative session + official
  identifier. `HB 264` is an official identifier, not a title. State bills
  wait until the shared bill tables exist.
- A federal bill keeps Congress, bill type, and bill number on the federal
  extension designed in the political-core mapping. The official House and
  Senate files remain the authority for their own vote totals.
- The transitional vote keys `us-<year>-lower-<roll>` and
  `us-<year>-upper-<roll>` may link an OpenStates event to an official roll
  only where that mapping is already tested. The OpenStates vote id stays in
  the identifier table and never in `roll_number`. Several OpenStates events
  may map to one roll call. The duplicate-identifier query in
  `votereconcile.py` is the known evidence. Keep each source event.

## Tests the implementation must have

- A second download of unchanged bytes reuses the artifact version.
- A changed body at the same month URL appends a version and keeps the first file.
- Restore refuses to target `openstates` or `opendiscourse`.
- A candidate that fails the archive list or the fingerprint is not renamed.
- A failed second rename restores the previous database name.
- The foreign server still says `dbname=openstates` after success.
- The July audit files are not edited to assert a checksum they did not record.

## Separate from the audit branch

Implement this on a new branch and a new issue. Do not add the restore to
`feat/openstates-audit-story-1`. That branch may later rerun its read-only
audit against the activated artifact. It does not perform the download or
the rename.
