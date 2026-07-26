# TECHNICAL_DEBT.md

## Active

### TD-001 — Quarantined generic Sprint 3–11 code
- **Severity:** Low (isolated, not imported)
- **Module:** `backend/legacy/`
- **Description:** The original generic "Electronic Submission Form" implementation
  (title/applicant/description Document + Snapshot, generic services/routers/templates,
  SQLite session, dual Base, ReportLab PDF) is kept for reference only.
- **Risk:** Confusion if someone imports from it; stale dependencies (reportlab, qrcode)
  referenced only there.
- **Fix Plan:** Delete the quarantine directory once Sprints 4R–8R reimplement the needed
  behavior on the new schema. Until then, do not import from it.
- **Status:** Open (intentional, tracked)

### TD-002 — Snapshot immutability not yet enforced at write time
- **Severity:** Medium
- **Module:** `app/models/esf_snapshot.py`
- **Description:** `ESFSnapshot` carries an `immutable` flag and is intended to be
  write-once, but nothing yet prevents UPDATE/DELETE of snapshot rows (no service guard,
  no DB trigger). Schema-only sprint.
- **Risk:** A future code path could mutate a published snapshot, breaking the "source of
  truth" guarantee.
- **Fix Plan:** Enforce in the Snapshot service (Sprint 6R) — reject mutations; optionally
  add a DB rule/trigger and verify `sha256` on read.
- **Status:** ✅ RESOLVED (Sprint 8R) — `ESFSnapshot` `before_update`/`before_delete` ORM
  listeners raise `SnapshotImmutableError`; `sha256` content hash stored and verified.

### TD-003 — `raw_payload` vs `snapshots.payload_json` discipline
- **Severity:** Low
- **Module:** `app/models/esf_document.py`, `app/models/esf_snapshot.py`
- **Description:** Two JSON columns exist with different roles: `esf_documents.raw_payload`
  (auxiliary, mutable) and `esf_snapshots.payload_json` (frozen legal copy). The rule
  "normalized fields/items are the source of truth, never `raw_payload`" is documented but
  not yet enforced by code.
- **Risk:** A future reader could mistakenly render the form from `raw_payload`.
- **Fix Plan:** In the document service (Sprint 4R), treat `raw_payload` as write-only
  metadata; render exclusively from normalized columns/items.
- **Status:** ✅ RESOLVED — `ESFService.serialize` renders exclusively from normalized
  columns/items; `raw_payload` is never read. Published rendering uses `snapshots.payload_json`.

### TD-004 — Dev preview route + mock data are temporary
- **Severity:** Low
- **Module:** `app/routers/dev_preview.py`, `app/dev_sample.py`
- **Description:** `GET /dev/esf-preview` and `SAMPLE_ESF` exist only to preview the template.
  They render hardcoded sample data and perform no DB access.
- **Risk:** If left after CRUD lands, they could mask missing real wiring or expose a sample
  document in non-prod environments.
- **Fix Plan:** In Sprint 5R, wire `form.html` to real persisted ESF data; remove or repoint
  the dev route and delete `dev_sample.py` (or convert it into a test fixture).
- **Status:** Open (intentional, deferred to Sprint 5R)

### TD-005 — Visual deltas vs. official PDF (to refine in Sprint 5R/7)
- **Severity:** Low (cosmetic)
- **Module:** `app/templates/esf/form.html`, `app/static/css/esf_form.css`
- **Description:** The reproduction is close but not pixel-exact. Known deltas:
  (a) INN/branch-INN render only as many boxed cells as characters present — the official form
  shows a fixed run of empty cells; (b) field-code chips sit in a full-height left column rather
  than a tiny box in each cell's top-left corner; (c) goods-table column widths are auto-sized,
  not fixed to the PDF proportions; (d) borders are 1px vs the PDF's ~0.5px hairline;
  (e) font is Arial Narrow with Arial fallback (wider on non-mac systems).
