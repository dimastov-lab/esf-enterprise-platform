# PROJECT_STATE.md

Current Mode: Autonomous Development Mode — queue complete.
Current Milestone: **MVP feature-complete — Release Candidate 1 (1.0.0-rc1).**
Current Status: Schema, STI-007 template (edit/view/public/pdf), DB binding + autosave,
validation → publish lifecycle with immutable snapshots, HTML-identical PDF, QR + public
verification, session auth + RBAC, dashboard polish, and an 18-test regression suite are all
complete and verified.

Completed through: Sprint 13R (Release Candidate 1). TODO queue is empty.

Verification (RC1): Docker PostgreSQL healthy; Alembic at head; `pytest tests/ -q` → 18 passed;
live end-to-end flow green; anonymous access redirects to /login; published public/PDF from snapshot.

Run: see README.md. Dev login admin/admin123 (development only).

Remaining (post-MVP, non-blocking — see TECHNICAL_DEBT.md): production hardening (CSRF TD-014,
rate limiting TD-013, Docker WeasyPrint libs TD-009), framework deprecation cleanup (TD-015),
dedicated test DB (TD-016), schema completeness for view-only STI-007 fields (TD-007), audit log,
cosmetic PDF parity (TD-005).

Final Release Audit: PASSED — 0 Critical. Release APPROVED (1.0).

v1.1.0 — post-acceptance hardening (closes the achievable acceptance-review punch-list):
- Audit logging on all critical actions + admin viewer (/admin/audit) — TD-017 resolved.
- CSRF protection on all state-changing POSTs — TD-014 resolved.
- Login rate limiting (5/5min/IP → 429) — TD-019 resolved.
- Persisted previously view-only fields: branch_inn (203/303), tax_office_code (206/306),
  item customs_refs (migration 9ea18ef4e591, reversible) — TD-007 resolved.
- 22 regression tests pass; clean install + restart persistence + immutability re-verified.

v1.1.2 — exact font: the reference form embeds DejaVu Sans; bundled it (app/static/fonts) and
used it for HTML + public + PDF, so the document is now a pixel-faithful, glyph-exact clone of
«Копия 6.pdf» (TD-005 resolved). 23 tests pass.

Out of scope (require external systems): ГНС/tax-authority integration, ЭЦП/digital signature,
legal validity. Remaining hardening: shared-store rate limit, structured logging, styled error
pages, prod DB secrets — see TECHNICAL_DEBT.md.

v1.1.3 — full visual match: status 101 «первоначальный (Принят)», editable number 102 / date 103,
QR in official esf.salyk.kg format (preview clone pixel-identical to the reference QR). The document
is a complete clone of «Копия 6.pdf» (layout + DejaVu Sans font + all data + QR). 23 tests pass.

Environment re-check 2026-07-26 (no feature changes): Docker PostgreSQL healthy,
Alembic at head (a7d4e91c25f8), `pytest tests/ -q` → **55 passed**. Note: the suite
has grown from the 23 recorded at v1.1.3 to 55 — tests were added after RC1 without a
state entry. This is a content/history gap worth a dedicated reconciliation pass, not a
wording fix. (Historical per-version counts above are left as-is: they were correct when written.)

Audit remediation 2026-07-29 (code quality, no user-facing change): closed audit
findings A-2 (all `Session` access in `ESFService` moved behind
`ESFDocumentRepository` — `flush`/`refresh`/`rollback`/`add_pending`), A-6
(`batch_publish` and `audit_service.record` now log failures instead of swallowing
them), and A-7 (`counterparties.owner_id` / `goods.owner_id` → `NOT NULL`, reversible
migration `b1c2d3e4f5a6`; dead NULL-owner cache rows purged). Suite now **82 tests
pass**; Postgres at head `b1c2d3e4f5a6`; `alembic` downgrade/upgrade round-trips clean.
Also closed the P2 architecture items: A-1 (`ESFService` god-object split into
`ESFSerializer` + `ESFQueryService` + a lifecycle/coordinator `ESFService`, 755→574
lines, public API unchanged), A-4 (ESF PDF/ZIP rendering moved from the router into
`pdf_service`), A-5 (removed dead `snapshot_service.latest_snapshot`). 82 tests pass,
coverage 91%, ruff clean. Then closed the last two technical items: I-6 (hash-pinned
`requirements.lock` + Dockerfile `--require-hashes`) and I-4 (CSP `script-src` moved
from `'unsafe-inline'` to a per-request nonce; all inline event handlers converted to
listeners; nginx CSP dropped so the app is the single authority). I-4 was verified in
the browser end-to-end (login→dashboard→editor→publish→view) with zero CSP violations;
83 tests pass. **All technical audit findings are now closed** — see `AUDIT_2026-07-28.md`
§7. Remaining: only owner-only P0 tasks (R-1/I-2/I-1, see `ACTION_REQUIRED.md`) and the
deliberately-out-of-scope items (style-src unsafe-inline; S-0 legal review).

