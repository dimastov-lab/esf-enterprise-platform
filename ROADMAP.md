# ROADMAP.md

Completed:
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
12. Full regression testing (18 pytest tests, transaction-isolated)
13. Release Candidate 1 (1.0.0-rc1) — README, packaging, final verification

Status: MVP feature-complete. Queue empty.

Post-MVP (backlog): production hardening (CSRF, rate limiting, Docker WeasyPrint libs),
audit log, deprecation cleanup, schema completeness for view-only fields, cosmetic PDF parity.
