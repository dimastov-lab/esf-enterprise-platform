# ROADMAP.md

> Completed items (sprints 1–30, v1.0–v1.2.4): see `git log` and CHANGELOG.md.

## Remaining code-side work (v1.3 horizon, low priority)

- **ESF-AUTH01-001** (Low) — `--expires-in-days` flag for `esf_` credential issue CLI
- **ESF-TD022-001** (Low) — `AIOS_AUTO_PROVISION=true`; deferred until multi-tenant scope defined

## Blocked on owner action

- **ESF-I1-001** (Critical) — Production deploy: real domain + TLS cert.
  `docker-compose.prod.yml` and `.env.production.example` are ready.
  See `ACTION_REQUIRED.md` (I-1, I-2).

## Ecosystem position

ESF is the reference implementation of AIOS domain convergence:
- Layer 1 (Tasks): AIOS task lifecycle on ESF state transitions
- Layer 2 (Identity): async AIOS JWT validation with graceful fallback
- Layer 3 (Memories): snapshots written to AIOS Memories post-commit

All domain modules (AML, Golden Record, AICOS) target the same convergence pattern.

Out of scope: ГНС/tax-authority integration, ЭЦП/digital signature, legal validity.
