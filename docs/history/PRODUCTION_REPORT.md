# PRODUCTION_REPORT.md — ESF Enterprise Platform

**Release:** 1.0 RC1 · **Scope of this report:** production infrastructure, documentation, and
deployment tooling (no business-logic / architecture / feature changes).

## Readiness scores (0–10)

| Area | Score | Basis |
|---|---:|---|
| Deployment readiness | 9 | One-command Compose stack (db + app + nginx); image builds deterministically; migrations auto-run on start; INSTALL/DEPLOY guides; `prod_smoke_test.sh`. |
| Security readiness | 7.5 | TLS-fronted; Secure+HttpOnly+SameSite session cookie; bcrypt; CSRF on all POSTs; owner/RBAC isolation; **fail-closed SECRET_KEY**; non-root container; immutable snapshots; audit log. Gaps: in-process rate limit, no WAF, env-file secrets. |
| Operational readiness | 8 | OPERATIONS.md runbooks (login, users, password reset, disable, logs, restart, health, troubleshooting); admin audit viewer. Gap: no centralized logging/metrics. |
| Backup readiness | 8 | pg_dump/restore + full recovery procedure; snapshots included in dump; QR volume backup; PDFs regenerate. Gap: restore drills not automated. |
| Monitoring readiness | 5 | Docker healthchecks on all three services + smoke test + business audit log. Gap: no metrics/alerting/log aggregation. |
| **Overall** | **7.5** | **Production-ready for a controlled launch behind HTTPS, with the documented hardening backlog.** |

## Deployment readiness
- `docker-compose.prod.yml`: PostgreSQL 15 + app (built from `backend/Dockerfile`) + nginx;
  named volumes (`pg_data`, `esf_storage`); `restart: unless-stopped`; healthchecks on all
  services; env-driven; json-file logging with rotation; `TZ` support.
- App image: slim (`python:3.11-slim`), no reload/debug, deterministic pinned deps, non-root
  user, entrypoint applies migrations then serves uvicorn (workers via `WEB_CONCURRENCY`).
- `scripts/prod_smoke_test.sh` validates: app start, DB, migration at head, /login 200,
  authenticated dashboard, public verification, PDF, QR, and absence of critical log errors.

## Security readiness
- HTTPS required (nginx TLS; HTTP→HTTPS redirect; HSTS + X-Content-Type-Options + X-Frame-Options
  + Referrer-Policy). Session cookies are `Secure` in production (TLS mandatory).
- App refuses to boot in production with a default/empty `SECRET_KEY`.
- bcrypt passwords; RBAC (ADMIN/ISSUER) + owner isolation (403); CSRF tokens; login rate limit;
  public routes read-only and PUBLISHED-only; snapshots ORM-immutable.
- Container runs as non-root; DB and app are not published to the host (only nginx 80/443).

## Operational & backup readiness
- Runbooks for all routine tasks (OPERATIONS.md); audit trail for login/publish/delete/view/PDF.
- Backups: nightly `pg_dump` (cron example), documented restore + full disaster recovery; QR
  volume archive; PDFs are derived (no backup needed).

## Monitoring readiness
- Present: per-service Docker healthchecks, `/healthz` (nginx) and `/` (app) probes, smoke test,
  in-app audit log.
- Missing (recommended before scale): metrics (Prometheus), centralized logs (Loki/ELK),
  alerting, uptime checks.

## Remaining risks
1. **No GNS integration / no ЭЦП** → issued documents are not legally valid (product scope, not infra).
2. **Rate limiting is per-process** — with multiple workers, limits multiply; add a shared store
   (Redis) or WAF for strict protection.
3. **No centralized logging/metrics/alerting** — operational blind spots at scale.
4. **TLS lifecycle is manual** (certbot copy + `restart nginx`); automate renewal.
5. **Single host** — DB co-located with app; no HA/replication; back up off-host.
6. **Secrets in `.env.production`** — acceptable for a single host; use a secret manager for higher assurance.

## Verdict
Infrastructure, documentation, and tooling are complete and self-contained: a new engineer can
deploy from INSTALL.md on a clean Linux server without assistance. **Production-ready for a
controlled launch behind HTTPS**; address the monitoring and rate-limit items as fast-follow.
