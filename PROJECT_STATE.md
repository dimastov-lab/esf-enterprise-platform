# PROJECT_STATE.md

**Version:** v1.2.6 | **Tests:** 267 pass | **Alembic head:** `e1f1d7a7bf24`

**Status:** Production-ready; ready for external acceptance. Verified 2026-08-08:
267 tests, three healthy production containers, trusted local TLS and 12/12
full production smoke. Public-domain/VPS acceptance remains external.
AIOS convergence complete (Layers 1/2/3 + AUTH-01 + operability + async identity + credential security + auto-provision).

**Open work:**
- I-1: Real domain + TLS cert (owner action, see ACTION_REQUIRED.md)
- Secrets: `~/.config/esf/.env.production` (mode 600); update `PUBLIC_BASE_URL` before public deploy
- External acceptance: tooling and evidence ready; public deployment and named
  independent acceptor pending (`docs/EXTERNAL_ACCEPTANCE.md`).

**Dev:** `docker compose up -d` → admin/admin123. Out of scope: ГНС, ЭЦП, legal validity.

> Per-version history: see CHANGELOG.md and `git log`.

Awaiting direction.
