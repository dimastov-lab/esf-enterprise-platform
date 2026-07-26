# TODO.md

## Completed
- [x] Step 0 — technical specification and architecture review
- [x] Sprint 1 — application foundation
- [x] Sprint 2 — PostgreSQL Docker foundation
- [x] Sprint 3R — correct ESF database schema
- [x] Sprint 4R — STI-007 visual HTML template
- [x] Sprint 5R — ESF draft create/edit/data binding
- [x] Sprint 6R — HTML-to-PDF identity with WeasyPrint
- [x] Sprint 7R — QR generation + public verification + result page
- [x] Sprint 8R — validation engine + generate/publish workflow + status transitions + snapshot
- [x] Sprint 9R — Authentication + RBAC (session login, roles ADMIN/ISSUER, admin user mgmt)
- [x] Sprint 10R — Autosave (debounced on change + every 10s; JSON endpoint; read-only safe)
- [x] Sprint 11R — Dashboard polish (search + status filter + sortable columns + confirmations)
- [x] Sprint 12R — Full regression testing (18 pytest tests, transaction-isolated, all green)
- [x] Sprint 13R — Release Candidate 1 (README + .env + packaging + final verification)

## Status
MVP feature-complete + post-acceptance hardening — **v1.1.0**. Queue empty.

## v1.1 hardening (done — from independent acceptance review)
- [x] Audit logging on critical actions + admin viewer (TD-017)
- [x] CSRF protection on state-changing POSTs (TD-014)
- [x] Login rate limiting (TD-019)
- [x] Persist branch_inn / tax_office_code / item customs_refs (TD-007)

## Out of scope (require external systems — not buildable from this repo)
- ГНС / tax-authority integration · ЭЦП / digital signature · legal validity of issued ESF

## Post-MVP backlog (from TECHNICAL_DEBT.md; not blocking RC1)
- Production hardening: CSRF (TD-014), rate limiting (TD-013), Docker WeasyPrint libs (TD-009).
- Framework deprecation cleanup (TD-015); dedicated test DB (TD-016).
- Schema completeness for view-only STI-007 fields (TD-007); audit log; cosmetic PDF parity (TD-005).
