# PROJECT_STATE.md

**Version:** v1.2.4 | **Tests:** 211 pass | **Alembic head:** `a2b3c4d5e6f7`

**Status:** Production-ready. Locally verified 2026-08-06 (self-signed cert, 3 containers healthy).
AIOS convergence complete (Layers 1/2/3 + AUTH-01 + operability + async identity + credential security).

**Open work:**
- TD-022: AIOS auto-provision (Low, deferred — see TECHNICAL_DEBT.md)
- ESF-AUTH01-001: `--expires-in-days` CLI flag (Low, `feat/credential-expiry`)
- I-1: Real domain + TLS cert (owner action, see ACTION_REQUIRED.md)
- Secrets: `~/.config/esf/.env.production` (mode 600); update `PUBLIC_BASE_URL` before public deploy

**Dev:** `docker compose up -d` → admin/admin123. Out of scope: ГНС, ЭЦП, legal validity.

> Per-version history: see CHANGELOG.md and `git log`.

Awaiting direction.
