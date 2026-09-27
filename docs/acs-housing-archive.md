# ACS PUMS and AHS archive refresh

The archive starts with discovery, not download. The connector turns official Census
directory indexes into a manifest of data packages, dictionaries, release notes, and
codebooks. Review the exact byte count and its capacity report before approving a
transfer; an unknown size stops the run.

Run `uv run python -m opendiscourse_research.ingestion.acs_archive --all-official-indexes`
first to discover and capacity-check every approved PUMS and AHS release directory. A
reviewed YAML `--indexes <reviewed-indexes.yaml>` list is available for a deliberately
smaller retry. Review the manifest output, then rerun the same command with
`--approve-transfer` to retain bytes under `DATA_ROOT`. A restart uses the newest usable artifact and stages rows with
artifact/member/ordinal lineage. Do not use the older `acs_load` table-estimate loader
for PUMS or AHS, and do not start this archive while the separate 2021--2024 ACS
five-year detailed-table load is active.

PUMS records are public sample records at PUMA geography, not identified households and
not county-level data. The generator includes each published AHS release from 2001 onward:
the national series and the intervening metropolitan releases. AHS national and metropolitan
files are separate components; only the current relational CSV representation publishes records. Flat or superseded files may
remain evidence but never create duplicate observations. The manifest explicitly records
the 2020 standard ACS one-year absence and other publisher gaps.
