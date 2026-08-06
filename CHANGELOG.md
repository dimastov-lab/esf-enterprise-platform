# CHANGELOG.md

## v1.2.2 — Credential security sprint (2026-08-06)

Closes TD-023 and TD-027.

- **TD-023**: `Settings.validate_for_runtime()` raises `RuntimeError` when
  `AIOS_ENABLED=true` and `ENVIRONMENT=production` if `AIOS_BASE_URL` does not start
  with `https://`. Dev mode (`ENVIRONMENT=development`) is exempt. 4 tests.
- **TD-027a**: `MAX_TTL_DAYS = 90` constant in `CredentialService`; `issue()` raises
  `ValueError` when `expires_in_days > MAX_TTL_DAYS`; router converts this to HTTP 422
  with a descriptive message. 2 tests.
- **TD-027b**: `CREDENTIAL_ISSUED` and `CREDENTIAL_REVOKED` audit action constants replace
  the misused `LOGIN`/`LOGOUT` actions in `auth.py` credential routes. Audit metadata
  now includes `credential_id`, `label`, and `expires_in_days` (issue) or `credential_id`
  (revoke). 3 tests.
- **TD-027c**: `AuthService.deactivate_user(user_id)` sets `is_active=False`; raises
  `ValueError` if not found or already inactive. `POST /admin/users/{id}/deactivate`
  (admin-only, CSRF-protected) calls `deactivate_user` then `revoke_all_for_user` and
  emits a `CREDENTIAL_REVOKED` audit row with `deactivated_user_id` + revoked count.
  "Деакт." button added to `admin_users.html` (non-admin active users only). 7 tests.
- Suite: **195 tests pass**.

---

## v1.2.1 — AIOS operability dashboard (2026-08-05)

- `AIOSBridgeService.ping()`: lightweight GET `/api/v1/health` (3 s timeout),
  returns `True` on any sub-500 response, `False` on network error.
- `_NoOpBridge.ping()`: returns `False` (AIOS disabled — no connection).
- `GET /admin/aios` (admin-only): live status page showing AIOS_ENABLED badge,
  base URL, workspace ID, token presence, connectivity result (ping, only when
  enabled), and per-entity integration stats (docs with `aios_task_id` / total,
  snapshots with `aios_memory_id` / total, percent linked).
- `admin_aios.html` template (badge-on/off/ok/warn/na colour scheme).
- `config.VERSION` → `"1.2.0"`.
- 10 tests: RBAC (admin pass / issuer 403 / anon redirect), disabled/enabled
  display, ping success/failure badges, stats section, no-ping-when-disabled,
  `_NoOpBridge.ping()`.
- Suite: **179 tests pass**.

---

## v1.2.0 — AIOS Core convergence: AUTH-01 + Layers 1/2/3 (2026-08-05)

Full integration of the ESF platform with AIOS Core per ADR-0015
("ESF as domain module on AIOS"). No breaking changes when `AIOS_ENABLED=false`
(the default); all new paths are safely no-op in standalone mode.

### AUTH-01 — Long-lived PG-backed API credentials

- New table `api_credentials` (migration `d0e1f2a3b4c5`): `id`, `user_id` (FK),
  `token_hash` (SHA-256, unique), `label`, `expires_at` (NULL = no expiry),
  `revoked_at`, `last_used_at`.
- Token format: `esf_<base64url(32B)>` (secret-scanner-detectable prefix; raw
  token shown once only at issue time).
- `CredentialService`: `issue`, `validate` (touches `last_used_at`), `revoke`,
  `revoke_all_for_user`, `list_for_user`.
- REST endpoints: `POST /auth/credentials`, `GET /auth/credentials`,
  `DELETE /auth/credentials/{id}`.
- `get_current_api_user` in `security.py` accepts `esf_` tokens and routes them
  to the PG path; everything else falls through to the JWT path.
- 23 tests added.

### Layer 1 — AIOS Tasks

- `AIOSBridgeService`: `task_create`, `task_start`, `task_escalate`,
  `task_complete`, `task_cancel` — synchronous httpx calls, fire-and-forget
  (exceptions logged at WARNING, never propagated).
- `_NoOpBridge`: returned when `AIOS_ENABLED=false`; all methods are silent no-ops.
- `ESFDocument.aios_task_id` column (migration `e1f2a3b4c5d6`).
- `ESFService` wired: `create_draft` → `task_create`; `validate` (success) →
  `task_start`; `publish` → `task_escalate` + `task_complete`; `cancel` →
  `task_cancel`.
- Config additions: `AIOS_ENABLED`, `AIOS_BASE_URL`, `AIOS_TOKEN` / `AIOS_TOKEN_FILE`,
  `AIOS_WORKSPACE_ID`.
- 9 tests added.

### Layer 3 — AIOS Memories

- `AIOSBridgeService.memory_create(snapshot_uuid, sha256, payload)`: POST
  `/api/v1/memories`; idempotent via `Idempotency-Key: esf-snapshot-<uuid>`.
- `_NoOpBridge.memory_create()`: silent no-op.
- `ESFSnapshot.aios_memory_id` column (migration `9bb4bef2e079`).
- `ESFService.publish()`: calls `memory_create` **before** `repo.commit()` so
  `aios_memory_id` is part of the INSERT (snapshot is immutable after commit).
- `snapshot_service.make_snapshot()`: UUID now assigned in Python at object
  construction (was DB-side default; needed to be readable before flush).
- 10 tests added.

### Layer 2 — AIOS Identity

- `AIOSBridgeService.identity_verify(user_token)`: GET `/api/v1/identity/me`
  using the *caller's* token (not the ESF service-account token); returns
  identity claims dict on 200, None on error or unreachability.
- `_NoOpBridge.identity_verify()`: returns None.
- `get_current_api_user()`: when `AIOS_ENABLED=true` and token is not `esf_`:
  AIOS Identity tried first; claims returned + local user found → authenticated;
  claims returned + unknown `preferred_username`/`sub` → 401; None returned
  (AIOS down/token not AIOS) → graceful fallback to ESF JWT.
  `esf_`-prefixed PG credentials bypass AIOS entirely.
- 9 tests added.

### Suite

169 tests pass (was 104 at v1.1.6). All new tests are transaction-isolated.

---

## v1.1.6 — housekeeping: version truth-up, TD-004/TD-020 closed (2026-08-01)

Zero behavior change for real users; the debt register reaches zero open items.

- **Version metadata truth-up.** `config.VERSION` had been frozen at `1.0.0-rc1` since
  Sprint 13R while the platform moved to v1.1.x; now `1.1.6` (also the prod image tag and
  the CLAUDE.md status block, which still said "Sprint 12 partial").
- **TD-004 executed.** `/dev/esf-preview` + `app/dev_sample.py` deleted — the form has
  rendered real persisted data since Sprint 5R; the hardcoded-sample preview route was a
  leftover with a standing removal plan. README updated.
- **TD-020 closed as by-design.** The official STI-007 form has no separate BIK box
  (field 207 is one text field, BIK written inside); the counterparty directory still
  stores and searches `bik`.
- **Test-count history reconciled** (gap flagged in PROJECT_STATE on 2026-07-26): the
  undocumented 23→55 growth maps to the July audit-remediation commits; full chain now
  recorded in PROJECT_STATE.

## v1.1.5 — final production-hardening backlog (2026-08-01)

Closes every remaining code-side item in TECHNICAL_DEBT.md; what's left is owner-only
(ACTION_REQUIRED.md) and deliberate out-of-scope. 104 tests pass.

- **Shared-store rate limiting (TD-013/TD-019 remainder).** Production runs uvicorn with
  `--workers 2`, so the in-process limiter windows were per-worker (limits ×N, lockout lost
  on restart). `app/core/ratelimit.py` is now store-backed: `memory` (dev/tests) or
  `postgres` — fixed-window counters in the new `rate_limits` table (migration
  `c7d8e9f0a1b2`, reversible), incremented atomically via `INSERT … ON CONFLICT … RETURNING`,
  shared across workers/replicas. Backend defaults by environment (production → postgres);
  `RATE_LIMIT_BACKEND` overrides. Router call sites unchanged. The login key's `\x00`
  separator is mapped to `\x1f` (Postgres rejects NUL in strings).
- **Styled error pages.** One styled error surface (`observability.error_response`) for
  404/403/409/429/…: browsers (Accept: text/html) get the same dark shell as the 500 page
  with per-status titles and the request id; API clients keep machine-readable JSON;
  headers (e.g. `Retry-After`) pass through. All router-level bare-text 404/429 responses
  migrated; framework-level HTTPExceptions (unknown URL, CSRF 403) go through the same
  handler.
- **TD-015: lifespan.** Dev-admin seed moved from deprecated `@app.on_event("startup")`
  to a FastAPI lifespan handler; `TemplateResponse(request, …)` was already migrated —
  import is now clean under `-W error::DeprecationWarning`.
