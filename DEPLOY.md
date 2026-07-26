# DEPLOY.md — ESF Enterprise Platform

All commands assume repo root. For brevity define:
```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
```

## First deployment
See **INSTALL.md**. In short:
```bash
$DC up -d --build
$DC exec app python scripts/create_admin.py
./scripts/prod_smoke_test.sh
```

## Application restart
```bash
$DC restart app          # restart just the app
$DC restart              # restart the whole stack
$DC ps                   # check health
```

## Update procedure (new code)
```bash
git pull
$DC build app                       # rebuild image with new code
$DC up -d                           # recreate changed containers (DB untouched)
# migrations run automatically on app start; confirm:
$DC exec app alembic current        # should show "(head)"
./scripts/prod_smoke_test.sh
```
Tip: take a database backup before updating (see BACKUP.md).

## Migration procedure
- **Automatic:** the app entrypoint runs `alembic upgrade head` on every start.
- **Manual / one-off:**
  ```bash
  $DC exec app alembic upgrade head        # apply
  $DC exec app alembic current             # show current revision
  $DC exec app alembic history --verbose   # list revisions
  ```

## Rollback procedure
1. **Code rollback** (preferred): redeploy the previous version.
   ```bash
   git checkout <previous-tag-or-commit>
   $DC build app && $DC up -d
   ```
2. **Schema rollback** (only if a migration must be reverted — back up first!):
   ```bash
   $DC exec app alembic downgrade -1        # step back one revision
   ```
   All migrations in this project are reversible. Downgrades that drop columns lose data in
   those columns — restore from backup if needed (BACKUP.md).
3. **Full restore** (worst case): `BACKUP.md → Recovery procedure`.

## Log inspection
```bash
$DC logs -f app          # application + uvicorn/access logs (follow)
$DC logs --tail=200 app  # last 200 lines
$DC logs nginx           # reverse-proxy access/error
$DC logs db              # PostgreSQL
```
Logs use the Docker json-file driver with rotation (configured in docker-compose.prod.yml).

## Stop / start
```bash
$DC stop                 # stop containers (data volumes preserved)
$DC up -d                # start again
$DC down                 # remove containers+network (named volumes preserved)
# DANGER: `$DC down -v` also deletes volumes (database + QR). Do NOT use in production.
```