- **Risk:** Print/PDF fidelity (Sprint 7) and exact-match expectations.
- **Fix Plan:** Fixed-count digit boxes; corner-anchored code chips; explicit column widths;
  hairline borders; bundle/define a condensed font for PDF rendering.
- **Status:** ✅ RESOLVED (v1.1.2) — fixed-count digit boxes, corner code chips, explicit column
  widths, 0.5px hairlines, matched vertical proportions, and the **exact font** (DejaVu Sans,
  the font embedded in «Копия 6.pdf») bundled and used for HTML + PDF. Output is a pixel-faithful clone.

### TD-006 — Auth is a development stand-in
- **Severity:** Medium
- **Module:** `app/core/security.py`
- **Description:** `get_current_user` get-or-creates a single non-admin `dev` user; there is no
  login. The owner/admin guard (`require_owner_or_admin`) is real and already enforced at the
  service layer, but every request currently resolves to the same user.
- **Risk:** No real access control until auth lands; not safe for production exposure.
- **Fix Plan:** Replace `get_current_user` with session-based auth + RBAC in Sprint 9R; the
  guard call sites stay unchanged. ESF routes should be gated behind login then.
- **Status:** ✅ RESOLVED (Sprint 9R) — session login (bcrypt + signed cookie), roles
  ADMIN/ISSUER, admin user management, all ESF routes gated. NOTE: the legacy `dev` user row
  remains (owns earlier docs) but cannot authenticate; admins manage those docs.

### TD-007 — Partial field bindings (visible fields without a schema column)
- **Severity:** Low
- **Module:** `app/templates/esf/form.html`, `app/services/esf_service.py`, ESF models
- **Description:** Several STI-007 fields are rendered (for fidelity) but have no column in the
  Sprint 3R schema, so they are view-only / not persisted: party branch-INN (203/303),
  tax-office code boxes (206/306 code portion; the name binds to `parties.tax_office`),
  `parties.bik` (207 binds only to `bank` text), correction №/date (406), item НсП-rate, and
  item customs refs (Реквизиты таможенной декларации).
- **Risk:** Users may expect these to save; they don't.
- **Fix Plan:** Decide per field whether to extend the schema (add columns) or formally drop
  from the editable set; do this alongside the validation/snapshot work.
- **Status:** ✅ RESOLVED (v1.1) — added columns `parties.branch_inn`, `parties.tax_office_code`,
  `esf_items.customs_refs` (migration 9ea18ef4e591); fields now bound and persisted.

### TD-008 — Duplicate esf_number raises a 500
- **Severity:** Low
- **Module:** `app/services/esf_service.py` (save), `esf_documents.esf_number` UNIQUE
- **Description:** Saving a draft with an `esf_number` already used by another document raises
  an IntegrityError (HTTP 500). Numbers are intended to be assigned at publish, not hand-typed.
- **Risk:** Poor UX on collision; unhandled 500.
- **Fix Plan:** Validate uniqueness in the Validation Engine (Sprint 6) and/or auto-assign the
  number at publish; surface a friendly field error instead of a 500.
- **Status:** ✅ RESOLVED (Sprint 8R) — field 102 is read-only; numbers are auto-assigned at
  publish via `next_esf_number()` with a uniqueness loop, so no user-typed collisions.

### TD-009 — WeasyPrint native libs (macOS dev) & PDF source
- **Severity:** Low
- **Module:** `app/services/pdf_service.py`
- **Description:** WeasyPrint needs pango/cairo/gobject. On macOS dev these come from Homebrew
  and the service injects `/opt/homebrew/lib` into `DYLD_FALLBACK_LIBRARY_PATH` at runtime.
  Also, the PDF currently renders from the live document's view data; once the Snapshot Engine
  exists, published PDFs must render from the immutable snapshot payload, not the live row.
