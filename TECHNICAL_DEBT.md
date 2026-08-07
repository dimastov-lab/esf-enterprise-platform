# TECHNICAL_DEBT.md

> Resolved items (TD-001–TD-022, TD-023–TD-027) are in git history.

## Active

| ID | Severity | Module | Description | Risk | Fix Plan | Status |
|----|----------|--------|-------------|------|----------|--------|
| CSS-01 | Low | frontend/CSP | `style-src 'unsafe-inline'` in CSP — left intentionally because WeasyPrint and Jinja2 inline styles are too numerous to nonce at this stage. | Minimal: `style-src` injection is much lower risk than `script-src`. | Revisit when moving to a CSS-in-JS renderer or replacing WeasyPrint. | Accepted risk |

## Rule

Every technical debt item must include: ID, Severity, Module, Description, Risk, Fix Plan, Status.
