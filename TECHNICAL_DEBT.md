# TECHNICAL_DEBT.md

> Resolved items (TD-001–TD-021, TD-023–TD-027) are in git history.

## Active

### TD-022 — AIOS Layer 2: auto-provision AIOS users in ESF

- **ID:** TD-022
- **Severity:** Low
- **Module:** `backend/app/core/security.py`
- **Description:** `get_current_api_user` validates AIOS identity but only maps to *existing* ESF users. Unknown AIOS users get 401 even though AIOS confirms their identity.
- **Risk:** Minor — risk increases when ESF is opened to external AIOS tenants.
- **Fix Plan:** Opt-in `AIOS_AUTO_PROVISION=true` that creates a minimal `User` row on first successful AIOS identity verification. Requires migration for `User.external_id`.
- **Status:** Open. Deferred until multi-tenant scope is defined.

## Rule

Every technical debt item must include: ID, Severity, Module, Description, Risk, Fix Plan, Status.
