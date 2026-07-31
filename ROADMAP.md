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

Status: MVP feature-complete (v1.1.4, RC1). Regression suite: **85 tests pass** (verified 2026-08-01).
All technical audit findings closed; remaining work is owner-only P0 (see ACTION_REQUIRED.md).

## Remaining — post-MVP backlog (see TECHNICAL_DEBT.md)
- Production hardening: shared-store rate limiting, Docker WeasyPrint libs,
  structured logging, styled error pages, production DB secrets.
- Framework deprecation cleanup; dedicated test DB; cosmetic PDF parity.

Out of scope (require external systems): ГНС/tax-authority integration,
ЭЦП/digital signature, legal validity.
