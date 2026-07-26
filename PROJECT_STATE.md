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

Awaiting direction.