- **Risk:** Hardcoded Homebrew path is dev-specific; pre-publish data could be rendered as if final.
- **Fix Plan:** In Docker/Linux install the libs via the image (no DYLD hack needed); switch the
  PDF source to the snapshot for PUBLISHED documents in the snapshot sprint.
- **Status:** Partially resolved (Sprint 8R) — PUBLISHED PDFs now render from the snapshot.
  Remaining: the macOS-only DYLD/Homebrew path hack (replace with proper libs in Docker/Linux).

### TD-010 — Public verification not yet publish-gated; QR not embedded in the document
- **Severity:** Medium
- **Module:** `app/routers/esf.py` (`esf_public_check`), `templates/esf/form.html`
- **Description:** The public page (`/esf/check-esf`) renders ANY existing document by UUID,
  because the publish workflow/snapshot doesn't exist yet. Security intent is that only
  PUBLISHED documents are publicly verifiable, served from the immutable snapshot. Also, the
  document footer still shows a "QR-код (Sprint 7)" placeholder box; the real QR image is
  served via `/qr/{uuid}.png` and shown on the result page, but is not yet embedded into the
  document template footer.
- **Risk:** Drafts are publicly viewable by UUID; document PDF/footer lacks the live QR.
- **Fix Plan:** When the Snapshot/publish sprint lands: restrict `/esf/check-esf` to PUBLISHED,
  render public + PDF from the snapshot, and embed `<img src="/qr/{uuid}.png">` into the footer
  `qr-box` for published documents.
- **Status:** ✅ RESOLVED (Sprint 8R) — `/esf/check-esf` is PUBLISHED-only and serves the
  snapshot; the footer embeds the live QR for published docs (HTML + PDF).

### TD-011 — QR encodes a relative path in dev
- **Severity:** Low
- **Module:** `app/services/qr_service.py`, `app/core/config.py`
- **Description:** With `PUBLIC_BASE_URL` unset (dev default), the QR encodes the bare path
  `/esf/check-esf?documentUUID=...`, which a phone scanner can't open without a host.
- **Risk:** Dev QR isn't directly scannable.
- **Fix Plan:** Set `PUBLIC_BASE_URL` in deployment so the QR encodes an absolute URL.
- **Status:** ✅ RESOLVED (v1.1.3) — default `PUBLIC_BASE_URL=https://esf.salyk.kg`; QR encodes the
  official-format absolute URL (verified against the reference QR).

### TD-012 — Field 101 shows internal lifecycle status
- **Severity:** Low
- **Module:** `app/services/esf_service.py` (STATUS_LABELS), `templates/esf/form.html`
- **Description:** Field 101 «СТАТУС» displays the internal lifecycle status (Черновик/
  Опубликован…) rather than the tax-authority status from the official form
  ("первоначальный (Принят)").
- **Risk:** Cosmetic divergence from the official document semantics.
- **Fix Plan:** Decide on an official-status field separate from the internal lifecycle when
  tax-authority integration is scoped.
- **Status:** ✅ RESOLVED (v1.1.3) — field 101 shows the ESF fiscal status «первоначальный (Принят)»
  for published docs (matches the official form); internal lifecycle remains on the dashboard.

### TD-013 — Public verification has no rate limiting
- **Severity:** Low
- **Module:** `app/routers/esf.py` (`esf_public_check`, `esf_qr`)
- **Description:** Open public routes have no throttling; UUIDs are unguessable but endpoints
  are unauthenticated.
- **Risk:** Potential scraping/abuse at scale.
- **Fix Plan:** Add rate limiting / caching in production hardening.
- **Status:** Open (production hardening)

### TD-014 — No CSRF protection on state-changing forms
- **Severity:** Medium
- **Module:** `app/routers/esf.py`, `app/routers/auth.py`, `app/routers/admin.py`
- **Description:** POST routes (save, autosave, validate, publish, delete, login, create-user)
  rely on the session cookie but have no CSRF token. Same-origin only, but cross-site POST is
  not blocked.
