# Project Handover — ESF Enterprise Platform

**Audience:** the engineering team taking ownership of this project.
**Purpose of this doc:** the single onboarding entry point. Read this first, then the two files in
§"What to read first". Estimated time to first productive change: **half a day to one day.**

---

## 1. Project purpose

A platform for issuing, storing, and publicly verifying **Kyrgyz electronic VAT invoices**
(ЭСФ — СЧЁТ-ФАКТУРА, form **STI‑007 / Приложение 3**). It reproduces the official salyk.kg form
glyph‑for‑glyph and models its full lifecycle:

```
DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED   (+ CANCELLED)
```

On publication a document is frozen into an **immutable snapshot** (JSONB payload + sha256). The
snapshot — not the live row — is the source of truth for the PDF and the public verification page.
The HTML template is the visual source of truth; the PDF is rendered from that **same** template.

**Out of scope (require government infrastructure):** tax‑authority (ГНС) integration, digital
signature (ЭЦП), and the resulting legal validity. These are intentionally not simulated.

---

## 2. Architecture overview

Strict layering, no shortcuts:

```
Controller (FastAPI router) → Service (business logic) → Repository (data access) → Database
```

- **No business logic in routers, no SQL outside repositories, no DB access from templates.**
- **Backend:** FastAPI + SQLAlchemy 2.0 (typed `Mapped[...]`), PostgreSQL only (one `Base`, one
  engine), Alembic migrations. Schema is managed by migrations — never `create_all`.
- **UI:** one Jinja template `app/templates/esf/form.html` renders **edit / view / public / pdf**
  from a `mode` flag — no duplicate layouts. Dense, document‑style CSS (not Bootstrap).
- **PDF:** WeasyPrint renders the same HTML (no ReportLab). Fonts bundled (DejaVu Sans).
- **QR + public page:** `qrcode` PNG → `/esf/check-esf?documentUUID=…` (published docs only,
  served from the snapshot).
- **Auth:** session login (signed cookie), bcrypt, roles **ADMIN / ISSUER**, owner isolation,
  session‑bound double‑submit **CSRF**, in‑process login rate limiting.
- **Observability:** per‑request `X-Request-ID`, structured JSON access logs, clean 500 handler
  (`app/core/observability.py`).

**Key invariants — do not break these:**
1. Snapshots are write‑once (an ORM guard raises on any UPDATE/DELETE of `ESFSnapshot`).
2. Publication is atomic (single transaction; rolls back fully on any failure).
3. A published document is read‑only; corrections create a new linked draft, they never mutate.
4. The public UUID behavior and publication semantics are stable contract — treat as frozen.

---

## 3. Folder structure

```
ESF-Enterprise-Clean-Starter/
├─ backend/
│  ├─ app/
│  │  ├─ core/          config, security (auth/CSRF), passwords, ratelimit, observability
│  │  ├─ db/            SQLAlchemy Base + engine/session
│  │  ├─ models/        13 ORM models (document, snapshot, party, item, totals, user, audit…)
│  │  ├─ repositories/  5 repos — the ONLY place SQL lives
│  │  ├─ routers/       5 routers — auth, esf, api, admin, dev_preview
│  │  ├─ services/      9 services — esf, snapshot, validation, pdf, qr, auth, audit, good…
│  │  ├─ static/        CSS, bundled fonts, images
│  │  ├─ templates/     Jinja (esf/form.html is the multi-mode document)
│  │  └─ main.py        app assembly, middleware, routers, dev-only startup seed
│  ├─ alembic/          migrations (7; head = a7d4e91c25f8)
│  ├─ scripts/          create_admin.py, seed_dev.py, verify_schema.py
│  ├─ tests/            test_regression.py (55 tests) + conftest (SAVEPOINT isolation)
│  ├─ Dockerfile        production image (python:3.11-slim + WeasyPrint native libs)
│  ├─ docker-entrypoint.sh   migrates then starts uvicorn
│  ├─ requirements.txt / requirements-dev.txt / pyproject.toml
│  └─ legacy/           superseded early code — NOT used at runtime, excluded from lint/CI
├─ infra/nginx/         production reverse-proxy config (TLS, headers, static)
├─ scripts/             prod_smoke_test.sh (host-side)
├─ docs/                UI reference, architecture review, screenshots
├─ docker-compose.yml           dev: PostgreSQL only
├─ docker-compose.prod.yml      prod: db + app + nginx
├─ .env.example / .env.production.example
└─ *.md                README + this handover + certification/ops docs (see §"Reports")
```

