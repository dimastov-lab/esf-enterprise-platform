# BACKUP.md — ESF Enterprise Platform

```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
```

## What is state, and what is derived
- **Source of truth — PostgreSQL** (`pg_data` volume): documents, parties, items, totals,
  **snapshots** (immutable published copies, incl. their sha256 hashes), users, audit log.
  A `pg_dump` of the database backs up everything above, including all snapshots.
- **Derived / cacheable — `esf_storage` volume** (`/app/storage/qr`): generated QR PNGs.
  These can be regenerated from data, but backing them up is cheap.
- **PDFs are NOT stored** — they are rendered on demand from the snapshot, so there is nothing
  to back up; they regenerate identically after a restore.

So a complete backup = **PostgreSQL dump (required)** + **QR volume (optional)**.

## PostgreSQL backup
```bash
mkdir -p backups
$DC exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > "backups/esf_$(date +%F_%H%M).sql"
```
Automate (nightly cron on the host):
```cron
15 2 * * * cd /path/to/esf && docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec -T db pg_dump -U esf esf > "backups/esf_$(date +\%F).sql" 2>> backups/backup.log
```
Store copies off-host (object storage / another machine). Always back up **before** an update or
`alembic upgrade`.

## PostgreSQL restore
Restore into an empty database (stop the app first so nothing writes):
```bash
$DC stop app
$DC exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/esf_YYYY-MM-DD.sql
$DC start app
```
For a clean restore, recreate the database first:
```bash
$DC exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
$DC exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"
$DC exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/esf_YYYY-MM-DD.sql
```

## Snapshot backup
Snapshots live in the `esf_snapshots` table and are included in every `pg_dump`. They are
write-once; a restored dump preserves each snapshot's `payload_json` and `sha256`, so published
documents remain byte-identical and their PDFs re-render the same.

## Generated PDF backup
None required — PDFs are rendered from snapshots on request. After any restore they regenerate
automatically and identically.

## QR backup (optional)
```bash
docker run --rm -v esf_storage:/data -v "$PWD/backups:/out" alpine \
  tar czf /out/qr_$(date +%F).tgz -C /data .
```
Restore:
```bash
docker run --rm -v esf_storage:/data -v "$PWD/backups:/in" alpine \
  sh -c "cd /data && tar xzf /in/qr_YYYY-MM-DD.tgz"
```
(If you skip this, QR images are recreated on next request/publish from the document data.)

## Recovery procedure (full)
1. Provision the server and repo as in INSTALL.md (steps 1–5), set `.env.production`.
2. Start only the database: `$DC up -d db` and wait until healthy (`$DC ps`).
3. Restore the database dump (see *PostgreSQL restore*).
4. (Optional) restore the QR volume (see *QR backup*).
5. Start the rest: `$DC up -d`.
6. Verify: `./scripts/prod_smoke_test.sh` and spot-check a public verification URL + its PDF.
