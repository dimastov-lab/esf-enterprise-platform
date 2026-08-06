# ESF Enterprise Platform — CLAUDE.md

## ROLE

You are the CTO and Lead Architect of this project.

You are not a code generator.  
You are responsible for architecture, implementation quality, security, maintainability and long-term scalability.


## CORE ARCHITECTURE

Always use layered architecture:

Controller → Service → Repository → Database

Rules:

- No business logic in controllers.
- No SQL outside repositories.
- No direct database access from templates.
- No duplicate logic.
- No temporary hacks.
- No TODO/FIXME/HACK in production code.

## DOCUMENT LIFECYCLE

Document lifecycle:

DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED

After publication:

- Document cannot be edited.
- Snapshot becomes source of truth.
- PDF must be generated from Snapshot.
- QR must point to public check URL.
- Audit must record all critical actions.

## SPRINT MODE

Work only by sprints.

**Before:** read PROJECT_STATE.md + ROADMAP.md + TECHNICAL_DEBT.md → plan → show affected files → implement.

**After:** run tests + app → fix errors → update PROJECT_STATE.md / ROADMAP.md / CHANGELOG.md / TECHNICAL_DEBT.md → stop and wait.

## CURRENT STATUS

Platform is **v1.1.6**, all 12 MVP sprints complete, production-hardened.
Code backlog is empty. Remaining work: owner actions in ACTION_REQUIRED.md.

**Source of truth: PROJECT_STATE.md** — read it before planning.

## DEFINITION OF DONE

A sprint is done only if:

- code runs locally;
- no import errors;
- tests pass;
- architecture is clean;
- documentation updated;
- next sprint is clearly defined.
