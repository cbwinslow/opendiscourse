# Download Congress bills, members, and votes

Each source is one command. The command downloads the publisher's file into
`DATA_ROOT`, keeps that file, and loads the database. Run the same command
again after a stop: it skips what is already loaded. No command reads a folder
that exists only on one machine.

Set `DATABASE_URL` and `DATA_ROOT` in `.env`. `uv run research-db init-db`
creates the tables and does not download anything.

```bash
uv sync --extra ingest
uv run research-db init-db
```

Members have to be loaded before votes, because a vote is stored against a
person's BioGuide id.

## Commands

| What | Years | Command |
|---|---|---|
| Members and terms | current file, back to the 1st Congress | `bash scripts/bootstrap_upstream.sh` then `uv run research-db load-legislators` |
| Current committee seats | the current roster | `uv run research-db sync-committee-membership` |
| Bills | 2003 onward (Congress 108 and later) | `uv run research-db sync-billstatus` |
| Bill text | 2013 onward (Congress 113–119) | `uv run research-db sync-bill-text` |
| Bills | 1973–2002 (Congress 93–107) | `uv run research-db sync-congress-bills --congress 93` |
| House roll calls | Congress 108–119 | `uv run research-db sync-votes --chamber house` |
| Senate roll calls | Congress 108–119 | `uv run research-db sync-votes --chamber senate` |
| Voteview scores | all Congresses in Voteview's file | `uv run research-db sync-voteview` |

Repeat `--congress` to choose years. Examples:

```bash
uv run research-db sync-billstatus --congress 118 --congress 119
uv run research-db sync-votes --chamber senate --congress 119
uv run research-db sync-congress-bills --congress 106 --congress 107
```

`sync-congress-bills` with no `--congress` loads only Congresses 106 and 107.
It refuses Congress 108 and later, because those bills come from GovInfo.
GovInfo has no bill-text zip before Congress 113. Official roll calls in this
loader start at Congress 108.

`sync-congress-bills` needs `CONGRESS_API_KEY` in `.env`. The other commands
in the table do not.

`load-legislators` is the one command that does not download by itself. The
bootstrap script clones the public `unitedstates/congress-legislators` project
into `vendor/` (that folder is not committed). The command checks that
checkout, copies the two member files into `DATA_ROOT`, and loads people and
terms. Committee seats are a separate download: `sync-committee-membership`
fetches its own three files.

`sync-voteview` downloads Voteview's member, roll-call, and party files. It
does not download the file of every member's vote, and it does not replace
the official House and Senate roll calls.

## When a command finishes

The command prints JSON.

- Exit 0: that source is complete.
- Exit 1: it stopped. Files and rows already saved stay. Run the same command again.
- Exit 2: it loaded what it could and something needs a look. The JSON names the gap. A rerun is safe.

Two copies of the same command must not run at once. The second one stops
immediately and says another sync is in progress.

## Commands that are not this download

- `research-db sync` refreshes catalog notes. It does not download these files.
- `research-db ingest congress-bill` fetches one bill.
- `research-db load-billstatus` reads a GovInfo archive that is already on disk and already checked. Use `sync-billstatus` to download.
- `research-db load-openstates-votes` reads the OpenStates copy. The official roll calls are `sync-votes`.
