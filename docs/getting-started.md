# Getting Started

This is the fastest path to a working local OpenDiscourse database. It uses
the Docker Compose Postgres service, not the bare-metal production setup
described in `README.md`.

## 1. Clone and configure

```bash
git clone https://github.com/cbwinslow/opendiscourse.git
cd opendiscourse
cp .env.example .env
```

Open `.env` and point `DATABASE_URL` at the Docker Compose database instead
of the bare-metal default:

```
DATABASE_URL=postgresql://research:change-me@localhost:5433/research
```

Leave `POSTGRES_*`, `OD_LAKE_ROOT`, and `DATA_ROOT` at their defaults for a
first run — they already point at a `./data-lake` folder inside this
checkout, which Docker creates automatically.

## 2. Start Postgres

```bash
docker compose up -d
```

## 3. Install and initialize

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[analytics,spatial,ingest]'
research-db init-db
```

`init-db` only creates schema and seeds the catalog of *known* datasets — it
never contacts a provider or downloads data.

## 4. Explore

```bash
research-db status   # catalog-ready datasets vs. registered-but-unimplemented
research-db browse    # interactive catalog browser
```

## Next steps

- Full adapter-by-adapter command reference: `README.md`
- How to add a new data source: `docs/adding-a-provider.md`
- How to propose a change: `CONTRIBUTING.md`
- If you're using an AI coding assistant on this repo, read `AGENTS.md` and
  `CLAUDE.md` first — they describe conventions this quickstart doesn't
  repeat.
- Running this for real, not local exploration: see the bare-metal
  PostgreSQL setup in `README.md`. Docker Compose here is a development
  convenience only.