- **TD-016: test isolation.** `TEST_DATABASE_URL` (when set) replaces the DB for the whole
  suite; QR PNGs written by publish tests go to a throwaway tmp dir via the new
  `QR_STORAGE_DIR` setting instead of the working tree.
- **Docker secrets.** `SECRET_KEY_FILE` / `DATABASE_URL_FILE` are honoured when the plain
  env var is absent (content read from the mounted secret file) — keeps production secrets
  out of container env / `docker inspect` (see DEPLOY.md).
- **Debt-register reconciliation.** TD-001 (quarantined legacy code) was already deleted in
  the 2026-07-28 audit cleanup and TD-009's Docker/Linux part was done (image installs
  pango/cairo; the macOS DYLD hack is dev-only and platform-gated) — both now marked
  resolved.

## Public verification rate limiting — TD-013 (2026-08-01)

Closes the last substantive open TECHNICAL_DEBT hardening item. The open, unauthenticated
routes `/esf/check-esf` and `/qr/{uuid}.png` now share a per-IP sliding-window throttle
(30 requests / 60 s → 429 with `Retry-After`), enforced BEFORE any DB work so it caps both
UUID enumeration probing (404s consume the same budget) and the audit-row write done on every
allowed public view. Implementation extends `app/core/ratelimit.py` with a second, independent
bucket alongside the login lockout (same honest per-process caveat: multi-worker production
needs a shared store — that remains the known post-MVP item). TDD: two new regression tests
(burst → 429 + Retry-After + shared QR bucket; 404-probe throttling); 85 tests pass.

## CSP: script nonce instead of 'unsafe-inline' (audit I-4) (2026-07-29)

Removes `'unsafe-inline'` from the Content-Security-Policy `script-src`, closing the
XSS-mitigation gap the audit flagged. 83 tests pass (a new regression test asserts the
nonce policy), and every interactive path was verified in the browser with zero CSP
console violations.

- **Per-request nonce.** `app/main.py` generates a fresh nonce into
  `request.state.csp_nonce` before each response and emits
  `script-src 'self' 'nonce-…'`. Every inline `<script>` in login/dashboard/form.html
  is stamped with `nonce="{{ request.state.csp_nonce … }}"`, so the browser runs our
  scripts but blocks any injected inline script.
- **Inline handlers → addEventListener.** A nonce does not cover inline event
  handlers, so all 8 were converted: the dashboard filter auto-submit (3× `onchange`
  → `data-autosubmit` + listener), the editor's add-row / delete-row (static **and**
  the JS-generated row) via delegation, the print button, and the delete-document
  confirm (`onsubmit` → submit listener).
- **nginx.** Dropped its static `Content-Security-Policy` header — the application is
  now the single CSP authority (nginx cannot reproduce the per-request nonce, and a
  static policy would either weaken it or collide with the nonce). Other security
  headers stay.
- **Scope.** `style-src 'unsafe-inline'` is intentionally kept (inline style
  attributes are pervasive in the STI-007 templates; out of scope for this change).

## Supply-chain hardening — hash-pinned dependencies (audit I-6) (2026-07-29)

- **`backend/requirements.lock`** — the full transitive closure of `requirements.txt`
  with SHA256 hashes for every artifact (44 packages), generated with
  `pip-compile --generate-hashes` under Python 3.11 (matching the Dockerfile runtime).
- **Dockerfile** now installs with `pip install --require-hashes -r requirements.lock`,
  so the image build **fails closed** if any downloaded artifact's hash does not match
  its pin — a substituted/compromised package on PyPI can no longer enter the image.
- `requirements.txt` stays the source of truth (still what `pip-audit` scans in CI);
  added a note documenting how to regenerate the lock after changing a pin.
- Verified: `--require-hashes` install succeeds in a clean `python:3.11` container, the
  full production image builds, and the app imports inside it with the locked deps.

## Audit remediation — decompose ESFService, PDF out of the router, drop dead code (2026-07-29)

Closes three architecture findings from `AUDIT_2026-07-28.md` (§7: A-1, A-4, A-5).
Behaviour-preserving refactor; **82 tests pass**, coverage 91%, `ruff` clean. The
routers' single entry point (`ESFService`) keeps its full public API, so no router
or test call site changed.

- **A-1 (god-object):** `ESFService` (755 lines, mixing CRUD + lifecycle + queries +
  serialization) is decomposed into focused, independently testable services:
  - `esf_serializer.py` — `ESFSerializer`: pure, DB-free mapping of the ORM graph to
    the template-ready dict (form / PDF / snapshot) and the compact dashboard row.
  - `esf_query_service.py` — `ESFQueryService`: the read side (lookup + owner/admin
    access, pagination/search/sort/filter, dashboard aggregates, snapshot-backed
    `serialize_published`).
  - `esf_service.py` — now the lifecycle/command service + coordinator (574 lines);
    the read/serialize methods are thin pass-throughs to the two services above.
- **A-4 (logic in controller):** the ESF PDF/ZIP rendering (Jinja template render +
  WeasyPrint) moved out of `routers/esf.py` into `pdf_service` (`render_esf_pdf`,
  `render_esf_zip`). The router now only serializes in the request context and
  offloads the blocking render to the threadpool — a thin controller.
- **A-5 (dead duplicate):** removed the unused `snapshot_service.latest_snapshot`
  (a raw-query copy of `ESFDocumentRepository.latest_snapshot`) and its now-unused
  imports. The bonus dead helper `_num` was dropped in the same pass.

## Audit remediation — layer boundary, error visibility, owner_id NOT NULL (2026-07-29)

Closes three code-quality findings from `AUDIT_2026-07-28.md` (§7: A-2, A-6, A-7).
No end-user behaviour change; **82 tests pass**, and `alembic upgrade`/`downgrade`
round-trips clean.

- **A-2 (layer leak):** `ESFService` no longer touches the SQLAlchemy `Session`
  directly. The 11 direct `self.db.flush/refresh/add/rollback` calls now go through
  new `ESFDocumentRepository` methods (`flush`, `refresh`, `rollback`, `add_pending`),
  keeping all DB access inside the repository layer (charter rule). `add_pending`
  stages the immutable snapshot inside the atomic publish without an early commit.
- **A-6 (silent excepts):** `batch_publish` now logs a failed document (uuid +
  traceback via `_log.exception`) and rolls back so the next item starts on a clean
  session, instead of a bare `failed += 1`. `audit_service.record` logs *why* an audit
  write failed (append-only trigger, DB down, …) before swallowing it — the write stays
  best-effort (never breaks the user action), but the compliance blind spot is closed.
- **A-7 (nullable owner scope):** `counterparties.owner_id` and `goods.owner_id` are now
  `NOT NULL` (models + reversible migration `b1c2d3e4f5a6`). Legacy pre-scoping rows
  (owner_id NULL — invisible to every per-owner query, a scope-bypass vector) are purged
  in the migration; the per-owner directories repopulate on the next save.

## Project closure — handover + production deployment guide (2026-06-28)

Documentation and repository-hygiene pass for handover to a new engineering team.
**No application logic changed** — verified: no code/config references the removed
directories, and the shipped dependency stack is unchanged (still 55 tests green,
zero runtime CVEs).

- **`PROJECT_HANDOVER.md`** — single onboarding entry point: purpose, architecture +
  the four invariants, folder map, stack, deploy/ops/backup/restore, CI, testing,
  known limitations, roadmap, tech debt, what to read first, onboarding time.
- **`DEPLOY_UBUNTU.md`** — complete step-by-step Ubuntu VPS deployment guide (server
  prep, DNS, Docker install, `.env.production`, Let's Encrypt HTTPS + renewal, first
  admin, smoke test, backup/restore, day-2 ops, troubleshooting, production checklist),
  grounded in the real `docker-compose.prod.yml` / `infra/nginx/nginx.conf` / scripts.
- **Repo hygiene:** removed empty leftover top-level dirs (`tests/`, `frontend/`,
  `docker/`) that duplicated `backend/tests` and misled navigation; expanded
  `.gitignore` (ruff/pytest caches, coverage, editor dirs); removed committed caches.
- **README accuracy:** corrected the test count (`23`→`55 passed, 90% coverage`), the
  stale "hardening backlog" note (CSRF/audit are implemented), and added a handover
  pointer. Python-version note aligned to 3.11.

## Enterprise hardening — security, observability, CI (2026-06-28)

See `ENTERPRISE_FINAL_CERTIFICATION.md`. Tests **55 passed** on the upgraded stack;
`pip-audit -r requirements.txt` reports **zero known vulnerabilities** (Python 3.11).
All changes verified in a clean-room `python:3.11` container against PostgreSQL.