v1.1.4 — TD-013 resolved: per-IP sliding-window throttle (30/60s → 429 + Retry-After) on the
open verification routes (`/esf/check-esf`, `/qr/*.png`), enforced before any DB work (caps
UUID probing + audit-row write amplification). 85 tests pass. Remaining hardening is only the
known in-process→shared-store limiter upgrade for multi-worker production.

v1.1.5 — final hardening backlog closed (2026-08-01). (1) Shared-store rate limiting: the
login lockout + public throttle counters moved from per-process dicts to the shared
`rate_limits` table (migration c7d8e9f0a1b2, reversible; atomic upsert; backend selectable,
production default = postgres) — limits now hold across uvicorn workers/replicas and survive
restarts. (2) Styled error pages: one `error_response` surface — browsers get the dark-shell
HTML page (per-status title + request id) for 404/403/409/429, API clients keep JSON, headers
(Retry-After) pass through; all router-level bare-text 404/429 migrated. (3) TD-015: startup
seed → lifespan handler (import clean under -W error::DeprecationWarning). (4) TD-016:
TEST_DATABASE_URL for a dedicated suite DB + QR_STORAGE_DIR (publish tests write PNGs to a
tmp dir, not the working tree). (5) Docker secrets: SECRET_KEY_FILE / DATABASE_URL_FILE.
(6) Debt register reconciled: TD-001 and TD-009 were already done in fact, now marked.
**104 tests pass.** Every code-side TECHNICAL_DEBT item is closed; remaining work is
owner-only P0 (ACTION_REQUIRED.md: R-1 private materials, I-2 secret rotation, I-1 TLS cert)
and deliberate out-of-scope (ГНС/ЭЦП/legal validity; style-src 'unsafe-inline').

v1.1.6 — housekeeping (2026-08-01). (1) Release metadata truth-up: `config.VERSION`
1.0.0-rc1 → 1.1.6, prod image tag `esf-platform:1.1.6`, CLAUDE.md status block updated
(Sprint 12 marked complete). (2) TD-004 executed: `/dev/esf-preview` + `dev_sample.py`
deleted (form renders real data since Sprint 5R; the route was a leftover). (3) TD-020
closed as by-design (official form has no separate BIK box — field 207 is a single text
field). (4) Test-count history reconciled — see below. **The debt register now has zero
open items.**

