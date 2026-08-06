# ESF Platform — Copilot Instructions

## Architecture

Layered: Controller → Service → Repository → Database.

- No business logic in controllers
- No SQL outside repositories
- No direct DB access from templates
- No duplicate logic, no TODO/FIXME/HACK in production code

## Document lifecycle

DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED

After publish: document is immutable. PDF and public verification page render from the snapshot, not the live row.

## Stack

FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL. Templates via Jinja2 + WeasyPrint for PDF.

Auth: session cookie (Argon2id) + long-lived API credentials (`esf_` prefix, SHA-256 hashed).
AIOS integration: gated on `AIOS_ENABLED=true` — all paths no-op when disabled.

## Current state

v1.2.4, 211 tests pass. One open TD: TD-022 (AIOS auto-provision, deferred).
Source of truth: `PROJECT_STATE.md`.