- **Dependency security sweep → zero runtime CVEs.** Reduced from ~20 vulnerable
  packages to none: `fastapi` 0.111→0.138.1 with `starlette` **explicitly pinned to
  1.3.1** (fastapi's range is broad, so an unpinned starlette resolves
  non-deterministically) clearing every starlette advisory, `python-multipart`
  0.0.9→0.0.31 (multipart DoS), `pillow` 10.3→12.2, `jinja2` 3.1.4→3.1.6,
  `weasyprint` 66→69 (69 clears the later GHSA-jhhc-3hcp-qhm5), `uvicorn` 0.30→0.34.
  Verified: `pip-audit -r requirements.txt` → **no known vulnerabilities**; 55 green.
- **starlette 1.x migration**, required by the upgrade: all 11 `TemplateResponse`
  calls moved to the `TemplateResponse(request, name, context)` signature. No change
  to business logic — the full regression suite (CSRF, sessions, publication,
  snapshots, PDF, batch ops, pagination) stays green.
- **Standardised on Python 3.11** (already the Docker runtime; the security-patched
  deps require ≥3.10). README and ruff `target-version` updated to match.
- **Structured observability** (`app/core/observability.py`): JSON access logs, a
  per-request `X-Request-ID`, and a clean JSON 500 handler. Wired in `main.py`.
- **Hardened production surface**: interactive `/docs`, `/redoc`, `/openapi.json`
  are disabled when `ENVIRONMENT=production`.
- **DB resilience knobs**: `statement_timeout`, `pool_size`, `max_overflow` now
  configurable (`DB_STATEMENT_TIMEOUT_MS` / `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`).
- **CI + tooling**: GitHub Actions (`.github/workflows/ci.yml`) runs ruff → migrate
  → `pytest --cov` → `pip-audit` on a Postgres service (Python 3.11, matching prod);
  `ruff`/coverage/pytest config in `backend/pyproject.toml`; `.pre-commit-config.yaml`.
- **Fixed a latent CI bug**: the test login helper extracted the CSRF token from a
  dashboard form that only renders when documents exist, so it failed on an empty
  database. It now falls back to the always-present token — CI works on a fresh DB.
- **Reproducibility**: pinned the previously-implicit test deps (`pypdf`, `httpx`)
  and added `pytest-cov`/`ruff`/`pip-audit` in `requirements-dev.txt`.

## Iteration 02 — pg_trgm search indexes (scalability insurance) (2026-06-28)

See `COMPLIANCE_ITERATION_02.md`. Tests **55 passed**. Migration `a7d4e91c25f8`.

- Added **pg_trgm GIN indexes** on `esf_parties.name/inn`, `esf_documents.esf_number`,
  `esf_supply_info.note` so dashboard substring search (`ILIKE '%…%'`) uses an index
  instead of a sequential scan at scale.
- Measured (50k): the party-name lookup plan goes **Seq Scan (cost 1853) → Bitmap
  Index Scan (cost 55), ~33×** — but **wall-clock is unchanged at 50k** (search isn't
  the bottleneck there). Honest verdict: **preventive infrastructure** that removes
  the O(n) search cliff at 100k–1M, not a felt win today. Zero downside, additive,
  backward-compatible.
- pg_trgm is a trusted extension on PG13+ (no superuser needed in prod). Benchmark
  data cleaned up; functional search unchanged.

## Parity iteration 01 — silent save + field compliance (2026-06-28)

See `COMPLIANCE_ITERATION_01.md`. Tests **55 passed**.

