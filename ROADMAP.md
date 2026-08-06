# ROADMAP.md

## Completed — MVP (Release Candidate 1, 1.0.0-rc1)
1. Architecture review
2. PostgreSQL foundation
3. Correct ESF schema
4. STI-007 visual template
5. Draft create/edit/data binding
6. HTML-to-PDF identity
7. QR + public verification + result page
8. Validation + generate/publish workflow + immutable snapshot
9. Authentication + RBAC (session login, roles, admin user management)
10. Autosave (debounced on change + every 10s)
11. Dashboard polish (search + filter + sort + confirmations)
12. Full regression testing (transaction-isolated pytest suite)
13. Release Candidate 1 (1.0.0-rc1) — README, packaging, final verification

## Completed — post-MVP hardening (v1.1.x)
14. Audit logging on all critical actions + admin viewer (/admin/audit) — TD-017
15. CSRF protection on all state-changing POSTs — TD-014
16. Login rate limiting (5 / 5 min / IP → 429) — TD-019
17. Persisted previously view-only fields (branch_inn, tax_office_code, item customs_refs) — TD-007
18. Exact bundled DejaVu Sans font + official QR format — pixel-faithful clone (TD-005)
19. Audit remediation (AUDIT_2026-07-28): repository layer boundary (A-2), error
    visibility in batch/audit paths (A-6), `owner_id NOT NULL` (A-7, migration b1c2d3e4f5a6)
20. Audit remediation P2 (AUDIT_2026-07-28): decomposed `ESFService` god-object into
    `ESFSerializer` + `ESFQueryService` + lifecycle service (A-1), PDF/ZIP render moved
    to `pdf_service` (A-4), removed dead `snapshot_service.latest_snapshot` (A-5)
21. Supply-chain hardening (AUDIT_2026-07-28 I-6): hash-pinned `requirements.lock` +
    Dockerfile `--require-hashes`
22. CSP hardening (AUDIT_2026-07-28 I-4): `script-src` nonce instead of `'unsafe-inline'`;
    all inline event handlers converted to listeners; nginx CSP dropped (app is sole authority)
23. Public verification rate limiting (30 / 60 s / IP → 429, before any DB work,
    shared bucket for /esf/check-esf + /qr/*.png) — TD-013
24. v1.1.5 — final hardening backlog: shared-store (Postgres) rate-limit counters for
    multi-worker production; styled HTML error pages (404/403/409/429) with JSON kept
    for API clients; lifespan migration (TD-015); dedicated test DB + injectable QR
    storage (TD-016); Docker-secrets `*_FILE` config; debt-register reconciliation
    (TD-001, TD-009)

25. v1.1.6 — housekeeping: version metadata truth-up (config.VERSION 1.0.0-rc1 → 1.1.6,
    prod image tag, CLAUDE.md status), TD-004 executed (dev-preview route + sample data
    deleted), TD-020 closed by-design, test-count history reconciled in PROJECT_STATE

26. v1.2.0 — AIOS Core convergence (ADR-0015), 2026-08-05:
    - AUTH-01: long-lived PG-backed API credentials (`esf_` prefix, SHA-256 hash,
      optional expiry, revoke, last_used_at touch) — migration d0e1f2a3b4c5
    - Layer 1 (Tasks): fire-and-forget AIOS task lifecycle on ESF state transitions;
      `ESFDocument.aios_task_id` — migration e1f2a3b4c5d6
    - Layer 3 (Memories): published snapshots written to AIOS Memories before commit;
      `ESFSnapshot.aios_memory_id`, idempotent via snapshot UUID — migration 9bb4bef2e079
    - Layer 2 (Identity): AIOS JWT validation in `get_current_api_user`; falls back
      to ESF JWT when AIOS unavailable; `esf_` credentials bypass AIOS
    - 51 tests added; suite: **169 tests pass**

27. v1.2.1 — AIOS operability (2026-08-05):
    - `AIOSBridgeService.ping()` + `_NoOpBridge.ping()` stub
    - `GET /admin/aios` admin status page: enabled flag, connectivity badge (ping),
      base URL / workspace / token presence, per-entity link-count stats
    - `config.VERSION` → `"1.2.0"`; 10 tests; suite: **179 tests pass**

28. v1.2.3 — Credential security + SDK adoption (2026-08-06):
    - TD-023: `validate_for_runtime()` rejects `http://` AIOS_BASE_URL in production
    - TD-027: `MAX_TTL_DAYS=90`; `CREDENTIAL_ISSUED`/`CREDENTIAL_REVOKED` audit;
      `POST /admin/users/{id}/deactivate` revokes all credentials + admin guard
    - TD-021: `AIOSBridgeService` → `aios_sdk.AIOSClient`; Python 3.11 → 3.12
    - Suite: **195 tests pass**

Status: **v1.2.3** — AIOS convergence + operability + SDK adoption + credential security
complete. All three integration layers (Tasks / Identity / Memories) are live behind
`AIOS_ENABLED` flag; behaviour when flag is false is identical to v1.1.6. Remaining work
is owner-only P0 (ACTION_REQUIRED.md) and the deliberately out-of-scope items below.

Out of scope (require external systems): ГНС/tax-authority integration,
ЭЦП/digital signature, legal validity.