Test-count history reconciliation (closes the gap flagged 2026-07-26): the repo's history
starts at the v1.1.3 baseline (`d3c325b`, 23 tests). The undocumented 23→55 growth happened
in the July security-audit remediation commits, each of which added regression tests without
a state entry: `8fee0b7` (XSS/owner-scoping), `9a09439` (H4/M infra), `94f2217` (H2
concurrency-safe publish), `4205560` (H3 DB-level immutability), `8bad365` (M10 validation),
`18ac7df` (reliability block), `8899457` (audit #2 adversarial blocks 2–4), `9c78d8f`
(authenticity/watermark). From 55 the documented chain resumes: 82 (A-1..A-7 remediation)
→ 83 (I-4 CSP) → 85 (v1.1.4 TD-013) → 104 (v1.1.5 hardening).

Owner-only P0 verification 2026-08-03: **R-1 done** (no private materials in the repo tree;
relocated to ~/Desktop/ESF-Private-Materials), **I-2 partially done** (.env.production absent
from repo and Desktop root; value rotation still pending), **I-1 open** (needs the real
server/domain). See ACTION_REQUIRED.md «Статус».

v1.2.0 — AIOS Core convergence (2026-08-05). AUTH-01 + Layers 1/2/3 complete.

**AUTH-01** (PG-backed API credentials): new `api_credentials` table (migration
`d0e1f2a3b4c5`); `CredentialService` issue/validate/revoke/list; token format
`esf_<base64url(32B)>` (SHA-256 hashed, shown once); REST endpoints
`POST/GET/DELETE /auth/credentials`; `get_current_api_user` routes `esf_` tokens to
PG path. 23 tests.

**Layer 1 — Tasks**: `AIOSBridgeService` + `_NoOpBridge`; `ESFDocument.aios_task_id`
(migration `e1f2a3b4c5d6`); `ESFService` wired at create/validate/publish/cancel.
Config: `AIOS_ENABLED`, `AIOS_BASE_URL`, `AIOS_TOKEN(_FILE)`, `AIOS_WORKSPACE_ID`. 9 tests.

**Layer 3 — Memories**: `AIOSBridgeService.memory_create()`; `ESFSnapshot.aios_memory_id`
(migration `9bb4bef2e079`); called before commit in `publish()` (INSERT, not UPDATE);
`snapshot_service.make_snapshot()` now generates UUID in Python (pre-flush accessible).
10 tests.

**Layer 2 — Identity**: `AIOSBridgeService.identity_verify(user_token)` (`GET
/api/v1/identity/me`); wired in `get_current_api_user`: AIOS first → ESF JWT fallback
(graceful degradation when AIOS down); `esf_` credentials bypass AIOS. 9 tests.

Alembic head: `8d5e97b2590b`. Suite: **169 tests pass** (2026-08-05).
All AIOS paths are gated on `AIOS_ENABLED=true`; standalone behaviour unchanged.

Security review hardening applied (commit 89ce7a3, 2026-08-05):
- C1: httpx/httpcore/certifi added to requirements.lock (prod container was unbootable)
- C2+I3: AIOS claims type-check + AIOS_EXPECTED_TENANT_ID tenant binding guard
- I8: repo.commit() moved outside fire-and-forget try in create_draft (DB errors now surface correctly)
- I9: workspace_id sent in task_create/memory_create request bodies
- TD-023..TD-027: cleartext relay / DoS / hybrid-fallback revocation / row-lock publish / credential TTL parked in TECHNICAL_DEBT.md

Suite: **169 tests pass** (2026-08-05). Branch: main.

v1.2.1 — AIOS operability (2026-08-05). `AIOSBridgeService.ping()`: GET
`/api/v1/health`, returns true on <500, false on network error; `_NoOpBridge.ping()`
returns false. `GET /admin/aios` (admin-only): shows enabled/disabled badge, base URL,
workspace ID, token presence, live connectivity (ping), per-entity link counts (docs
with `aios_task_id`, snapshots with `aios_memory_id`). Template `admin_aios.html`
consistent with admin_audit style. 10 tests. `config.VERSION = "1.2.0"`.
Suite: **179 tests pass** (2026-08-05).

v1.2.3 — Credential security + SDK adoption (2026-08-06).
**TD-023**: `validate_for_runtime()` rejects `http://` AIOS_BASE_URL in production
when `AIOS_ENABLED=true`. 4 tests.
**TD-027**: `MAX_TTL_DAYS=90` enforced in `CredentialService.issue()`; distinct
`CREDENTIAL_ISSUED`/`CREDENTIAL_REVOKED` audit actions; `AuthService.deactivate_user()`
→ `POST /admin/users/{id}/deactivate` revokes all credentials + audit + admin guard.
**TD-021**: `AIOSBridgeService` rewritten to use `aios_sdk.AIOSClient` for tasks,
memories, ping; `identity_verify` retains httpx (not in SDK). Python target 3.11 → 3.12
(Dockerfile, pyproject.toml, requirements.txt). `config.VERSION = "1.2.3"`.
TD-021 / TD-023 / TD-027 closed.
Suite: **195 tests pass** (2026-08-06). Alembic head: `8d5e97b2590b`.

ESF-RUNTIME-001 — production deploy prep (2026-08-06).
`docker-compose.prod.yml`: image tag updated `1.1.6` → `1.2.3`; AIOS optional env
vars added (`AIOS_ENABLED`, `AIOS_BASE_URL`, `AIOS_TOKEN`, `AIOS_WORKSPACE_ID`,
`AIOS_EXPECTED_TENANT_ID` — all default to disabled/empty).
`.env.production.example`: AIOS section added.
Docker build requires Docker Desktop running:
  `docker build -t esf-platform:1.2.3 ./backend`
  `docker compose -f docker-compose.prod.yml --env-file .env.production up -d`
Suite: **195 tests pass** (2026-08-06). Owner-only I-1 (TLS cert + real domain) still open.

v1.2.4 — async AIOS identity + credential rate-limiting (TD-024, 2026-08-06).
`get_current_api_user` is now `async def`; uses `httpx.AsyncClient` (2 s timeout,
was sync httpx 5 s in Starlette threadpool — DoS vector). New `throttle_api()`
rate-limiter (20 req/60 s/IP, shared Postgres bucket `api:`) applied to
POST/GET/DELETE `/auth/credentials`. `_NoOpBridge.async_identity_verify` stub added.
TD-024 closed. Suite: **200 tests pass** (2026-08-06).

TD-026 fix (same release): `memory_create()` moved AFTER `self.repo.commit()` in
`publish()` — row lock is released before the 5 s AIOS HTTP call. `ESFSnapshot`
ORM guard narrowed to payload fields only (`payload_json`, `sha256`, `immutable`);
`aios_memory_id` written in a post-commit UPDATE. Alembic migration
`a2b3c4d5e6f7` narrows the matching DB-level PL/pgSQL trigger to the same
field set — without it, the post-commit UPDATE would be rejected by the DB in
production. TD-026 closed.

TD-025 closed (same release): `AIOSTokenRejectedError` wired into
`get_current_api_user` — 4xx responses raise HTTP 401 immediately, no ESF JWT
fallback. 5xx/network errors still return `None` so graceful degradation is
preserved when AIOS is down. 1 new integration test
(`test_aios_explicit_rejection_blocks_esf_jwt_fallback`). TD-025 resolved.

`config.VERSION = "1.2.4"`. Suite: **211 tests pass** (2026-08-06).

Awaiting direction.
