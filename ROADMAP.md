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

Status: MVP feature-complete (v1.1.3, RC1). Regression suite: **55 tests pass** (verified 2026-07-26).

## Remaining — post-MVP backlog (see TECHNICAL_DEBT.md)
- Production hardening: shared-store rate limiting, Docker WeasyPrint libs,
  structured logging, styled error pages, production DB secrets.
- Framework deprecation cleanup; dedicated test DB; cosmetic PDF parity.

Out of scope (require external systems): ГНС/tax-authority integration,
ЭЦП/digital signature, legal validity.