- **Risk:** CSRF on authenticated state changes.
- **Fix Plan:** Add CSRF tokens (hidden field + header for fetch) or SameSite=strict + origin
  checks in production hardening.
- **Status:** ✅ RESOLVED (v1.1) — session-bound double-submit token; `require_csrf` on all
  state-changing POSTs; hidden field in forms + `X-CSRF-Token` for fetch; invalid → 403.

### TD-015 — Framework deprecation warnings
- **Severity:** Low
- **Module:** `app/main.py` (`@app.on_event`), router `TemplateResponse(name, {...})` calls
- **Description:** FastAPI/Starlette warn that `on_event` should be a lifespan handler and that
  `TemplateResponse` should take `request` first. Functional, but deprecated.
- **Risk:** Will break on a future Starlette/FastAPI major.
- **Fix Plan:** Migrate startup seed to a `lifespan` handler; swap to
  `TemplateResponse(request, name, context)` signature.
- **Status:** Open (low priority; production hardening)

### TD-016 — Tests share the dev database; publish writes QR files
- **Severity:** Low
- **Module:** `backend/tests/`, `app/services/qr_service.py`
- **Description:** Regression tests are transaction-isolated (rolled back) but run against the
  dev database and the QR publish path writes PNGs to `storage/qr` (filesystem, not rolled back).
- **Risk:** Orphan QR PNGs accumulate; no dedicated test DB.
- **Fix Plan:** Use a dedicated test database in CI; make QR generation injectable/mockable in tests.
- **Status:** Open (low priority)

### TD-017 — Audit logging not implemented (HIGH)
- **Severity:** High
- **Module:** `app/models/audit_log.py` (model only)
- **Description:** The `audit_logs` table + `AuditLog` model exist, but no critical action
  (login, publish, delete, public view, PDF download) writes an audit record. CLAUDE.md requires
  "Audit must record all critical actions."
- **Risk:** No traceability/forensics; charter requirement unmet. Not a functional/safety break.
- **Fix Plan:** Add an audit service writing `AuditLog` on login/publish/delete/public-view with
  actor, ip, user_agent, entity, action, meta.
- **Status:** ✅ RESOLVED (v1.1) — `audit_service` records 9 action types; admin viewer at /admin/audit.

### TD-018 — Production SECRET_KEY fail-closed
- **Severity:** (was High) — RESOLVED
- **Module:** `app/core/config.py`
- **Description:** A default signing secret would silently work in production, allowing forgeable
  sessions.
- **Risk:** Session forgery / auth bypass on misconfiguration.
- **Fix Plan:** N/A.
- **Status:** ✅ RESOLVED (Release Audit) — `Settings.validate_for_runtime()` raises at startup
  when `ENVIRONMENT=production` and `SECRET_KEY` is default/empty.

### TD-019 — No login rate-limiting / account lockout
- **Severity:** Medium
- **Module:** `app/routers/auth.py`
- **Description:** No throttling on `/login`; brute-force possible.
- **Risk:** Credential brute-force.
- **Fix Plan:** Add rate-limiting/lockout with the public-route limiter (TD-013).
- **Status:** ✅ RESOLVED (v1.1) — in-process sliding-window lockout (5/5min/IP) → 429.
  NOTE: per-process only; use a shared store (Redis) for multi-worker.

### TD-020 — Counterparty BIK not autofilled into a field
- **Severity:** Low
- **Module:** `templates/esf/form.html`, `counterparty_service`
- **Description:** The directory stores `bik`, but the form has no separate BIK input (field 207
  «Наименование банка и код (БИК)» binds to `bank`), so lookup autofill cannot populate a BIK
  field. `bik` is still saved/searched.
- **Risk:** Minor — BIK is conventionally written inside the bank text.
- **Fix Plan:** If a dedicated BIK field is added to the document model, include it in autofill.
- **Status:** Open (low)

## Rule

Every technical debt item must include:

- ID
- Severity
- Module
- Description
- Risk
- Fix Plan
- Status
