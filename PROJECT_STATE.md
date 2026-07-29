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
coverage 91%, ruff clean. See `AUDIT_2026-07-28.md` §7. Remaining audit items: P0
owner-only tasks (R-1/I-2/I-1, see `ACTION_REQUIRED.md`) and deferred I-6/I-4.

Awaiting direction.
