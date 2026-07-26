# ESF Enterprise Platform — Release Candidate 1

A platform for issuing, storing, and publicly verifying **Kyrgyz electronic VAT invoices
(ЭСФ — СЧЁТ-ФАКТУРА, form STI-007 / Приложение 3)**. The HTML document is the visual source of
truth; the PDF is rendered from the same template, and published invoices are frozen into an
immutable snapshot with a QR-linked public verification page.

## Status

MVP feature-complete (Release Candidate 1). Lifecycle:
**DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED** (+ CANCELLED).

## Architecture

Layered, per `CODING_STANDARDS.md`: **Controller (router) → Service → Repository → Database**.

- **Backend:** FastAPI + SQLAlchemy 2.0, PostgreSQL only (one Base, one engine), Alembic migrations.
- **UI:** one Jinja template `app/templates/esf/form.html` renders **edit / view / public / pdf**
  modes — no duplicate layouts. Dense, hairline, document-style CSS (not Bootstrap).
- **PDF:** WeasyPrint renders the same HTML template (no ReportLab).
- **QR + public verification:** `qrcode` PNG → `/esf/check-esf?documentUUID=...` (published only).
- **Auth:** session login (signed cookie), bcrypt passwords, roles **ADMIN / ISSUER**.
- **Autosave:** debounced on change + every 10s on the edit form.

## Fonts

The document uses **DejaVu Sans** — the exact font embedded in the reference «Копия 6.pdf» —
bundled at `backend/app/static/fonts/` and used for HTML, the public page, and the PDF, so the
output matches the official form glyph-for-glyph.

## Prerequisites

- Docker (for PostgreSQL), Python 3.11 (matches the production image; the pinned
  security-patched dependencies require Python ≥3.10).
- macOS dev only: WeasyPrint needs Homebrew pango/cairo — `brew install pango`.
  (`pdf_service` injects `/opt/homebrew/lib` into the dyld path automatically.)

## Run

```bash
# 1) Database
docker compose up -d                       # PostgreSQL 15 on localhost:5432 (esf/esf/esf)

# 2) Backend deps
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # add -r requirements-dev.txt for tests

# 3) Schema
export DATABASE_URL=postgresql+psycopg2://esf:esf@localhost:5432/esf
alembic upgrade head

# 4) Run
uvicorn app.main:app --port 8011
# open http://127.0.0.1:8011/login
```

In development, a dev admin is auto-seeded: **admin / admin123**. Optional demo issuer via
`python scripts/seed_dev.py` (issuer / issuer123). These exist only when `ENVIRONMENT=development`.

## Using it

1. Log in → **Dashboard** (search / filter / sort).
2. **+ Новый ЭСФ** → fill the STI-007 form (autosaves).
3. **Проверить** (validate) → **Сформировать** (publish): freezes a snapshot, assigns the
   number, generates the QR, and locks the document (read-only).
4. **Результат** page: QR, public link, download PDF / QR.
5. **Public verification** (no login): `/esf/check-esf?documentUUID=<uuid>` — published only,
   served from the snapshot. `/pdf/<uuid>.pdf` renders from the snapshot for published docs.
6. Admins manage users at **/admin/users**.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg2://esf:esf@localhost:5432/esf python -m pytest tests/ -q
# 23 passed — transaction-isolated regression suite
```

## Configuration

See `.env.example` (`DATABASE_URL`, `SECRET_KEY`, `PUBLIC_BASE_URL`, `ENVIRONMENT`).

## Production deployment (Docker)

For a clean-server production install use the dedicated pack — do **not** use the dev steps below:
**INSTALL.md** (first install) → **DEPLOY.md** (updates/rollback) → **OPERATIONS.md** (runbook) →
**BACKUP.md** (backups). Stack: `docker-compose.prod.yml` + `backend/Dockerfile` +
`infra/nginx/nginx.conf`, configured via `.env.production` (template: `.env.production.example`).
Validate a running stack with `scripts/prod_smoke_test.sh`. See `PRODUCTION_REPORT.md` and
`RELEASE_NOTES.md`.

## Deployment (production, manual / non-Docker)

1. Set environment: `ENVIRONMENT=production`, a unique `SECRET_KEY`
   (`python -c "import secrets;print(secrets.token_hex(32))")`), `PUBLIC_BASE_URL=https://your-host`,
   and a production `DATABASE_URL`. **The app refuses to start in production with a default/empty
   `SECRET_KEY`** (fail-closed).
2. Provision PostgreSQL and run `alembic upgrade head`.
3. Install WeasyPrint native libs in the image (Debian/Ubuntu):
   `apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0`.
4. Serve over HTTPS behind a reverse proxy (the session cookie is `Secure` only when
   `ENVIRONMENT=production`). Run with a process manager, e.g.
   `uvicorn app.main:app --host 0.0.0.0 --port 8000` (add workers as needed).
5. In production the dev admin is NOT seeded and `/dev/esf-preview` is NOT mounted — create the
   first admin out-of-band (e.g. a one-off `AuthService(...).create_user(...)` script).

See `RELEASE_REPORT.md` for the production-hardening backlog (CSRF, rate limiting, audit log).

## Backup & Restore

State lives in two places: PostgreSQL (all documents, snapshots, users) and `backend/storage/qr`
(generated QR PNGs — regenerable from data, but cheap to back up).

```bash
# Backup (database)
docker compose exec -T db pg_dump -U esf esf > backup_$(date +%F).sql
# Backup (QR assets)
tar czf qr_$(date +%F).tgz backend/storage/qr

# Restore (into a fresh, empty database)
docker compose exec -T db psql -U esf -d esf < backup_YYYY-MM-DD.sql
tar xzf qr_YYYY-MM-DD.tgz
```

Notes: snapshots are immutable (write-once) — restoring a dump preserves the legal copies and
their sha256 hashes. Take backups before `alembic upgrade` on a schema change. For production,
schedule periodic `pg_dump` (e.g. nightly) and store off-host.

## Troubleshooting

- **WeasyPrint import/render fails on macOS** — `brew install pango`; the service adds
  `/opt/homebrew/lib` to the dyld path automatically.
- **`SECRET_KEY must be set...` on startup** — expected in production; set a real `SECRET_KEY`.
- **DB connection refused** — ensure `docker compose up -d` is healthy and `DATABASE_URL` matches.
- **Login fails in dev** — the dev admin (`admin`/`admin123`) is seeded only when
  `ENVIRONMENT=development`; or run `python scripts/seed_dev.py`.
- **Alembic “target database is not up to date”** — run `alembic upgrade head`.

## Project management

`CLAUDE.md` (charter), `PROJECT_STATE.md`, `ROADMAP.md`, `TODO.md`, `CHANGELOG.md`,
`TECHNICAL_DEBT.md`, `DEFINITION_OF_DONE.md`, `CODING_STANDARDS.md`.
Visual spec: `docs/UI_REFERENCE.md`; analysis: `docs/STEP0_ARCHITECTURE_REVIEW.md`.

## Known limitations (see `TECHNICAL_DEBT.md`)

Form fidelity is glyph-exact (DejaVu Sans, matched to the reference). Remaining items are
operational, not visual: general-route rate limiting (TD-013); macOS dyld hack for WeasyPrint
(TD-009, n/a on Linux/Docker); legacy `dev` user row retained (TD-006); in-process login rate
limiter (use a shared store for multi-worker, TD-019). Out of scope (require external systems):
tax-authority (ГНС) integration, digital signature (ЭЦП), and the resulting legal validity.
