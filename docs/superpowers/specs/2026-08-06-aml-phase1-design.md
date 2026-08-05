# AML Phase 1 — Design Spec

**Date:** 2026-08-06  
**Status:** Approved

---

## Goal

Build a standalone Anti-Money Laundering (AML) service that receives alerts from external systems, allows analysts to triage them, group them into cases, and record decisions. Customer data is read from Golden Record — AML never stores its own customer copy.

## Architecture

```
Controller → Service → Repository → Database
           ↑
        GR Port (Protocol + InMemoryGRAdapter stub)
```

Same stack as Golden Record: FastAPI / psycopg3 / AsyncConnectionPool / SQLAlchemy Core / Alembic / Pydantic v2. Standalone repo at `~/Projects/aml/`. Port 8200 (service), 5435 (PostgreSQL).

## Scope

Phase 1 includes:
- Alert management (external push → triage → close)
- Case management (group alerts → investigate → decision)
- GR Port stub (InMemoryGRAdapter — real HTTP client deferred to Phase 2)
- Single Bearer-token auth, single tenant from env

Not in Phase 1: transaction monitoring engine, regulatory reporting, SAR filing workflow, KYC/EDD, real GR HTTP client, user/role tables.

---

## Domain

### Alert

State machine:
```
OPEN → IN_REVIEW → CLOSED
```
Transitions are forward-only. `OPEN→IN_REVIEW`, `IN_REVIEW→CLOSED` are the only valid moves.

Fields:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `tenant_id` | UUID | from env |
| `gr_customer_id` | UUID | reference into Golden Record |
| `customer_snapshot` | JSONB | name/type/tax_number — snapshotted at creation |
| `alert_type` | str | e.g. "LARGE_CASH_TRANSACTION" |
| `description` | str | |
| `severity` | enum | LOW / MEDIUM / HIGH / CRITICAL |
| `status` | enum | OPEN / IN_REVIEW / CLOSED |
| `source_system` | str | name of originating system |
| `source_ref` | str | external alert ID |
| `created_at` | datetime | UTC |
| `updated_at` | datetime | UTC |

### Case

State machine:
```
OPEN → UNDER_INVESTIGATION → CLOSED  (outcome required at close)
```

Fields:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `tenant_id` | UUID | from env |
| `title` | str | |
| `description` | str | |
| `status` | enum | OPEN / UNDER_INVESTIGATION / CLOSED |
| `outcome` | enum \| null | CLEARED / ESCALATED / SAR_FILED — required when CLOSED |
| `assigned_to` | str \| null | analyst name string (no user table in Phase 1) |
| `created_at` | datetime | UTC |
| `updated_at` | datetime | UTC |
| `closed_at` | datetime \| null | set when CLOSED |

### case_alerts (link table)

| Field | Type |
|---|---|
| `case_id` | UUID FK → cases |
| `alert_id` | UUID FK → alerts |
| `added_at` | datetime UTC |

PK: `(case_id, alert_id)`.

### Domain invariants

- `Case.close(outcome)` without outcome → `InvalidTransitionError`
- Adding an alert to a CLOSED case → `CaseClosedError`
- Duplicate `(case_id, alert_id)` → `AlertAlreadyInCaseError`
- Alert status is independent of case membership

---

## GR Port

```python
@runtime_checkable
class GRPort(Protocol):
    async def get_customer_snapshot(
        self, tenant_id: UUID, customer_id: UUID
    ) -> CustomerSnapshot | None: ...

@dataclass(frozen=True, slots=True)
class CustomerSnapshot:
    customer_id: UUID
    full_name: str
    customer_type: str   # "INDIVIDUAL" | "LEGAL_ENTITY"
    tax_number: str | None
```

`InMemoryGRAdapter` takes `dict[UUID, CustomerSnapshot]` in constructor. Returns `None` for unknown IDs. Alert creation with unknown `gr_customer_id` → 404.

---

## File Structure

```
~/Projects/aml/
├── pyproject.toml
├── alembic.ini
├── src/aml/
│   ├── domain/
│   │   ├── alert.py          # AlertStatus, AlertSeverity, Alert
│   │   ├── case.py           # CaseStatus, CaseOutcome, Case
│   │   └── exceptions.py     # domain exceptions
│   ├── ports/
│   │   ├── alert_repository.py   # AlertRepository Protocol (async def)
│   │   ├── case_repository.py    # CaseRepository Protocol (async def)
│   │   └── gr_port.py            # GRPort Protocol + CustomerSnapshot
│   ├── adapters/
│   │   ├── gr_stub.py            # InMemoryGRAdapter
│   │   └── pg/
│   │       ├── alert_repository.py
│   │       └── case_repository.py
│   ├── service/
│   │   ├── alert_service.py      # create_alert, transition_alert, get_alert, list_alerts
│   │   └── case_service.py       # create_case, add_alert_to_case, remove_alert_from_case,
│   │                             #   transition_case, close_case, get_case, list_cases
│   ├── api/
│   │   ├── app.py                # create_app(settings, gr, alert_repo, case_repo)
│   │   ├── alerts.py             # /v1/alerts router
│   │   └── cases.py              # /v1/cases router
│   ├── db/
│   │   ├── schema.py             # SQLAlchemy Core metadata (alerts, cases, case_alerts)
│   │   └── migrations/           # Alembic env.py + 0001_initial.py
│   ├── config.py                 # Settings: database_url, bearer_token, tenant_id, host, port
│   └── __main__.py               # asyncio.run(_serve()) with AsyncConnectionPool
└── tests/
    ├── unit/
    │   ├── test_alert_service.py
    │   ├── test_case_service.py
    │   ├── test_api_alerts.py
    │   └── test_api_cases.py
    └── integration/
        ├── conftest.py           # function-scoped pool + DELETE cleanup per tenant_id
        ├── test_pg_alert_repo.py
        ├── test_pg_case_repo.py
        └── test_journey.py       # full flow: alert → case → link → close
```

