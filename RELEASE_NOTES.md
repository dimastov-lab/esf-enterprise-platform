# RELEASE_NOTES.md

## ESF Enterprise Platform — Version 1.0 RC1

Release milestone: **1.0 RC1** (production-ready candidate). Internal build string:
`config.VERSION = 1.1.x` (incremented during the visual-fidelity work; see CHANGELOG.md).

A platform for creating, validating, publishing, and publicly verifying Kyrgyz electronic VAT
invoices (ЭСФ — СЧЁТ-ФАКТУРА, form STI-007 / Приложение 3).

### Completed features
- **STI-007 document** reproduced in original HTML/CSS — one template renders edit / view /
  public / PDF (no duplicate layouts). Glyph-exact (bundled **DejaVu Sans**, the font embedded
  in the reference form).
- **Lifecycle:** DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED (+ CANCELLED), with a
  validation engine and a generate/publish workflow.
- **Immutable snapshots** at publish (JSON payload + sha256; ORM-enforced write-once). Public
  page and PDF for published documents render from the snapshot.
- **PDF** rendered from the same template via WeasyPrint (vector, A4 landscape).
- **QR + public verification:** `/esf/check-esf?documentUUID=…` (PUBLISHED only); QR encodes the
  official `https://esf.salyk.kg/...` format.
- **Editable header** so a document reproduces official values exactly: number (102), issue date
  (103); status 101 shows «первоначальный (Принят)» when published.
- **Auth + RBAC:** session login (bcrypt, signed cookie), roles ADMIN / ISSUER, owner isolation,
  admin user management.
- **Audit log** of critical actions (admin viewer at /admin/audit).
- **Autosave** (debounced + every 10s), **CSRF protection**, **login rate limiting**.
- **Dashboard** with search / status filter / sortable columns.
- **23-test** transaction-isolated regression suite.

### Known limitations
- **No tax-authority (ГНС) integration, no digital signature (ЭЦП)** → issued documents have no
  legal validity; this is a faithful functional + visual clone, not a connected ESF system.
- On a *live* document the QR encodes its own UUID and the timestamp is the real publish time
  (the byte-identical reference reproduction is the preview clone).
- Login rate-limiter is in-process (per worker) — use a shared store (Redis) for strict,
  multi-worker limits.
- No general-route rate limiting; no structured/centralized logging; error pages are plain.

### Production recommendations
- Always run behind **HTTPS** (session cookies are `Secure` in production).
- Set a unique `SECRET_KEY` and strong DB password; keep `.env.production` out of version control.
- Schedule nightly `pg_dump` backups, stored off-host (BACKUP.md).
- For strict brute-force protection across workers, front login with a shared rate limiter / WAF.
- Monitor container health (`docker compose ps`) and ship logs to a central system.

### Planned — Version 1.1
- Shared-store (Redis) rate limiting + general request throttling.
- Structured/centralized logging and metrics; styled error pages.
- Self-service password reset and richer user administration.
- Multi-sheet invoices and the correction workflow (fields 406/407).
- CI pipeline with a dedicated test database.
- (If/when in scope) GNS integration and digital signature for legally valid issuance.