---

## 4. Technology stack

| Layer | Choice | Version |
|-------|--------|---------|
| Runtime | Python | **3.11** (production + CI; deps require ≥3.10) |
| Web | FastAPI / Starlette | 0.138.1 / 1.3.x |
| Server | uvicorn (workers) | 0.34 |
| ORM / migrations | SQLAlchemy / Alembic | 2.0.30 / 1.13 |
| Database | PostgreSQL | 15 |
| PDF | WeasyPrint | 69 |
| QR / images | qrcode / pillow | 7.4 / 12.2 |
| Templating | Jinja2 | 3.1.6 |
| Auth | bcrypt, itsdangerous (signed session) | — |
| Lint | ruff (F, I) | pinned in `pyproject.toml` |
| Tests | pytest (+ pytest-cov) | 55 tests, ~90% coverage |
| Proxy | Nginx | 1.27 |

All runtime dependencies pass `pip-audit` with **no known vulnerabilities** (verified on Python
3.11). Versions are kept current with the advisory DB; `pip-audit` runs in CI.

---

## 5. Deployment

- **Local dev:** `docker compose up -d` (Postgres) → `alembic upgrade head` → `uvicorn app.main:app`.
  Full steps in `README.md`.
- **Production (VPS, Docker + Nginx + HTTPS):** follow **`DEPLOY_UBUNTU.md`** — the complete
  step‑by‑step guide (server prep, DNS, `.env.production`, TLS via Let's Encrypt, first admin,
  smoke test, backup/restore). Concise alternatives: `INSTALL.md`, `DEPLOY.md`.
- Production stack: `docker-compose.prod.yml` (db + app + nginx). The app entrypoint auto‑runs
  migrations. Only nginx is exposed (80/443); Postgres is internal.

---

## 6. Operations

- **Runbook:** `OPERATIONS.md`; day‑2 quick reference in `DEPLOY_UBUNTU.md` §13.
- **Health:** `GET /` (app JSON), `GET /healthz` (nginx edge). Compose healthchecks on all services.
- **Logs:** structured JSON to stdout, captured by Docker's json‑file driver with rotation. Trace a
  request by its `X-Request-ID`.
- **Config:** environment only (`.env.production`) — `DATABASE_URL`, `SECRET_KEY` (fail‑closed in
  prod), `PUBLIC_BASE_URL`, `ENVIRONMENT`, `WEB_CONCURRENCY`, `TZ`, DB pool/timeout knobs.

---

## 7. Backup & restore

- **Critical state:** PostgreSQL (`pg_data` volume) — documents, snapshots, users. QR PNGs
  (`esf_storage`) are regenerable from the DB.
- **Backup:** `pg_dump` via `docker compose exec -T db` (nightly cron example in `DEPLOY_UBUNTU.md`
  §11; also `BACKUP.md`). Take a dump before every schema migration.
- **Restore:** pipe a gzipped dump into `psql` (`DEPLOY_UBUNTU.md` §12). Immutable snapshots and
  their sha256 hashes survive dump/restore intact. **Test a restore into a scratch DB at least once.**

---

## 8. CI

`.github/workflows/ci.yml` (GitHub Actions), Python 3.11 with a Postgres 15 service:
`ruff check` → `alembic upgrade head` → `pytest --cov` → `pip-audit -r requirements.txt`.
`.pre-commit-config.yaml` runs ruff + hygiene hooks locally. Keep CI green before merging.

---

## 9. Testing

- `backend/tests/test_regression.py` — **55 tests** covering field round‑trip, validation,
  atomic publication, snapshot immutability, corrections/cancellation, CSRF, RBAC/owner isolation,
  pagination/search/sort, batch ops, PDF/QR, and public‑page rendering.