---

## API Surface

**Auth:** `Authorization: Bearer <token>`. Token from `AML_BEARER_TOKEN` env. Checked via `hmac.compare_digest`.

**Tenant:** `AML_TENANT_ID` from env (UUID).

### Alerts

```
POST   /v1/alerts
  Body: {gr_customer_id, alert_type, description, severity, source_system, source_ref}
  → 201 AlertResponse (includes customer_snapshot)

GET    /v1/alerts/{id}
  → 200 AlertResponse | 404

GET    /v1/alerts?status=&severity=&gr_customer_id=&limit=20
  → 200 {items: [AlertResponse], total: int}

PATCH  /v1/alerts/{id}/status
  Body: {status: "IN_REVIEW" | "CLOSED"}
  → 200 AlertResponse | 404 | 409 (invalid transition)
```

### Cases

```
POST   /v1/cases
  Body: {title, description, assigned_to?}
  → 201 CaseResponse

GET    /v1/cases/{id}
  → 200 CaseResponse (includes alerts: [AlertSummary]) | 404

GET    /v1/cases?status=&outcome=&limit=20
  → 200 {items: [CaseResponse], total: int}

POST   /v1/cases/{id}/alerts/{alert_id}
  → 200 CaseResponse | 404 | 409 (already linked | case closed)

DELETE /v1/cases/{id}/alerts/{alert_id}
  → 204 | 404

POST   /v1/cases/{id}/transition
  Body: {status: "UNDER_INVESTIGATION"}
  → 200 CaseResponse | 404 | 409

POST   /v1/cases/{id}/close
  Body: {outcome: "CLEARED" | "ESCALATED" | "SAR_FILED"}
  → 200 CaseResponse | 404 | 409
```

---

## Error Handling

RFC 7807 for all errors. Handler map:

| Exception | HTTP |
|---|---|
| `AlertNotFoundError` | 404 |
| `CaseNotFoundError` | 404 |
| `GRCustomerNotFoundError` | 404 |
| `InvalidTransitionError` | 409 |
| `AlertAlreadyInCaseError` | 409 |
| `CaseClosedError` | 409 |
| Pydantic `RequestValidationError` | 422 |

---

## Testing Strategy

**Unit tests** — in-memory stubs, no DB:
- `test_alert_service.py`: create alert enriches snapshot; invalid transitions raise; unknown gr_customer_id raises
- `test_case_service.py`: add_alert, remove_alert, close with outcome, close without outcome raises, add to CLOSED raises
- `test_api_alerts.py`: endpoint smoke with stub repo (TestClient / ASGITransport)
- `test_api_cases.py`: endpoint smoke with stub repo

**Integration tests** — real PostgreSQL at 5435:
- `test_pg_alert_repo.py`: insert/get/list/transition; multi-tenant isolation
- `test_pg_case_repo.py`: CRUD; case_alerts link/unlink; get_case returns embedded alerts
- `test_journey.py`: full analyst flow end-to-end

**Journey scenario:**
1. `POST /v1/alerts` → 201 (gr_customer_id from stub)
2. `POST /v1/cases` → 201
3. `POST /v1/cases/{id}/alerts/{alert_id}` → 200 (case now has alert)
4. `POST /v1/cases/{id}/transition` `{status: "UNDER_INVESTIGATION"}` → 200
5. `PATCH /v1/alerts/{id}/status` `{status: "IN_REVIEW"}` → 200
6. `POST /v1/cases/{id}/close` `{outcome: "CLEARED"}` → 200 (closed_at set)
7. `POST /v1/cases/{id}/alerts/{alert_id2}` → 409 (case is CLOSED)

**Test isolation:** function-scoped `AsyncConnectionPool`, unique `uuid4()` `tenant_id` per test, autouse `DELETE` cleanup — same pattern as Golden Record.

---

## Deferred to Phase 2

- Real `HttpGRAdapter` (HTTP client to GR at port 8100)
- Analyst auth / user table (currently `assigned_to` is a free string)
- `source_ref` uniqueness constraint per tenant (prevent duplicate alert ingestion)
- Pagination cursor (Phase 1 uses `LIMIT`, no cursor)
- Dockerfile + `make dev`
- Cross-tenant isolation test, wrong-token rejection test

---

## Ports & Environment

| Var | Default | Notes |
|---|---|---|
| `AML_DATABASE_URL` | `postgresql+psycopg://aml:aml@localhost:5435/aml` | |
| `AML_BEARER_TOKEN` | `dev-token` | rotate in prod |
| `AML_TENANT_ID` | (required) | UUID |
| `AML_HOST` | `0.0.0.0` | |
| `AML_PORT` | `8200` | |
