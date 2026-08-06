# CHANGELOG.md

> Versions v0.0.1–v1.2.1: see `git log` or `git log --oneline`.

## v1.2.4 — Async AIOS identity + credential rate-limiting + row-lock fix + AIOS rejection (2026-08-06)

Closes TD-024, TD-025, TD-026.

- **Async identity verify**: `get_current_api_user` → `async def`; `httpx.AsyncClient` 2 s timeout (was sync 5 s in Starlette threadpool).
- **`throttle_api()`**: 20 req / 60 s / IP on `POST/GET/DELETE /auth/credentials` (shared Postgres store).
- **TD-026**: `memory_create()` moved after `repo.commit()` — row lock released before AIOS call. ORM + DB trigger narrowed to payload fields; `aios_memory_id` written in post-commit UPDATE.
- **TD-025**: `AIOSTokenRejectedError` — AIOS 4xx → HTTP 401 immediately, no ESF JWT fallback. 5xx/network → graceful degradation preserved.
- `config.VERSION` → `"1.2.4"`. Suite: **211 tests pass**.

## ESF-RUNTIME-001 — Production deploy prep (2026-08-06)

- `docker-compose.prod.yml`: image tag → `1.2.3`; AIOS optional env block added.
- `.env.production.example`: AIOS section added.

## v1.2.3 — Credential security + SDK adoption (2026-08-06)

Closes TD-021, TD-023, TD-027.

- **TD-023**: `validate_for_runtime()` rejects `http://` AIOS_BASE_URL in production.
- **TD-027**: `MAX_TTL_DAYS=90`; `CREDENTIAL_ISSUED`/`CREDENTIAL_REVOKED` audit actions; `POST /admin/users/{id}/deactivate` revokes all credentials + audit + admin guard.
- **TD-021**: `AIOSBridgeService` → `aios_sdk.AIOSClient`; Python 3.11 → 3.12.
- Suite: **195 tests pass**.