- Isolation: each test runs in a SAVEPOINT rolled back at the end (`conftest.py`) — the suite leaves
  the database unchanged and is repeatable.
- Run: `cd backend && python -m pytest -q` (needs a running Postgres + `DATABASE_URL`). Use
  `python -m pytest` (not bare `pytest`) so `app` is importable.

---

## 10. Production checklist

See `DEPLOY_UBUNTU.md` §15 for the full list. Essentials: real `SECRET_KEY` + DB password,
`ENVIRONMENT=production`, valid TLS certs + renewal, all services healthy, first admin created,
smoke test GREEN, nightly backups running, a restore rehearsed.

---

## 11. Known limitations

- **External systems out of scope:** ГНС integration, ЭЦП digital signature, legal validity — these
  require government infrastructure and are intentionally absent (not faked).
- **Rate limiting is per‑process** (in‑memory). For strict limits use one worker or an external store
  (`TECHNICAL_DEBT.md` TD‑019).
- **Pagination is OFFSET/LIMIT.** Correct and fast to large sizes; for multi‑million‑row deep paging,
  keyset pagination would be the next step (`SCALABILITY_REPORT.md`).
- **WeasyPrint on macOS dev** needs a dyld path shim (`brew install pango`); n/a on Linux/Docker
  (TD‑009).
- **Residual advisory risk:** none in shipped runtime deps at handover time; re‑audit periodically as
  new CVEs are published (that's what the CI `pip-audit` step is for).

---

## 12. Future roadmap

Short list (details in `ROADMAP.md` / `TECHNICAL_DEBT.md`):
1. Distributed login rate limiting (shared store) for multi‑worker strictness.
2. Keyset pagination if datasets reach multi‑million rows.
3. Multi‑sheet document support (needs an official multi‑sheet reference to implement faithfully).
4. Opt‑in stricter lint rules (ruff `B`, `UP`) behind a one‑off modernization PR.

---

## 13. Technical debt

Tracked in `TECHNICAL_DEBT.md` (IDs referenced throughout the code/docs). None of it blocks
production. The `backend/legacy/` tree is dead code retained for history — it is excluded from lint
and CI and can be deleted once nobody references it for context.

---

## 14. Support notes

- The app **refuses to start in production without a real `SECRET_KEY`** — this is intentional
  (fail‑closed), not a bug.
- In production the dev admin is **not** seeded and `/dev/esf-preview` is **not** mounted; create the
  first admin with `backend/scripts/create_admin.py` (see `DEPLOY_UBUNTU.md` §9).
- Published documents are immutable by design — "why can't I edit/delete this?" is expected; use a
  correction (new linked draft) or cancellation instead.
- If tests fail only on a fresh database, check fixtures that scrape rendered HTML — the dashboard's
  hidden CSRF input only renders when rows exist (the `conftest` login helper falls back to the JS
  token for exactly this reason).

---

## 15. What to read first

1. **`README.md`** — what the system is, how to run it locally, using it end‑to‑end.
2. **`DEPLOY_UBUNTU.md`** — how it runs in production (also the clearest picture of the moving parts).
3. Then skim `CLAUDE.md` (project charter/rules), `TECHNICAL_DEBT.md`, and
   `ENTERPRISE_FINAL_CERTIFICATION.md` (category‑by‑category posture).

Reports & history (background, not required to be productive): `CHANGELOG.md`, `SCALABILITY_REPORT.md`,
`COMPLIANCE_*`, `FINAL_*`, `ENTERPRISE_*_REPORT.md`. These are historical audit trails — the current,
authoritative operational docs are the three above.

---

## 16. Estimated onboarding time

| Milestone | Time |
|-----------|------|
| Local stack running, logged in, one ESF published | ~1–2 hours |
| Comfortable with the layered flow (router→service→repo) and the snapshot invariants | ~half a day |
| First safe change merged (with a passing test) | ~1 day |
| Confident doing a production deploy + restore drill | ~1–2 days |

The codebase is intentionally small and consistent (**~3,200 LOC of application Python**, 5 routers /
9 services / 5 repositories / 13 models). Once the layering and the four invariants in §2 click, it
is quick to navigate.
