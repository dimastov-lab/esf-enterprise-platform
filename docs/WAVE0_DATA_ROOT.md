# Wave 0 data-root evidence

Issue: [#26](https://github.com/dimastov-lab/esf-enterprise-platform/issues/26)  
Accepted source revision: `a5df81ca1175f49f62a1b1c4039c5c5d1df616c6`

## Retained production-root contract

- Compose project: `esf-enterprise-clean-starter`
- PostgreSQL volume: `esf-enterprise-clean-starter_pg_data`
- QR volume: `esf-enterprise-clean-starter_esf_storage`
- Application DSN contract:
  `postgresql+psycopg2://esf:<password>@db:5432/esf` (the checked example is
  `.env.production.example`; the real password remains outside Git).

`docker-compose.prod.yml` pins the project and both physical volume names, so a
production Compose invocation from another checkout cannot derive alternate
roots from the worktree name. Development Compose uses `tmpfs` and therefore
cannot create or retain a second PostgreSQL data root.

## Backup and restore evidence

- Custom-format dump: `/Users/dmitrijcernikov/.config/esf/backups/pre-acceptance-20260808.dump`
- SHA-256: `529aaa6499e83c6ddececbc5a62ccabeff940391f3851b9f9f782a62bfc0e093`
- Captured: `2026-08-08T16:54:11+0300`
- Verification: `pg_restore --list` succeeded and contains table data for
  `alembic_version`, `audit_logs`, `esf_documents`, and `esf_snapshots`.

The detailed restore procedure is in `BACKUP.md`. A destructive restore drill
was intentionally not performed against the active production stack. It
requires an isolated empty database and explicit operator approval.

## Quarantine register

`esf-enterprise-clean-starter_postgres_data` — **QUARANTINED / NO-USE**.

It was observed locally on 2026-08-08 with Compose label
`com.docker.compose.volume=postgres_data`. It is the former development root,
is not referenced by either current Compose file, and must not be attached,
renamed, migrated, or deleted under this issue. Human authorization is required
for any later destructive disposition.
