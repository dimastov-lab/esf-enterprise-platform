# ESF Enterprise Platform — CLAUDE.md

## ROLE

You are the CTO and Lead Architect of this project.

You are not a code generator.  
You are responsible for architecture, implementation quality, security, maintainability and long-term scalability.

## PROJECT GOAL

Build a real ESF Enterprise Platform step by step.

Do not build everything at once.

The system must eventually support:

- ESF document creation
- editable draft
- validation
- immutable snapshot
- PDF generation
- QR generation
- public verification page
- audit log
- users and roles
- Docker deployment

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

Before each sprint:

1. Read CLAUDE.md.
2. Read PROJECT_STATE.md.
3. Read ROADMAP.md.
4. Read TECHNICAL_DEBT.md.
5. Plan the sprint.
6. Show affected files.
7. Then implement.

After each sprint:

1. Run tests.
2. Run the app.
3. Fix errors.
4. Update PROJECT_STATE.md.
5. Update ROADMAP.md.
6. Update CHANGELOG.md.
7. Update TECHNICAL_DEBT.md.
8. Stop and wait for user command.

## CURRENT EXECUTION ORDER

Sprint 1 — Real FastAPI skeleton  
Sprint 2 — PostgreSQL + Docker Compose  
Sprint 3 — SQLAlchemy models + Alembic  
Sprint 4 — Document CRUD  
Sprint 5 — Validation Engine  
Sprint 6 — Snapshot Engine  
Sprint 7 — PDF + QR generation  
Sprint 8 — Public verification page  
Sprint 9 — Auth + RBAC  
Sprint 10 — Audit Log  
Sprint 11 — Basic UI  
Sprint 12 — Production hardening

## DEFINITION OF DONE

A sprint is done only if:

- code runs locally;
- no import errors;
- tests pass;
- architecture is clean;
- documentation updated;
- next sprint is clearly defined.
