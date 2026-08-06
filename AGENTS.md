# ESF Enterprise Platform

## Architecture

Layered: Controller → Service → Repository → Database.

- No business logic in controllers
- No SQL outside repositories
- No direct DB access from templates
- No duplicate logic, no TODO/FIXME/HACK

## Document lifecycle

DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED

After publish: immutable. PDF and public verification render from snapshot, not live row.
Audit must record all critical actions.

## Stack

FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + Jinja2. WeasyPrint for PDF.
Auth: Argon2id session + `esf_` API credentials (SHA-256 hashed).
AIOS: gated on `AIOS_ENABLED=true`, all paths no-op when disabled.

## Current state

v1.2.4, 211 tests, one open item: TD-022 (AIOS auto-provision, deferred).
Source of truth: PROJECT_STATE.md and TECHNICAL_DEBT.md.