- **Ctrl+S / «Сохранить» now save in the background** (via the autosave endpoint)
  instead of submitting the form — no page reload, scroll & focus preserved.
  Verified in a real browser (`POST …/autosave`, no navigation). Pure client JS;
  publication/snapshot semantics unchanged. (Retrospective #6 fixed.)
- **Field-compliance audit:** new `test_all_sti007_fields_round_trip` proves all
  35 STI-007 fields survive save → immutable snapshot → public page → PDF — no
  dropped fields.
- Honest note: live diffing against esf.salyk.kg is not possible from here, so no
  «PARITY ACHIEVED» certification is claimed; provenance markers are not forged.

## v6.0 #3 — Batch operations (2026-06-28)

End-of-day workflow: multi-select on the dashboard → act on many documents at once.
Additive; reuses the existing (atomic) per-document service methods, no engine
changes. Tests **54 passed**.

- **Selection:** a checkbox per row + a select-all header checkbox (with
  indeterminate state); a batch bar appears when ≥1 row is selected.
- **Опубликовать** (`POST /esf/batch/publish`): publishes each editable doc
  atomically; invalid ones stay DRAFT and are counted as failed.
- **Скачать PDF (ZIP)** (`POST /esf/batch/pdf`): renders the selected documents
  and returns them as one `application/zip` download (cap 100/request).
- **Удалить** (`POST /esf/batch/delete`): deletes selected drafts, skips
  published/cancelled and foreign docs. Confirm dialogs on publish/delete.
- Service: `batch_publish` / `batch_delete` / `get_if_owner` (silently skip
  foreign/missing docs); routes CSRF-protected. Tests: `test_batch_publish_and_delete`,
  `test_batch_pdf_returns_zip`, `test_dashboard_has_batch_controls`.
- Screenshot: `docs/screenshots/dashboard_batch.png`.

## v6.1 — Enterprise scalability: server-side dashboard (2026-06-28)

Replaced client-side full-list loading with server-side pagination/search/sort/
filter. Engines, document rendering, public URL, PDF — unchanged. Tests **51 passed**.
See `SCALABILITY_REPORT.md`.

- **Repository:** `paginate_for_user()` (COUNT + LIMIT/OFFSET + one selectinload —
  no `.all()`, no N+1); aggregate `status_counts()` / `created_counts_since()`
  (one GROUP BY each). `dashboard_stats` no longer iterates all rows.
- **Service:** `page()` → `{rows, page, page_size, total, total_pages}`.
- **API:** `GET /api/esf?page&page_size&q&status&currency&supplier&buyer&date_from&date_to&sort&dir`
  → `{items, page, page_size, total, total_pages}`.
- **Search** (server-side): ESF number, supplier/buyer name & INN, note, currency.
  **Sort:** number/date/status/updated/supplier/buyer, asc/desc. **Filters:** status,
  date range, currency, supplier, buyer. `page_size` clamped 1–200 (default 25).
- **Dashboard UI:** GET filter form, sortable header links, real pagination controls;
  stat cards are now server-side filter links.
- **Measured (N=10,000):** page load **438 ms → 18 ms (~24×)**, constant ~4 queries
  and 25 rows in memory (was 22 queries / 10,000 rows); `dashboard_stats` 9 ms.
- Tests: `test_api_esf_pagination_search_sort_filter`,
  `test_dashboard_renders_server_side_pagination`. Screenshot:
  `docs/screenshots/dashboard_serverside.png`.

## v6.0 #1 — Corrections & cancellation (2026-06-28)

The biggest real-world blocker from the accountant retrospective. Additive (one
Alembic migration `f6a1c2d3e4b7`); snapshot immutability preserved. Tests **49 passed**.

- **Annul a published ESF** — `POST /esf/{uuid}/cancel`: status PUBLISHED → CANCELLED
  with `cancelled_at`. The immutable snapshot is **kept** (history intact); the
  document view shows «✗ Аннулирован». Confirm dialog (irreversible). A cancelled
  doc isn't publicly verifiable.
- **Issue a correction** — `POST /esf/{uuid}/correct`: creates a new editable DRAFT
  copied from the published original, **linked via `corrects_id`**, with field 406
  («Корректировка к счёту-фактуре» № + date) prefilled to the original number/date.
  The original is never modified. Field 406 is now editable; `correction_number` /
  `correction_date` persist and serialize.
- Buttons «✎ Корректировка» and «✗ Аннулировать» on the published-document toolbar
  (owner only); migration adds `esf_documents.cancelled_at/corrects_id` and
  `esf_supply_info.correction_number/correction_date`.
- Tests: `test_cancel_published_keeps_snapshot`, `test_correction_creates_linked_draft`.

## v5.1 — Final enterprise polish (2026-06-27)

Speed/Comfort/Confidence micro-wins only; no architecture/backend change. Tests
**47 passed**. See `FINAL_PRODUCT_AUDIT.md` for scores, the Top-100 list, debt and
the v6.0 roadmap.

- **Whole dashboard row opens the document** — click anywhere on a row (except the
  action buttons) instead of aiming at the small "Открыть" link.
- **"⧉ Дублировать" on the published view** — issue the next near-identical invoice
  in one click right after publishing (repeat invoices dominate daily volume).
- Both additive and owner-only; the public page carries neither.

## Compliance: published form matched to the official GNS STI-007 (2026-06-27)

Audit of our published form against the real salyk.kg ESF (text extracted from
`Копия 6.pdf`). Structure/labels/codes already matched; three value-formatting
differences found and fixed. See `COMPLIANCE_FORM_AUDIT.md`. Tests **45 passed**.

- **Price** and **Quantity** now print with **5 decimal places** (e.g. `116.49850`,
  `21000.00000`) regardless of input, like the GNS form (`_qty5()`).
- Footer **timestamp** uses dotted time `13.46.33` (was `13:46:33`).
- Open item flagged for confirmation: decimals in the НДС/НсП «Ставка» columns.
- New test `test_published_form_matches_gns_formatting`. Already-published
  snapshots keep their stored formatting (immutable); changes apply to new
  publications.

## Edit page = one screen, no scrolling (2026-06-27)

The editing page now shows the **whole STI-007 fit inside the canvas (width AND
height), centred, with no scrolling in any direction** — you see the entire form
at once and never scroll up/down/left/right. It keeps the document's real, tested
layout (no overlapping fields); only the zoom adapts: it scales down to fit on
small/short windows and up (to 1.8×) on large ones, recomputing on resize, panel
toggle and row add/remove. `.ws-canvas` is `overflow: hidden` + flex-centred.
(Supersedes the earlier "comfortable" attempt, which enlarged fonts and made the
form overflow/scroll and overlap.) Scoped to `.mode-edit` — **view / public / PDF
keep the exact STI-007**. Tests **44 passed**.

## Accountant pain #2 — Duplicate ESF (2026-06-27)

Additive only; publication/snapshot/validation/security unchanged. Tests **44 passed**.

- **«Дублировать»** creates a new editable DRAFT copied from any document
  (parties, supply info, goods, signatory) — a fresh invoice with no number,
  no status/snapshot, blank issue date and correction refs. The source is never
  modified. Opens the copy in the editor.
- New route `POST /esf/{uuid}/duplicate` (CSRF-protected) + `ESFService.duplicate()`.
- Buttons: «Дублировать» in each dashboard row and in the editor's More (⋯) menu.
- New test `test_duplicate_creates_editable_copy` (duplicates a published doc →
  fresh draft, source stays published).

## Accountant pains #1 & #3 (2026-06-27)

From `ACCOUNTANT_RETROSPECTIVE.md`. Additive only — publication, snapshot,
validation, security unchanged. Tests **43 passed** (added one).

- **Supplier carries over to a new draft** (#1): `создать ЭСФ` now prefills the
  supplier from the user's most recent document (the supplier is almost always
  the same organisation); the buyer stays blank. Removes re-entering ~16 fields
  on every new invoice. *(`last_supplier_for()` + `create_draft()` prefill.)*
- **VAT computed from the rate** (#3): typing a rate in «Ставка» now auto-fills
  the VAT amount (`amount × rate / 100`) live, and it flows into the document
  totals. It only fills empty cells, never overwrites a value you typed (or one
  saved earlier), and clearing the cell resumes auto. Backend still stores the
  submitted amount, so snapshots stay exact.
- Verified in a real browser: VAT auto=120.00, totals updated, manual override
  respected, clear→auto resumed; new test `test_new_draft_carries_over_supplier`.

## Micro-nit polish pass — ~50 tiny annoyances (2026-06-27)

Small UX/CSS fixes only, no features or logic changes. Tests **42 passed**.

Dashboard: status pill colour per state (draft/validated/published/cancelled);
hover on action buttons, top-bar links, "+ Новый ЭСФ", reset; removed search
auto-focus (restored the `n` = new-doc shortcut); steadier count width; brighter
sort arrow + header hover; search aria-label + "( / )" hint.
Editor: Ctrl+P now prints (matched the Print button); ⌘→Ctrl shortcut hints on
non-Mac; Esc exits focus mode; visible "○" marker for incomplete wizard steps;
correct initial active step; INN caret no longer jumps mid-edit; Esc clears the
field search; titles on Проверить/Сформировать; aria-labels on icon buttons;
aria-live on save status; aligned delete-confirm wording.
Viewer: "+ Новый" → "+ Новый ЭСФ"; rel=noopener + titles on PDF/QR/link; zoom
±/% aria-labels + live region.
CSS: faster field flash (1.6s→0.9s); clean edit-mode printing (no blue input
boxes / grey hints); no layout shift on "✓ Скопировано"; keyboard focus rings;
wider date field (no clipping); tab labels don't wrap; smoother button hover;
document `<title>` fallback for unsaved drafts; better QR alt text.

## Final editor redesign — document-first workspace (2026-06-27)

Edit-mode chrome only; the STI-007 document, backend, publication, snapshot,
validation, security, database and routing are unchanged. Tests **42 passed**.

- **Slim toolbar (40px, white, almost invisible):** permanently visible only
  Save-status · Validate · Publish · Print · PDF · Search · Fullscreen; everything
  else (Save, +строка, Undo/Redo, Copy link, Результат, К списку) moved into a
  **More (⋯)** menu — roughly a 40% reduction in visible controls.
- **Left panel is now a numbered wizard** (① Документ … ⑧ Проверка) with per-step
  state — done (green ✓), warning (amber !), incomplete — and the current section
  highlighted.
- **Right panel slimmed:** only Validation, Recent Counterparties, Recent Goods
  stay; History / AI / Attachments / Danger collapse into **tabs** (one active at
  a time).
- **Lighter, Office-like palette:** almost-white canvas, subtle borders, status
  bar fades into the background; reduced padding so the document dominates.
- **Print** button (hides all workspace chrome → clean A4) and **F11 focus mode**
  (hides both side panels).
- Verified in a real browser: wizard states (done/warn/todo), tab switching, More
  menu, F11 focus all PASS. Screenshot: `docs/screenshots/editor_redesign.png`.

## v5.0 Module 6 — Excel-grade goods grid (2026-06-27)

Edit-mode only, pure client-side: it fills the SAME inputs the form already
submits, so backend validation, publication and snapshots are untouched.
Tests **42 passed** (added one).

- **Paste ranges from Excel** (Ctrl/Cmd+V): TSV is parsed into cells starting at
  the active cell; rows are auto-created as needed; live totals recompute.
- **Copy** selected cells (Ctrl/Cmd+C) as TSV.
- **Fill down** (Ctrl/Cmd+D): top of selection → rows below (or cell-above → cell).
- **Arrow-key navigation** between cells (Up/Down always; Left/Right at the text
  boundary), **Shift+Arrows** for multi-cell selection (highlighted).
- **Enter** moves down within the column (Excel-style) and creates a new row at
  the bottom; **Tab** still creates the next row at the end.
- Verified in a real headless browser: paste→rows+calc, fill-down, Enter-row,
  arrow-nav all PASS. New test `test_excel_grid_wired_in_edit_only` asserts the
  grid is present in edit mode and absent from the public viewer.
- Screenshot: `docs/screenshots/v5_excel_grid.png`.

## Enterprise Pack v4.0 — Validation Center + local AI (2026-06-27)

See `ENTERPRISE_FINAL_REPORT.md`. Additive, edit-mode only; no change to
Publication/Snapshot/Validation/Security engines. Tests **41 passed**.

- **Module 9 — Validation Center:** server validation errors (top banner + right
  panel) are now clickable → scroll to the offending field and flash it (amber).
  Maps the official field code in each message (`поле 201` → supplier INN, …) with
  keyword fallbacks. Pure client-side; the Validation Engine is unchanged.
- **Module 19 — Local AI assistant:** right-panel "Помощник (ИИ)" runs heuristic
  checks (same supplier/buyer INN, INN length ≠ 14, currency without rate,
  price/qty ≤ 0, VAT-rate-without-amount, duplicate rows) and **warns before
  publish**. No external calls; never edits data.
- Report documents which of the 22 v4.0 modules are done / partial / roadmapped
  (honest status table) + a v5.0 roadmap.
- Screenshot: `docs/screenshots/v4_workspace_ai.png`.

## Final visual parity — light ESF viewer (2026-06-27)

See `FINAL_VISUAL_REPORT.md`. Viewer only; document/edit/PDF/snapshot/QR
unchanged. Tests **41 passed**.

- Public + owner-view now share ONE **light** document viewer (was: dark for
  view, plain paper for public): minimal compact white toolbar over a near-white
  canvas, document centered as a paper sheet with a **soft shadow** and **large
  margins**.
- **Zoom:** Fit Page default (capped at 100% so it shows the natural-size sheet
  with big margins, not maximized) · Fit Width · 100% · 125% · 150% · ± /
  Ctrl-Cmd; remembered across visits; active preset highlighted.
- **Public toolbar is minimal** (title + zoom only) — no owner/edit actions;
  test updated (`test_public_page_is_light_viewer_no_internal_chrome`).
- Screenshots: `docs/screenshots/final_public_after.png`, `final_public_wide.png`,
  `final_viewer_toolbar.png`.
- Limitation: no network access to esf.salyk.kg here, so a live pixel overlay
  was not run — matched against the provided screenshot + spec.

## ESF number format aligned to salyk.kg (2026-06-27)

- `next_esf_number()` now generates the official format `000{YYYY}-004-{8 digits}`
  (e.g. `0002026-004-00000010`) instead of `{YYYY}-004-{8 digits}`. Matches the
  reference document and the dev sample. Display, snapshot, and QR are unaffected
  (they read `esf_number` as-is).
- New assertion in `test_publish_creates_snapshot_and_number`:
  `re.fullmatch(r"000\d{4}-004-\d{8}", esf_number)`. Tests **41 passed**.

## Public page — paper-sheet preview like the official viewer (2026-06-27)

Public/check page only (`GET /esf/check-esf`). Tests **41 passed** (added one).
No change to edit/dashboard/PDF/snapshot/publish/QR.

- The public document now renders as a **smaller centered paper sheet** on a
  light canvas (`#eef0f2`) with a **subtle shadow** and **large margins** — it no
  longer fills the viewport or feels like an editor. Uniform `scale` (~0.82 on
  roomy screens, shrinks to fit on small ones, never upscaled) preserves STI-007
  A4 proportions.
- No dark toolbar / zoom / workspace chrome on the public page (read-only).
- QR stays embedded bottom-left inside the document; footer/signature unchanged.
- New test `test_public_page_is_plain_paper_no_internal_chrome` asserts the paper
  sheet is present and no internal chrome (viewer-bar/zoom/workspace/edit inputs)
  leaks onto the public page.
- Screenshots: `docs/screenshots/public_view_before.png` (natural size),
  `public_view_after.png` (wide), `public_view_after_laptop.png`.

## Public page matched to the official salyk.kg viewer (2026-06-27)

Tests stay **40 passed**. PDF unchanged (24 KB, valid).

- **Public verification page is now plain like the official esf.salyk.kg page:**
  white background, the document centered at natural size with white margins,
  **no dark toolbar, no gray stage, no zoom chrome**. The viewer (toolbar + zoom)
  now applies to the owner `view` mode only.
- **Footer corrected to the official STI-007 layout** (document-level, so it is
  identical in edit/view/public/pdf): QR cell · 450 + signatory label ·
  director-name cell (own vertical divider, no signature underline) · **vertical
  date/time stamp** on the far-right edge — matching the reference.
- Screenshot: `docs/screenshots/public_like_original.png`.

> Note: the document NUMBER still uses the internal format `YYYY-004-NNNNNNNN`
> (e.g. `2026-004-00000010`); the official sample shows `0002026-004-00962265`.
> That is number-generation data, not page layout — left unchanged unless you want
> the format aligned too.

## ESF Viewer — zoom controls + official footer (2026-06-27)

Tests stay **40 passed**. View/public only; PDF and the document layout unchanged.

- **Zoom engine:** Fit Page (default on first open), Fit Width, 100%, Zoom In/Out
  (also Ctrl/Cmd +/−/0). Controls live in the toolbar; current % shown; active
  fit-mode highlighted. **Last zoom is remembered** (localStorage). Page stays
  centered on both axes and scrolls smoothly; uniform `scale` only — A4
  proportions never distorted; min white margin around the page.
- **Document-first chrome:** the top toolbar is now thinner (40 px) and more
  subtle so the white document is the visual hero.
- **Official STI-007 footer:** two document cells — QR in the bottom-left cell
  (in normal grid flow, never absolutely positioned, fixed 88×88, not stretched)
  and the 450 signatory block beside it, with the signed name on a signature line
  and the date/time stamp beneath it. Identical in edit/view/public/pdf; draft
  shows the placeholder frame, published/public/pdf show the generated QR.
- Screenshots: `docs/screenshots/viewer_fitpage_desktop.png`,
  `viewer_fitpage_ultrawide.png`, `viewer_zoom_toolbar.png`.

## Official ESF Viewer — view / public / PDF (2026-06-27)

The Published/View and Public pages now behave like a dedicated document viewer
instead of a web page. Same document layout in view / public / PDF — only the
toolbar differs. Tests stay **40 passed**.

- **Thin fixed toolbar** outside the document (dark, full-width). View (owner):
  Назад · Печать · Сохранить PDF · QR · Публичная страница · Копировать ссылку ·
  + Новый ЭСФ. Public (anonymous): Печать · QR · Копировать ссылку. No sidebars,
  no dashboard chrome.
- **Neutral gray stage** (Acrobat-like) fills the viewport; the document is
  centered and **scrolls independently** while the toolbar stays fixed.
- **Fit-to-width zoom** (uniform `scale`, capped 0.45–1.7×) makes the page occupy
  the available width on laptop / desktop / ultra-wide **without stretching** —
  STI-007 A4 proportions are unchanged.
- **PDF unaffected:** viewer wrappers/CSS are gated to view+public only; print
  un-viewers the page to a clean A4.
- Screenshots: `docs/screenshots/viewer_public_ultrawide.png`,
  `viewer_public_laptop.png`, `viewer_owner.png`.

## Enterprise UX Audit v3.1 (2026-06-27)

See `ENTERPRISE_UX_REPORT.md`. No new features, no backend rewrite; tests stay
**40 passed**.

- **Form flow (Module 36):** Enter now moves to the next field (and creates the
  next item row at the end) instead of submitting — no accidental saves; first
  empty required field is auto-focused on load.
- **Smart publication (Phase 9):** publishing opens the final official document
  directly (no intermediate result page).
- **Review mode (Phase 9):** clean dark toolbar outside the read-only document —
  Печать · Сохранить PDF · QR · Публичная страница · Копировать ссылку ·
  + Новый ЭСФ · К списку; print now hides all chrome for a clean A4.
- **Dashboard (Phase 8):** search auto-focuses on load (find a document in < 3 s).
- Screenshot: `docs/screenshots/review_mode.png`.

## Enterprise Productivity Suite v2.5 — Modules 33–35 (2026-06-27)

See `ENTERPRISE_PRODUCTIVITY_REPORT.md` for the full report. Additive, no
architecture change, no STI-007 duplication; Snapshot/Publication/Validation/
Security untouched. Tests 26 → **40 passed**.

### Module 33 — Editor productivity core (edit mode only, client-side)
- Live calculations (per-row amount/total + sheet/invoice/currency totals as you type).
- Smart item table: duplicate, copy/paste, insert above/below, delete, Tab→new row,
  auto-numbering, right-click context menu, multi-select + mass duplicate/delete,
  drag-and-drop reorder.
- Keyboard: Ctrl/Cmd+S / Enter / P / K / Z / Y, Tab, Esc.
- Command palette (Ctrl/Cmd+K) with commands + recent documents.
- Smart formatting (INN/account digit-only, date dd.mm.yyyy, currency `,`→`.`).
- Auto-recovery of unsaved drafts via localStorage.

### Module 34 — Smart goods catalog + favorites/usage
- New `goods` table; `use_count` + `is_favorite` on `goods` and `counterparties`
  (migration `e4b7c1a9f210`).
- Item-name autocomplete fills code/unit/price/VAT; ranked favorites→most-used→recent.
- Right-panel "Recent goods" (one click adds a filled row).
- New auth-only endpoints `GET /api/goods/search`, `GET /api/goods/recent`.
- Catalog upsert on save; counterparty ranking now honors favorites + usage.

### Module 35 — Smart dashboard analytics
- Stat cards (total/drafts/validated/published/today), click-to-filter by status.
- Inline 7-day activity chart (`ESFService.dashboard_stats`).
- Dashboard keyboard shortcuts (n = new, / = search, Esc = clear).

## Module 32 — Fullscreen editor workspace (2026-06-27)

### Added (EDIT MODE ONLY)
- A distraction-free, full-window editor: sticky top toolbar + bottom status bar
  always visible, the STI-007 document scrolls independently in a centered canvas.
- New `esf_workspace.css`, linked only in edit mode and fully scoped under
  `.mode-edit` / `.ws*` — view, public and PDF output are byte-identical.
- Top toolbar: Save · autosave indicator · Undo/Redo (Ctrl+Z / Ctrl+Y) · + строка ·
  field search · Проверить · Сформировать · PDF · copy public link · Fullscreen · panel toggles.
- Left navigation panel (collapsible): Документ / Поставщик / Покупатель / Реализация /
  Товары / Итоги / Подпись / Проверка / История — click to jump; the active section is
  tracked via IntersectionObserver and shown in the status bar.
- Right productivity panel (collapsible): live validation, quick actions, recent
  counterparties (click → fill Поставщик/Покупатель), recent-goods + AI-assistant
  placeholders, history links, delete.
- Bottom status bar: autosave state, validation state, current section, document status,
  number, current user.
- Fullscreen mode (native Fullscreen API; Esc exits) hides both side panels, leaving only
  document + toolbar + status bar.
- Backend: `GET /api/counterparties/recent` (auth-only) + repo/service `recent()`.
- The STI-007 document is never restyled: it keeps its fixed A4 width and centers in the
  canvas; on smaller screens the canvas scrolls horizontally instead of stretching it.
- Responsive: laptop / desktop / ultra-wide; panels auto-collapse under 880px.
- Tests: 30 pass (added recent-endpoint auth + data, edit-chrome present, chrome absent in
  view/public). Evidence: `docs/screenshots/editor_workspace_wide.png`, `…_laptop.png`.

## Module 31 — Full-width dashboard (2026-06-27)

### Changed (dashboard.html only)
- Replaced the narrow centered layout with a full-width back-office workspace: compact sticky
  top bar (brand · user · admin links · logout · + Новый ЭСФ) and full-bleed content (24/40px
  side padding, no max-width cap).
- One professional toolbar row: search + status + date-from/date-to + reset + live count.
- Documents table uses the full width inside a horizontal-scroll container
  (`.table-wrap` overflow-x auto, `min-width:1040px`) so wide tables scroll on small screens;
  sticky table header under the top bar; large-screen padding at ≥1800px.
- Self-contained in `dashboard.html` (inline styles). Login, editor, public page, PDF, and the
  STI-007 document width are unchanged. 26 tests still pass.
- Evidence: `docs/screenshots/dashboard_fullwidth.png`, `dashboard_narrow.png`.

## Sprint UX-2 — Counterparty lookup (2026-06-27)

### Added (edit mode + backend; document output unchanged)
- `Counterparty` model + table (`counterparties`): inn (unique), name, branch, address,
  tax_office, bank, bik, account, last_used_at, created_at, updated_at. Migration `d2389f930148`.
- `CounterpartyRepository` (search + upsert-by-INN) and `CounterpartyService`.
- `GET /api/counterparties/search?q=` — **authenticated only**, returns ≤10 results ordered by
  exact-INN match → most recent `last_used_at` → name. No public access.
- Editor lookup on supplier/buyer INN & name: 300 ms debounce, floating dropdown above the form,
  mouse + keyboard (↑/↓, Enter selects, Esc closes); selection autofills inn/name/branch/address/
  tax_office/bank/account. "Контрагент не найден — заполните вручную" when empty; manual entry
  always works.
- On ESF save, supplier and buyer are upserted into the directory (keyed by INN, refreshes
  `last_used_at`), so the next document reuses them.
- 3 new tests (auth required, upsert+search by INN/name with exact-first ordering, empty query).
  Suite now **26 passed**.

### Unchanged (verified)
- PDF, public page, view mode (byte-identical), publication/snapshot logic, STI-007 appearance.
  The lookup JS/dropdown exist only in edit mode; public output has no lookup markup.

### Note
- `bik` is stored in the directory but the form has no separate BIK input (БИК is part of the
  bank field 207), so it is not autofilled into a field — see TECHNICAL_DEBT.md.

## Sprint UX-1 — Edit-mode usability (2026-06-27)

### Changed (EDIT MODE ONLY — view / public / PDF byte-identical)
- Editable fields are now clearly distinguished in the editor: light-blue input background,
  thin blue border, 3px radius, hover state, focus ring, blinking caret, and placeholders
  (INN, names, dates, accounts, currency, item table, signatory).
- Empty **required** fields show an amber background/border (via `.cinp.req:placeholder-shown`)
  so missing data is obvious; optional fields stay neutral blue.
- Goods-table cells with inputs get a subtle fill so the grid reads as fillable.
- Added a subtle **«✎ Режим редактирования»** badge in the action bar (outside the document).
- All styling is scoped under `.mode-edit` and inputs render only in edit mode, so VIEW, PUBLIC,
  and PDF output are unchanged (verified: view render byte-identical to the reference; public
  has no inputs/badge; PDF 200). 23 tests still pass.

## 1.1.3 — Full visual match (status / number / date / QR) (2026-06-27)

### Changed
- QR + verification URL now use the official Kyrgyz portal format
  `https://esf.salyk.kg/esf/check-esf?documentUUID=...` (decoded from the reference QR), via
  `PUBLIC_BASE_URL` default. The preview clone embeds a QR encoding the exact reference URL, so it
  is pixel-identical to the original; live published docs use the same format with their own UUID.
- Field 101 «СТАТУС» shows the ESF fiscal status: **«первоначальный (Принят)»** for published
  documents (matches the official form) — TD-012 resolved. Internal lifecycle stays on the dashboard.
- Fields 102 (НОМЕР) and 103 (Дата оформления) are editable again so a document reproduces the
  official values exactly; `esf_documents.issue_date` column added (migration a21036a5126a).
  Footer print-stamp uses `published_at`.
- Duplicate `esf_number` is now a clean **409** (set after the item-rebuild flush, caught at commit)
  — no 500 (TD-008 stays resolved, now user-settable).
- New static asset `app/static/img/sample_qr.png` (reference QR for the preview clone).
- 23 tests pass; `config.VERSION` → 1.1.3.

### Result
The document is a complete clone of «Копия 6.pdf»: layout, font, all data, status, number, date,
and QR format all match. Inherent (correct) differences on a *live* document: its own UUID (so the
QR points to its own verification) and its real publish timestamp.

## 1.1.2 — Exact font match (2026-06-27)

### Changed
- Identified the reference form's embedded font: **DejaVu Sans** (`WKEGME+DejaVuSans` subset in
  «Копия 6.pdf») — not Arial Narrow. Bundled the full `DejaVuSans.ttf` / `DejaVuSans-Bold.ttf`
  under `app/static/fonts/`, wired via `@font-face`, and set it as the document font for HTML,
  the public page, and the WeasyPrint PDF (the PDF url_fetcher now serves the `.ttf`).
- Result: the rendered glyphs now match the official form — the font is identical, not a
  substitute. TD-005 fully resolved (the last residual deltum was the font).
- New test `test_official_font_bundled_and_served`; suite now **23 passed**. `config.VERSION` → 1.1.2.

## 1.1.1 — Visual fidelity pass (clone) (2026-06-27)

### Changed (CSS only — no logic)
- Matched the STI-007 vertical proportions to «Копия 6.pdf»: taller address rows (205/305) and
  a taller goods-item row. The rendered document (template, PDF, and public page) is now a
  near-pixel clone of the reference form.
- Verified end-to-end as a user: login → create → fill with reference data → publish → snapshot
  → public page (clean, no chrome, real embedded QR) → PDF. 22/22 tests still pass.
- Residual differences are inherent and documented: the exact government font is not bundled
  (Arial Narrow substitute), and the live app shows the real lifecycle status / auto-number /
  current date / generated QR rather than the reference's static values. `config.VERSION` → 1.1.1.
- Evidence: `docs/screenshots/clone_final.png` (template = reference data) and
  `clone_public.png` (live published page).

## 1.1.0 — Post-acceptance hardening (2026-06-27)

Closes the achievable items from the independent acceptance review. (Out of scope, by nature:
ГНС/tax-authority integration, ЭЦП/digital signature, legal validity — require external systems.)

### Added
- **Audit logging** (TD-017): `audit_service` writes `AuditLog` on LOGIN / LOGIN_FAILED /
  LOGOUT / CREATE / VALIDATE / PUBLISH / DELETE / VIEW_PUBLIC / DOWNLOAD_PDF (actor, IP,
  user-agent, document, meta). Admin viewer at `GET /admin/audit` (+ nav links).
- **CSRF protection** (TD-014): session-bound double-submit token; `require_csrf` dependency on
  save/autosave/validate/publish/delete and admin user-creation; hidden `csrf_token` in all
  forms; autosave sends it via `FormData`. Missing/invalid token → 403.
- **Login rate limiting** (TD-019): in-process sliding-window lockout (5 failures / 5 min / IP) → 429.
- **Persisted previously view-only fields** (TD-007): party `branch_inn` (203/303),
  `tax_office_code` (206/306), and item `customs_refs` now save and reload. Migration
  `9ea18ef4e591` (reversible).

### Tests
- 4 new regression tests (CSRF rejection, rate-limit lockout, audit recording, field
  persistence). Suite now **22 passed**. `config.VERSION` → 1.1.0.

## 1.0.0 — Final Release Audit (2026-06-27)

### Audit (re-verified from scratch; see RELEASE_REPORT.md)
- Functional regression 18/18 + all 22 flows incl. **DB + app restart with data persistence**.
- Security: owner isolation 8/8 → 403, bcrypt, signed/httponly/samesite cookie, UUID-only,
  snapshot immutability. DB audit: correct FKs, unique constraints, 0 duplicates/orphans.
  PDF audit: STI-007 faithfully reproduced (Minor/Cosmetic deltas only). Perf: pages 5–31 ms,
  no N+1.

### Fixed (release hardening — not a feature)
- **Production fail-closed on SECRET_KEY**: `Settings.validate_for_runtime()` raises at startup
  when `ENVIRONMENT=production` and `SECRET_KEY` is default/empty (prevents forgeable sessions).

### Docs
- README: added Deployment (production) and Troubleshooting sections.
- Added `RELEASE_REPORT.md` (scores, issues, readiness Q&A, deployment notes).

### Verdict
- **0 Critical issues → RELEASE APPROVED (1.0).** Outstanding High: audit logging (TD-017,
  fast-follow). Medium/Low items tracked in TECHNICAL_DEBT.md.

## 1.0.0-rc1 — Sprint 13R · Release Candidate 1 (2026-06-27)

### Release packaging (no new features)
- Rewrote `README.md` as the RC1 guide (architecture, run, dev login, full flow, tests, config,
  known limitations).
- `.env.example` documents `DATABASE_URL`, `SECRET_KEY`, `PUBLIC_BASE_URL`, `ENVIRONMENT`.
- `config.VERSION` → `1.0.0-rc1`.

### Final verification
- Docker PostgreSQL healthy; Alembic at head (`cf15352b4898`).
- Regression suite: **18 passed**.
- Live smoke (login → create → save → validate → publish → snapshot → PDF → QR → public):
  all green; anonymous access correctly redirected to /login; published public page served
  from snapshot.

### MVP summary (Sprints 1–13R)
PostgreSQL ESF schema · STI-007 HTML template (edit/view/public/pdf, one template) ·
draft CRUD + autosave · validation → publish lifecycle with immutable snapshots ·
HTML-identical WeasyPrint PDF · QR + public verification (published-only) ·
session auth + RBAC (ADMIN/ISSUER) · dashboard search/filter/sort · 18-test regression suite.

## 0.12.0 — Sprint 12R (2026-06-27)

### Added — Full regression suite
- `backend/tests/conftest.py` — pytest fixtures with per-test SAVEPOINT transaction isolation
  (each test rolls back; the dev DB is left unchanged and the suite is repeatable). Fixtures:
  `db_session`, `override_db`, `seed_users`, `admin`, `issuer`, `anon`.
- `backend/tests/test_regression.py` — 18 tests across health, auth + RBAC, CRUD + totals,
  validation, publish + snapshot (hash verified), immutability (409 + ORM-blocked snapshot),
  PDF (draft + published), QR, public verification (published-only), autosave, dashboard polish.
- `backend/requirements-dev.txt` (pytest). `config.VERSION` → 0.12.0.

### Result
- `pytest tests/ -q` → **18 passed**. Remaining warnings are framework deprecations
  (`on_event`, `TemplateResponse` arg order) — tracked, non-blocking.

## 0.11.0 — Sprint 11R (2026-06-27)

### Added — Dashboard polish (client-side, no new backend features)
- Search box (filters by number / supplier / buyer), status filter dropdown, and
  sortable columns (click headers; asc/desc arrow) on the dashboard.
- A live "shown / total" count and a "Ничего не найдено" empty-results state.
- Delete confirmation now names the document and warns it is irreversible.
- `list_rows` exposes `status_code` and `created_sort` to drive client filtering/sorting.
- `config.VERSION` → 0.11.0.

## 0.10.0 — Sprint 10R (2026-06-27)

### Added — Autosave
- `POST /esf/{uuid}/autosave` — JSON endpoint that persists the draft via the existing
  `ESFService.save` without navigation; returns `{ok, saved_at}`.
- Client autosave in `form.html` (edit mode only): saves ~1.5s after the last change
  (debounced) and every 10s while dirty; "+ строка"/row-delete mark the form dirty. A status
  indicator in the edit bar shows Не сохранено / Сохранение… / Сохранено HH:MM:SS / errors.

### Safety
- Autosave reuses the editable + owner/admin guards: published docs return 409 (read-only),
  unauthenticated requests redirect to /login. No new document features were added.
- `config.VERSION` → 0.10.0.

## 0.9.0 — Sprint 9R (2026-06-27)

### Added — Authentication + RBAC
- Session-based login via Starlette `SessionMiddleware` (signed cookie, `SECRET_KEY`).
- `app/core/passwords.py` — bcrypt hashing used directly (passlib 1.7.4 is incompatible with
  bcrypt 5.x in this env).
- `app/core/security.py` rewritten: `get_current_user` reads the session and raises
  `NotAuthenticated` when absent; `get_optional_user`; `require_admin`; existing
  `require_owner_or_admin` kept. A FastAPI exception handler redirects `NotAuthenticated` → /login.
- `app/services/auth_service.py` — `authenticate`, `create_user`, `ensure_roles`,
  `ensure_dev_admin`; roles **ADMIN** / **ISSUER**.
- `app/repositories/user_repository.py` — user/role data access.
- Routers: `app/routers/auth.py` (`GET/POST /login`, `GET /logout`),
  `app/routers/admin.py` (`GET/POST /admin/users`, admin-only).
- Templates: `login.html`, `admin_users.html`; dashboard shows the current user, a logout link,
  and a "Пользователи" link for admins.
- Dev-only startup seed ensures roles + an initial admin (`admin` / `admin123`).

### Security
- All ESF routes (dashboard, create, edit, save, validate, publish, delete, pdf, result) now
  require a logged-in user; unauthenticated requests redirect to /login.
- RBAC: admins see/manage all documents and users; issuers see only their own documents and
  cannot reach `/admin/*` (403).
- Public verification (`/esf/check-esf`) and `/qr/*.png` remain open and read-only.

### Changed
- Dependencies: `bcrypt==5.0.0` and `itsdangerous==2.2.0` added; broken `passlib[bcrypt]` removed.
- `config.VERSION` → 0.9.0.

### Resolved technical debt
- TD-006 (auth dev stand-in) — replaced by real session auth + RBAC. (The legacy `dev` user row
  remains and owns earlier documents but cannot log in; admins manage those documents.)

## 0.8.0 — Sprint 8R (2026-06-27)

### Added — validation + generate/publish lifecycle
- `app/services/validation_service.py` — Validation Engine (requisites, INN digits, ≥1 item
  with name/unit/price>0/qty>0, currency, signatory) returning human-readable errors.
- `app/services/snapshot_service.py` — freezes the published template-ready payload into an
  immutable `ESFSnapshot` with a sha256 content hash; `latest_snapshot` helper.
- Lifecycle in `ESFService`: `validate()` (DRAFT→VALIDATED), `publish()`
  (validate → assign esf_number → PUBLISHED + published_at → snapshot + QR), `is_editable`,
  `serialize_published` (renders from the snapshot), `next_esf_number()`.
- Routes: `POST /esf/{uuid}/validate`, `POST /esf/{uuid}/publish`. Edit page gains
  "Проверить" / "Сформировать" buttons (form `formaction`), an errors panel and a validated
  banner. Published docs open read-only (locked owner bar; no edit form).
- PDF and `GET /esf/check-esf` render from the snapshot for published docs; the public page is
  now **PUBLISHED-only** (drafts → 404). The real QR is embedded in the document footer once
  published (WeasyPrint url_fetcher also serves `/qr/*.png`).

### Changed
- `esf_number` (field 102) is now read-only and auto-assigned at publish (was a free input).
- Editing a VALIDATED draft reverts it to DRAFT (re-validation required).
- Dashboard hides "Удалить" for published documents.
- `config.VERSION` → 0.8.0.

### Security / integrity
- Published documents are immutable: `save`/`delete` return HTTP 409.
- `ESFSnapshot` rows are write-once — ORM `before_update`/`before_delete` listeners raise
  `SnapshotImmutableError`.
- Public verification exposes only PUBLISHED documents, read-only, from the snapshot.

### Resolved technical debt
- TD-002 (snapshot immutability enforced), TD-008 (no hand-typed numbers; auto-assigned),
  TD-009 (PDF renders from snapshot for published), TD-010 (public publish-gated + QR embedded).

## 0.7.0 — Sprint 7R (2026-06-27)

### Added
- External verification flow:
  - `app/services/qr_service.py` — QR PNG generation; `qr_target()` encodes
    `/esf/check-esf?documentUUID={uuid}` (absolute when `PUBLIC_BASE_URL` is set); persists
    `backend/storage/qr/{uuid}.png`.
  - `GET /qr/{uuid}.png` — returns `image/png` (open; encodes only the public URL).
  - `GET /esf/check-esf?documentUUID={uuid}` — PUBLIC verification page, no login, read-only,
    renders the SAME `templates/esf/form.html` with `mode="public"` (no edit/dashboard chrome).
  - `GET /result/{uuid}` — owner/admin result page: QR image, public link, PDF link,
    download-PDF / download-QR / open-public / back-to-dashboard.
  - `result.html` (utility landing page — not a duplicate of the document template).
  - "Результат" links on the dashboard and edit action bar.
  - `PUBLIC_BASE_URL` setting in `app/core/config.py`.
- `qrcode[pil]` + `pillow` added to the active dependency set.

### Security
- Public route has no auth dependency (verified open); edit/result stay owner/admin-guarded.
- `/esf/check-esf` and `/esf/new` are declared before the `/esf/{uuid}` catch-all so the
  literal paths win. UUID-only URLs; no sequential id exposed.

### Notes
- Public page currently shows any existing document by UUID (no publish gate yet — TD-010).
- QR is now real (placeholder removed from the verification flow; the document footer still
  shows a QR placeholder box until the snapshot/publish step embeds the image).

## 0.6.0 — Sprint 6R (2026-06-27)

### Added
- PDF generation from the **same** HTML template (`templates/esf/form.html`, `mode="pdf"`):
  - `app/services/pdf_service.py` — WeasyPrint renderer; a small url_fetcher serves the bundled
    `esf_form.css` so rendering needs no running server or network. Sets
    `DYLD_FALLBACK_LIBRARY_PATH` to Homebrew on macOS so pango/cairo load in-process.
  - `GET /pdf/{uuid}.pdf` (`app/routers/esf.py`) — owner/admin-guarded, renders from the
    document's serialized view data; returns `application/pdf` inline.
  - "PDF" links added to the edit action bar and the dashboard.
- `weasyprint==66.0` added to the active dependency set.

### Changed
- ReportLab PDF layout abandoned — the live app has no `reportlab` usage (it remains only in
  quarantined `legacy/`). One template now serves edit / view / public / PDF.
- Rate fields (`currency_rate`, item `vat_rate`) display normalized (no trailing-zero noise:
  `1.226300` → `1.2263`, `0.00` → `0`) in both HTML and PDF; price/qty keep fixed scale.

### Notes / fidelity
- WeasyPrint reproduces the flexbox layout accurately and emits vector A4-landscape PDF, so the
  preferred renderer was kept (no alternative needed).
- HTML and PDF share template + stylesheet → identical layout by construction; remaining
  differences are engine-level only (font shaping; the empty 406 date-box group sits a touch
  tighter in WeasyPrint). QR remains a placeholder (Sprint 7).

## 0.5.0 — Sprint 5R (2026-06-27)

### Added
- ESF draft CRUD wired to the normalized schema, Controller → Service → Repository:
  - `app/routers/esf.py` — `GET /dashboard`, `GET /esf/new`, `GET /esf/{uuid}`,
    `POST /esf/{uuid}/save`, `POST /esf/{uuid}/delete` (UUID-only URLs).
  - `app/services/esf_service.py` — form⇄schema mapping, item rebuild, totals recompute,
    create/save/delete, serialize-to-template.
  - `app/repositories/esf_document_repository.py` — UUID-keyed data access, owner scoping.
  - `app/core/security.py` — `get_current_user` (dev stand-in) + `require_owner_or_admin`.
  - `app/templates/dashboard.html` — document list (number, date, supplier, buyer, status,
    updated, open, delete).
- `form.html` gained edit-mode bindings: `name`-attributed inputs, an edit action bar
  (Сохранить / + строка / К списку / Удалить), per-row delete, and add-row JS. Items bind via
  repeated form keys parsed with `getlist`. View/public output is unchanged.
- Totals recomputed on save: subtotal = Σ amount, VAT = Σ vat, НсП = Σ nsp,
  grand = subtotal+VAT+НсП, foreign-currency = grand ÷ rate.
- `python-multipart` added to the active dependency set (form parsing).

### Security
- All ESF routes run through `get_current_user`; the service enforces owner-or-admin access.
- URLs expose only the document UUID; sequential ids are never used.
- `User.is_admin` stays false by default; the dev user cannot log in (placeholder hash).

### Notes / fidelity
- View-mode render is **byte-identical** to Sprint 4R v2 (image diff: no difference).
- Edit mode renders boxed fields (INN/dates/currency) as single inputs; view/public keep boxes.
- No PDF / QR / public page / generate workflow in this sprint.

## 0.4.0 — Sprint 4R (2026-06-27)

### Added
- STI-007 ESF visual template `backend/app/templates/esf/form.html` — one reusable Jinja
  template with `mode` = edit / view / public, reproducing «Копия 6.pdf» in HTML/CSS
  (header band, status row 101–103, supplier/buyer requisites 201–308, supply info 401–407,
  currency strip, goods table with grouped НДС/НсП headers, totals rows, signatory 450,
  QR placeholder).
- ESF stylesheet `backend/app/static/css/esf_form.css` — dense, monochrome, hairline-ruled
  document styling; boxed-digit (INN/date) components; print `@page A4 landscape`.
- Dev-only preview route `GET /dev/esf-preview` (`app/routers/dev_preview.py`), mounted only
  when `ENVIRONMENT != production`; supports `?mode=edit|view|public`.
- Sample mock data `backend/app/dev_sample.py` (values transcribed from Копия 6.pdf).
- `main.py` now mounts `/static` (CWD-safe absolute path) and conditionally includes the dev
  preview router.
- `jinja2` returned to the active dependency set.

### Visual refinement (screenshot-driven, headless Chromium vs. Копия 6.pdf)
- Field-code chips moved to each cell's top-left corner (was a full-height divider column).
- INN/branch-INN and dates now render as fixed-count boxed cells (`innbox`/`datebox` macros):
  14 cells for INN (filled from the left, remainder blank), 2/2/4 for dates — empty fields
  still show their boxes, matching the official form.
- Currency strip left-aligned with the traceability checkbox pushed right.
- Field 406 (Корректировка) now shows its empty date boxes.

### Notes
- Visual foundation ONLY — no CRUD, no DB access, no PDF/QR, no auth, no workflow.
- The form is recreated in original HTML/CSS; the PDF is never used as an image or rasterized.
- Residual cosmetic deltas (hairline border weight, minor row spacing, condensed-font
  availability) tracked as TD-005 — best finalized alongside PDF generation (Sprint 7).

## 0.3.0 — Sprint 3R (2026-06-26)

### Changed (breaking)
- **Rebuilt the data model for the Kyrgyz STI-007 ESF.** The generic
  title/applicant/description `Document` model is replaced by a normalized ESF schema.
- Quarantined the generic Sprint 3–11 implementation under
  `backend/legacy/` (models, services, routers, templates, SQLite session,
  stale migration). Not imported anywhere.
- Consolidated to **one** declarative `Base` (`app/db/base.py`) and **one** engine
  (`app/db/session.py`). Removed the SQLite runtime path — **PostgreSQL only**.
- `app/main.py` reduced to the FastAPI skeleton + health endpoint (no routers/UI/PDF).
- `requirements.txt` trimmed to the active Sprint 3R dependency set (added `alembic`,
  `psycopg2-binary`; deferred jinja2/reportlab/qrcode to later sprints).

### Added
- ESF models: `User`, `Role` (+`user_roles`), `Organization`, `ESFDocument`, `ESFParty`,
  `ESFSupplyInfo`, `ESFItem`, `ESFTotals`, `ESFSignature`, `ESFSnapshot`, `AuditLog`.
- Lifecycle enum `document_status`: DRAFT, VALIDATED, SNAPSHOT_CREATED, PUBLISHED, CANCELLED;
  and `party_type`: SUPPLIER, BUYER.
- Alembic baseline migration `cf15352b4898_esf_baseline_schema` (12 tables, JSONB, UUID,
  indexes, unique constraints, FK ondelete rules); reversible — drops enum types on downgrade.
- `app/core/config.py` settings (env-driven `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`).
- `scripts/verify_schema.py` — verifies tables, enum values, and `is_admin` default.
- `scripts/seed_dev.py` — dev-only roles + `admin/admin123`, refuses to run in production.

### Security
- `User.is_admin` now defaults to **false** (was true).
- Default credentials `admin/admin123` exist only in the dev seed (guarded by `ENVIRONMENT`).
- Public access designed around document **UUID**, not the sequential id/number.

### Verified
- `alembic upgrade head` applies cleanly to PostgreSQL 15; `alembic current` = head.
- Down→up migration cycle succeeds (no "type already exists").
- `scripts/verify_schema.py` → PASS. FastAPI `GET /` → `{"status":"running",...}`.

## 0.2.0 — Sprint 2 (2026-06-26)

- Created `docker-compose.yml` with PostgreSQL 15 service
- Database: `esf`, user: `esf`, port: 5432, persistent volume, healthcheck
- Added Docker run instructions to README
- Verified: container starts healthy, `database system is ready to accept connections`

## 0.1.0 — Sprint 1 (2026-06-26)

- Created `backend/app/main.py` with FastAPI app and `GET /` health endpoint
- Created `backend/requirements.txt` (fastapi 0.111.0, uvicorn 0.30.1)
- Added run instructions to README
- Verified: `uvicorn app.main:app --reload` runs; endpoint returns `{"status": "running"}`

## 0.0.1

- Clean starter repository created.
- Added CLAUDE.md.
- Added roadmap and project state files.
