# PROJECT_STATE.md

**Version:** v1.2.6 | **Tests:** 221 pass | **Alembic head:** `e1f1d7a7bf24`

**Status:** Production-ready. Locally verified 2026-08-07 (self-signed cert, 3 containers healthy).
AIOS convergence complete (Layers 1/2/3 + AUTH-01 + operability + async identity + credential security + auto-provision).

**Open work:**
- I-1: Real domain + TLS cert (owner action, see ACTION_REQUIRED.md)
- Secrets: `~/.config/esf/.env.production` (mode 600); update `PUBLIC_BASE_URL` before public deploy

**Dev:** `docker compose up -d` → admin/admin123. Out of scope: ГНС, ЭЦП, legal validity.

> Per-version history: see CHANGELOG.md and `git log`.

Awaiting direction.
