# AML Governance Platform — DATA-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new standalone FastAPI application at `~/Desktop/AML-Governance-Platform/` that lets bank analysts close TM alerts with machine-readable outcome codes (D1/D2), enforces all business invariants, and produces a rule × month × outcome report.

**Architecture:** Three strict layers — Router → Service → Repository → DB. No SQL outside repositories. No business logic in routers. All domain exceptions raised in services, translated to HTTP in routers.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL 16, Jinja2, Docker Compose, pytest.

## Global Constraints

- Root of new repo: `/Users/dmitrijcernikov/Desktop/AML-Governance-Platform/`
- App runs at `http://localhost:8001` (port 8001 to avoid conflict with ESF on 8000)
- PostgreSQL exposed on host port 5433
- D1 (`OutcomeCode`) and D2 (`OutcomeReasonCode`) are Python Enums stored as VARCHAR in DB — never separate tables
- `CLOSED_FP` always requires `outcome_reason_code` — enforced in `DispositionService`, not in DB
- `DUPLICATE` always requires `parent_alert_id` — same enforcement
- Alembic migrations run automatically on container start (`alembic upgrade head` in entrypoint)
- All tests use a separate in-memory SQLite DB (`sqlite:///./test.db`) via `conftest.py` override
- No JavaScript frameworks — pure Jinja2 + HTML forms

---

## File Map

```
AML-Governance-Platform/
  backend/
    app/
      __init__.py
      main.py                        ← FastAPI app, lifespan, routers mount
      core/
        __init__.py
        config.py                    ← Settings (DATABASE_URL, SECRET_KEY, env)
        security.py                  ← session auth, get_current_user, require_role
        exceptions.py                ← AlertAlreadyClosedError, InvalidDispositionError
      db/
        __init__.py
        session.py                   ← get_db() dependency, engine
        base.py                      ← declarative Base
      models/
        __init__.py
        enums.py                     ← OutcomeCode, OutcomeReasonCode, OutcomeSource, QAResult, AlertStatus, UserRole
        alert.py                     ← Alert ORM model
        disposition.py               ← AlertDisposition ORM model
        rule.py                      ← Rule ORM model
        user.py                      ← User ORM model
      repositories/
        __init__.py
        alert_repo.py                ← get_by_id, get_by_external_id, list_open, create, update_status
        disposition_repo.py          ← create, get_by_alert_id
        report_repo.py               ← rule_month_matrix(rule_id, from_ym, to_ym)
      services/
        __init__.py
        disposition_service.py       ← close_alert(alert_id, analyst_id, req, db)
        alert_service.py             ← import_from_csv(file_content, db) → ImportResult
        report_service.py            ← rule_month_matrix(...) → list[dict], to_csv(rows) → str
      routers/
        __init__.py
        auth.py                      ← GET/POST /login, POST /logout
        alerts.py                    ← GET /alerts, GET /alerts/{id}, POST /alerts/{id}/close, POST /alerts/import
        reports.py                   ← GET /reports/matrix
      templates/
        base.html
        auth/login.html
        alerts/list.html
        alerts/detail.html
        alerts/close.html
        alerts/import.html
        reports/matrix.html
    Dockerfile
    requirements.txt
  alembic/
    versions/
    env.py
    script.py.mako
  alembic.ini
  tests/
    conftest.py                      ← TestClient + SQLite test DB + seed data
    unit/
      test_disposition_service.py
      test_alert_service.py
      test_report_service.py
    integration/
      test_alerts_flow.py            ← import → list → close → report end-to-end
  docker-compose.yml
  .env.example
  .gitignore
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/base.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `tests/conftest.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `get_db()` dependency (used by all repositories), `Settings` singleton, FastAPI `app` object

- [ ] **Step 1: Init git repo and create directory tree**

```bash
cd ~/Desktop
mkdir -p AML-Governance-Platform/backend/app/{core,db,models,repositories,services,routers,templates/{auth,alerts,reports}}
mkdir -p AML-Governance-Platform/{alembic/versions,tests/{unit,integration}}
cd AML-Governance-Platform
git init
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
*.db
.pytest_cache/
pgdata/
```

- [ ] **Step 3: Create `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg2-binary==2.9.10
python-multipart==0.0.17
jinja2==3.1.4
itsdangerous==2.2.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.1
pytest==8.3.3
httpx==0.27.2
```

- [ ] **Step 4: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY ../alembic/ ./alembic/
COPY ../alembic.ini ./
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 5: Create `docker-compose.yml`**

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: aml_platform
      POSTGRES_USER: aml
      POSTGRES_PASSWORD: aml_secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aml"]
      interval: 5s
      retries: 5
  app:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://aml:aml_secret@db:5432/aml_platform
      SECRET_KEY: dev_secret_change_in_prod_32chars__
    ports:
      - "8001:8000"
    depends_on:
      db:
        condition: service_healthy
volumes:
  pgdata:
```

- [ ] **Step 6: Create `.env.example`**

```
DATABASE_URL=postgresql://aml:aml_secret@localhost:5433/aml_platform
SECRET_KEY=dev_secret_change_in_prod_32chars__
```

- [ ] **Step 7: Create `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://aml:aml_secret@localhost:5433/aml_platform"
    secret_key: str = "dev_secret_change_in_prod_32chars__"

    class Config:
        env_file = ".env"

settings = Settings()
```

Add `pydantic-settings==2.5.2` to `requirements.txt`.

- [ ] **Step 8: Create `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

- [ ] **Step 9: Create `backend/app/db/session.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 10: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import pathlib

app = FastAPI(title="AML Governance Platform")

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 11: Create `alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://aml:aml_secret@localhost:5433/aml_platform
```

- [ ] **Step 12: Create `alembic/env.py`**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.db.base import Base
from app.core.config import settings
import app.models  # noqa: F401 — import all models so Base.metadata is populated

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 13: Create `backend/app/models/__init__.py`** (imports all models so Alembic sees them)

```python
from app.models.alert import Alert          # noqa
from app.models.disposition import AlertDisposition  # noqa
from app.models.rule import Rule            # noqa
from app.models.user import User            # noqa
```

- [ ] **Step 14: Create `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 15: Write health check test**

Create `tests/test_health.py`:
```python
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 16: Run test to verify it fails (app not wired yet)**

```bash
cd ~/Desktop/AML-Governance-Platform/backend
pip install -r requirements.txt
cd ..
PYTHONPATH=backend pytest tests/test_health.py -v
```
Expected: PASS (health endpoint exists already).

- [ ] **Step 17: Commit**

```bash
git add .
git commit -m "feat: project scaffold — FastAPI app, Docker, Alembic, health endpoint"
```

---

## Task 2: Models + Enums + Migration

**Files:**
- Create: `backend/app/models/enums.py`
- Create: `backend/app/models/alert.py`
- Create: `backend/app/models/disposition.py`
- Create: `backend/app/models/rule.py`
- Create: `backend/app/models/user.py`
- Create: `alembic/versions/001_initial_schema.py`
- Test: `tests/unit/test_models.py`

**Interfaces:**
- Produces: `Alert`, `AlertDisposition`, `Rule`, `User`, `OutcomeCode`, `OutcomeReasonCode`, `OutcomeSource`, `QAResult`, `AlertStatus`, `UserRole` — used by all repositories and services

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_models.py`:
```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from app.models.alert import Alert
from app.models.enums import AlertStatus, OutcomeCode, OutcomeReasonCode, OutcomeSource, UserRole
from app.models.disposition import AlertDisposition
from app.models.rule import Rule
from app.models.user import User

def test_alert_defaults(db):
    rule = Rule(id="7.1", name="Порог расходов ЮЛ", status="ACTIVE", alerts_per_year=4710)
    db.add(rule)
    alert = Alert(
        id=uuid.uuid4(),
        external_id="EXT-001",
        rule_id="7.1",
        client_id="CLIENT-1",
        amount=Decimal("500000"),
        alert_dt=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    assert alert.status == AlertStatus.OPEN

def test_disposition_created(db):
    rule = Rule(id="7.1", name="Порог расходов ЮЛ", status="ACTIVE", alerts_per_year=4710)
    db.add(rule)
    user = User(id=uuid.uuid4(), username="analyst1", hashed_password="x", role=UserRole.ANALYST)
    db.add(user)
    alert = Alert(id=uuid.uuid4(), external_id="EXT-002", rule_id="7.1", client_id="C-2",
                  amount=Decimal("100000"), alert_dt=datetime.now(timezone.utc))
    db.add(alert)
    db.flush()
    disp = AlertDisposition(
        id=uuid.uuid4(),
        alert_id=alert.id,
        rule_id="7.1",
        outcome_code=OutcomeCode.CLOSED_NO_RISK,
        outcome_dt=datetime.now(timezone.utc),
        analyst_id=user.id,
        escalated_flag=False,
        sar_flag=False,
        outcome_source=OutcomeSource.LIVE,
    )
    db.add(disp)
    db.commit()
    db.refresh(disp)
    assert disp.outcome_code == OutcomeCode.CLOSED_NO_RISK
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=backend pytest tests/unit/test_models.py -v
```
Expected: FAIL — `app.models.enums` not found.

- [ ] **Step 3: Create `backend/app/models/enums.py`**

```python
import enum

class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class UserRole(str, enum.Enum):
    ANALYST = "analyst"
    MLRO = "mlro"
    ADMIN = "admin"

class OutcomeCode(str, enum.Enum):
    PENDING = "PENDING"
    CLOSED_FP = "CLOSED_FP"
    CLOSED_NO_RISK = "CLOSED_NO_RISK"
    ESCALATED_REJECTED = "ESCALATED_REJECTED"
    ESCALATED_CONFIRMED = "ESCALATED_CONFIRMED"
    SAR_FILED = "SAR_FILED"
    DUPLICATE = "DUPLICATE"

class OutcomeReasonCode(str, enum.Enum):
    FP_LEGIT_BUSINESS = "FP_LEGIT_BUSINESS"
    FP_KNOWN_COUNTERPARTY = "FP_KNOWN_COUNTERPARTY"
    FP_THRESHOLD_LOW = "FP_THRESHOLD_LOW"
    FP_SEGMENT_MISMATCH = "FP_SEGMENT_MISMATCH"
    FP_TEXT_MATCH = "FP_TEXT_MATCH"
    FP_DUPLICATE_LOGIC = "FP_DUPLICATE_LOGIC"
    FP_DATA_ERROR = "FP_DATA_ERROR"
    FP_ONE_OFF = "FP_ONE_OFF"

class OutcomeSource(str, enum.Enum):
    LIVE = "LIVE"
    RETRO = "RETRO"

class QAResult(str, enum.Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
```

- [ ] **Step 4: Create `backend/app/models/rule.py`**

```python
from sqlalchemy import Column, String, Integer, Text
from app.db.base import Base

class Rule(Base):
    __tablename__ = "rules"
    id = Column(String, primary_key=True)       # "7.1", "№4", "РС_103"
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")   # ACTIVE / RETIRED
    alerts_per_year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
```

- [ ] **Step 5: Create `backend/app/models/user.py`**

```python
import uuid
from sqlalchemy import Column, String, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import UserRole

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole, name="userrole"), nullable=False, default=UserRole.ANALYST)
```

- [ ] **Step 6: Create `backend/app/models/alert.py`**

```python
import uuid
from sqlalchemy import Column, String, Numeric, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import AlertStatus

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, unique=True, nullable=False, index=True)
    rule_id = Column(String, ForeignKey("rules.id"), nullable=False)
    client_id = Column(String, nullable=False)
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    alert_dt = Column(DateTime(timezone=True), nullable=False)
    status = Column(SAEnum(AlertStatus, name="alertstatus"), nullable=False, default=AlertStatus.OPEN)
    raw_payload = Column(JSON, nullable=True)
```

- [ ] **Step 7: Create `backend/app/models/disposition.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import OutcomeCode, OutcomeReasonCode, OutcomeSource, QAResult

class AlertDisposition(Base):
    __tablename__ = "alert_dispositions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False, unique=True)
    rule_id = Column(String, nullable=False)
    outcome_code = Column(SAEnum(OutcomeCode, name="outcomecode"), nullable=False)
    outcome_reason_code = Column(SAEnum(OutcomeReasonCode, name="outcomereasoncode"), nullable=True)
    outcome_dt = Column(DateTime(timezone=True), nullable=False)
    analyst_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    escalated_flag = Column(Boolean, nullable=False, default=False)
    escalated_dt = Column(DateTime(timezone=True), nullable=True)
    case_id = Column(String, nullable=True)
    sar_flag = Column(Boolean, nullable=False, default=False)
    sar_dt = Column(Date, nullable=True)
    sar_number = Column(String, nullable=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=True)
    parent_alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    outcome_source = Column(SAEnum(OutcomeSource, name="outcomesource"), nullable=False, default=OutcomeSource.LIVE)
    review_minutes = Column(Integer, nullable=True)
    qa_flag = Column(Boolean, nullable=True)
    qa_result = Column(SAEnum(QAResult, name="qaresult"), nullable=True)
```

- [ ] **Step 8: Run tests to verify pass**

```bash
PYTHONPATH=backend pytest tests/unit/test_models.py -v
```
Expected: PASS (SQLite creates tables from metadata).

- [ ] **Step 9: Generate Alembic migration for PostgreSQL**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
```
This creates `alembic/versions/001_initial_schema.py`. Review it — confirm tables: `rules`, `users`, `alerts`, `alert_dispositions`.

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "feat: models — Alert, AlertDisposition, Rule, User + D1/D2 enums + migration"
```

---

## Task 3: Repositories

**Files:**
- Create: `backend/app/repositories/alert_repo.py`
- Create: `backend/app/repositories/disposition_repo.py`
- Create: `backend/app/repositories/report_repo.py`
- Test: `tests/unit/test_repositories.py`

**Interfaces:**
- Consumes: `Alert`, `AlertDisposition`, `AlertStatus`, `OutcomeCode` from Task 2; `Session` from `db/session.py`
- Produces:
  - `AlertRepo.get_by_id(alert_id: UUID, db: Session) -> Alert | None`
  - `AlertRepo.get_by_external_id(external_id: str, db: Session) -> Alert | None`
  - `AlertRepo.list_open(db: Session, skip: int, limit: int) -> list[Alert]`
  - `AlertRepo.create(alert: Alert, db: Session) -> None`
  - `AlertRepo.update_status(alert_id: UUID, status: AlertStatus, db: Session) -> None`
  - `DispositionRepo.create(disposition: AlertDisposition, db: Session) -> None`
  - `DispositionRepo.get_by_alert_id(alert_id: UUID, db: Session) -> AlertDisposition | None`
  - `ReportRepo.rule_month_matrix(db: Session, rule_id: str | None, from_ym: str | None, to_ym: str | None) -> list[dict]`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_repositories.py`:
```python
import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest

from app.models.alert import Alert
from app.models.disposition import AlertDisposition
from app.models.rule import Rule
from app.models.user import User
from app.models.enums import AlertStatus, OutcomeCode, OutcomeSource, UserRole
from app.repositories.alert_repo import AlertRepo
from app.repositories.disposition_repo import DispositionRepo
from app.repositories.report_repo import ReportRepo

@pytest.fixture
def seeded_db(db):
    rule = Rule(id="7.1", name="Порог расходов", status="ACTIVE", alerts_per_year=4710)
    user = User(id=uuid.uuid4(), username="a1", hashed_password="x", role=UserRole.ANALYST)
    db.add_all([rule, user])
    db.flush()
    return db, rule, user

def test_alert_create_and_get(seeded_db):
    db, rule, _ = seeded_db
    repo = AlertRepo()
    alert = Alert(id=uuid.uuid4(), external_id="EXT-1", rule_id="7.1",
                  client_id="C1", amount=Decimal("1000"), alert_dt=datetime.now(timezone.utc))
    repo.create(alert, db)
    db.commit()
    fetched = repo.get_by_id(alert.id, db)
    assert fetched is not None
    assert fetched.external_id == "EXT-1"

def test_alert_update_status(seeded_db):
    db, _, _ = seeded_db
    repo = AlertRepo()
    alert = Alert(id=uuid.uuid4(), external_id="EXT-2", rule_id="7.1",
                  client_id="C2", amount=Decimal("2000"), alert_dt=datetime.now(timezone.utc))
    repo.create(alert, db)
    repo.update_status(alert.id, AlertStatus.CLOSED, db)
    db.commit()
    fetched = repo.get_by_id(alert.id, db)
    assert fetched.status == AlertStatus.CLOSED

def test_disposition_create_and_get(seeded_db):
    db, _, user = seeded_db
    alert_repo = AlertRepo()
    disp_repo = DispositionRepo()
    alert = Alert(id=uuid.uuid4(), external_id="EXT-3", rule_id="7.1",
                  client_id="C3", amount=Decimal("3000"), alert_dt=datetime.now(timezone.utc))
    alert_repo.create(alert, db)
    db.flush()
    disp = AlertDisposition(
        id=uuid.uuid4(), alert_id=alert.id, rule_id="7.1",
        outcome_code=OutcomeCode.CLOSED_NO_RISK,
        outcome_dt=datetime.now(timezone.utc),
        analyst_id=user.id, escalated_flag=False, sar_flag=False,
        outcome_source=OutcomeSource.LIVE,
    )
    disp_repo.create(disp, db)
    db.commit()
    fetched = disp_repo.get_by_alert_id(alert.id, db)
    assert fetched is not None
    assert fetched.outcome_code == OutcomeCode.CLOSED_NO_RISK

def test_report_matrix(seeded_db):
    db, _, user = seeded_db
    alert_repo = AlertRepo()
    disp_repo = DispositionRepo()
    report_repo = ReportRepo()
    for i in range(3):
        alert = Alert(id=uuid.uuid4(), external_id=f"EXT-R{i}", rule_id="7.1",
                      client_id=f"C{i}", amount=Decimal("1000"), alert_dt=datetime.now(timezone.utc))
        alert_repo.create(alert, db)
        db.flush()
        disp = AlertDisposition(
            id=uuid.uuid4(), alert_id=alert.id, rule_id="7.1",
            outcome_code=OutcomeCode.CLOSED_FP if i == 0 else OutcomeCode.CLOSED_NO_RISK,
            outcome_dt=datetime.now(timezone.utc),
            analyst_id=user.id, escalated_flag=False, sar_flag=False,
            outcome_source=OutcomeSource.LIVE,
        )
        disp_repo.create(disp, db)
    db.commit()
    rows = report_repo.rule_month_matrix(db, rule_id="7.1")
    total = sum(r["count"] for r in rows)
    assert total == 3
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=backend pytest tests/unit/test_repositories.py -v
```
Expected: FAIL — `app.repositories.alert_repo` not found.

- [ ] **Step 3: Create `backend/app/repositories/alert_repo.py`**

```python
from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.enums import AlertStatus

class AlertRepo:
    def get_by_id(self, alert_id: uuid.UUID, db: Session) -> Alert | None:
        return db.query(Alert).filter(Alert.id == alert_id).first()

    def get_by_external_id(self, external_id: str, db: Session) -> Alert | None:
        return db.query(Alert).filter(Alert.external_id == external_id).first()

    def list_open(self, db: Session, skip: int = 0, limit: int = 50) -> list[Alert]:
        return (
            db.query(Alert)
            .filter(Alert.status == AlertStatus.OPEN)
            .order_by(Alert.alert_dt.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all(self, db: Session, skip: int = 0, limit: int = 50) -> list[Alert]:
        return db.query(Alert).order_by(Alert.alert_dt.desc()).offset(skip).limit(limit).all()

    def count_open(self, db: Session) -> int:
        return db.query(Alert).filter(Alert.status == AlertStatus.OPEN).count()

    def create(self, alert: Alert, db: Session) -> None:
        db.add(alert)

    def update_status(self, alert_id: uuid.UUID, status: AlertStatus, db: Session) -> None:
        db.query(Alert).filter(Alert.id == alert_id).update({"status": status})
```

- [ ] **Step 4: Create `backend/app/repositories/disposition_repo.py`**

```python
from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from app.models.disposition import AlertDisposition

class DispositionRepo:
    def create(self, disposition: AlertDisposition, db: Session) -> None:
        db.add(disposition)

    def get_by_alert_id(self, alert_id: uuid.UUID, db: Session) -> AlertDisposition | None:
        return db.query(AlertDisposition).filter(AlertDisposition.alert_id == alert_id).first()
```

- [ ] **Step 5: Create `backend/app/repositories/report_repo.py`**

```python
from __future__ import annotations
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.disposition import AlertDisposition

class ReportRepo:
    def rule_month_matrix(
        self,
        db: Session,
        rule_id: str | None = None,
        from_ym: str | None = None,
        to_ym: str | None = None,
    ) -> list[dict]:
        month_label = func.strftime("%Y-%m", AlertDisposition.outcome_dt)   # SQLite
        # For PostgreSQL use: func.to_char(func.date_trunc("month", AlertDisposition.outcome_dt), "YYYY-MM")
        q = (
            db.query(
                AlertDisposition.rule_id,
                month_label.label("month"),
                AlertDisposition.outcome_code,
                AlertDisposition.outcome_reason_code,
                func.count().label("count"),
            )
            .group_by(
                AlertDisposition.rule_id,
                month_label,
                AlertDisposition.outcome_code,
                AlertDisposition.outcome_reason_code,
            )
            .order_by(AlertDisposition.rule_id, month_label)
        )
        if rule_id:
            q = q.filter(AlertDisposition.rule_id == rule_id)
        rows = q.all()
        return [
            {
                "rule_id": r.rule_id,
                "month": r.month,
                "outcome_code": r.outcome_code,
                "outcome_reason_code": r.outcome_reason_code,
                "count": r.count,
            }
            for r in rows
        ]
```

**Note:** `func.strftime` is SQLite-only. For the PostgreSQL production path, swap to `func.to_char(func.date_trunc("month", AlertDisposition.outcome_dt), "YYYY-MM")`. The test DB uses SQLite; production uses PostgreSQL.

- [ ] **Step 6: Run tests to verify pass**

```bash
PYTHONPATH=backend pytest tests/unit/test_repositories.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "feat: repositories — AlertRepo, DispositionRepo, ReportRepo"
```

---

## Task 4: Auth + RBAC

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/exceptions.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/templates/base.html`
- Create: `backend/app/templates/auth/login.html`
- Modify: `backend/app/main.py` — mount auth router
- Test: `tests/unit/test_auth.py`

**Interfaces:**
- Consumes: `User`, `UserRole` from Task 2; `get_db` from Task 1
- Produces:
  - `get_current_user(request: Request, db: Session) -> User` — raises HTTP 302 to `/login` if not authenticated
  - `require_role(*roles: UserRole)` — dependency factory; raises HTTP 403 if user role not in `roles`
  - `hash_password(password: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `AlertAlreadyClosedError(alert_id)` — from `exceptions.py`
  - `InvalidDispositionError(message: str)` — from `exceptions.py`

- [ ] **Step 1: Create `backend/app/core/exceptions.py`**

```python
import uuid

class AlertAlreadyClosedError(Exception):
    def __init__(self, alert_id: uuid.UUID):
        super().__init__(f"Alert {alert_id} is already closed")
        self.alert_id = alert_id

class InvalidDispositionError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
```

- [ ] **Step 2: Create `backend/app/core/security.py`**

```python
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db.session import get_db
from app.models.user import User
from app.models.enums import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi.responses import RedirectResponse
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user

def require_role(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return dependency
```

- [ ] **Step 3: Create `backend/app/routers/auth.py`**

```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pathlib, uuid

from app.db.session import get_db
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent.parent / "templates"))

@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Неверный логин или пароль"})
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/alerts", status_code=302)

@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 4: Update `backend/app/main.py`** to add session middleware and mount routers

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.routers import auth
import pathlib

app = FastAPI(title="AML Governance Platform")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))

app.include_router(auth.router, tags=["auth"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Create `backend/app/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{% block title %}AML Platform{% endblock %}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; color: #222; }
    nav { background: #1a2535; color: white; padding: 12px 24px; display: flex; gap: 24px; align-items: center; }
    nav a { color: #7ec8cf; text-decoration: none; font-size: 14px; }
    .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #e0e0e0; text-align: left; font-size: 14px; }
    th { background: #f0f0f0; font-weight: 600; }
    .btn { padding: 8px 16px; background: #1a2535; color: white; border: none; cursor: pointer; font-size: 14px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; }
    .badge-open { color: #0a7a0a; font-weight: 600; }
    .badge-closed { color: #888; }
    .alert-msg { padding: 10px; background: #fef3cd; border: 1px solid #f0c040; margin-bottom: 12px; font-size: 14px; }
    .error { color: #b00; }
    label { display: block; margin-top: 10px; font-size: 14px; font-weight: 500; }
    select, input { padding: 6px; font-size: 14px; width: 100%; max-width: 400px; }
  </style>
</head>
<body>
<nav>
  <span style="font-weight:700;font-size:15px;">AML Platform</span>
  <a href="/alerts">Алерты</a>
  <a href="/reports/matrix">Отчёт</a>
  <form method="post" action="/logout" style="margin-left:auto">
    <button type="submit" style="background:none;border:none;color:#7ec8cf;cursor:pointer;font-size:14px;">Выйти</button>
  </form>
</nav>
<div class="container">
{% block content %}{% endblock %}
</div>
</body>
</html>
```

- [ ] **Step 6: Create `backend/app/templates/auth/login.html`**

```html
{% extends "base.html" %}
{% block title %}Вход — AML Platform{% endblock %}
{% block content %}
<div style="max-width:360px;margin:60px auto;background:white;padding:32px;border:1px solid #ddd;">
  <h2 style="margin-top:0">Вход в систему</h2>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" action="/login">
    <label>Логин</label>
    <input name="username" type="text" required autofocus>
    <label>Пароль</label>
    <input name="password" type="password" required>
    <br><br>
    <button class="btn" type="submit">Войти</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 7: Write auth test**

Create `tests/unit/test_auth.py`:
```python
import uuid
from app.core.security import hash_password, verify_password

def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)

def test_login_redirect(client, db):
    from app.models.user import User
    from app.models.enums import UserRole
    from app.core.security import hash_password
    user = User(id=uuid.uuid4(), username="admin", hashed_password=hash_password("pass"), role=UserRole.ADMIN)
    db.add(user)
    db.commit()
    resp = client.post("/login", data={"username": "admin", "password": "pass"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/alerts"

def test_login_bad_password(client, db):
    from app.models.user import User
    from app.models.enums import UserRole
    from app.core.security import hash_password
    user = User(id=uuid.uuid4(), username="admin2", hashed_password=hash_password("pass"), role=UserRole.ADMIN)
    db.add(user)
    db.commit()
    resp = client.post("/login", data={"username": "admin2", "password": "wrong"})
    assert resp.status_code == 200
    assert "Неверный" in resp.text
```

- [ ] **Step 8: Run tests**

```bash
PYTHONPATH=backend pytest tests/unit/test_auth.py -v
```
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "feat: auth — session login/logout, RBAC, password hashing"
```

---

## Task 5: DispositionService

**Files:**
- Create: `backend/app/services/disposition_service.py`
- Test: `tests/unit/test_disposition_service.py`

**Interfaces:**
- Consumes: `AlertRepo`, `DispositionRepo` (Task 3); `AlertAlreadyClosedError`, `InvalidDispositionError` (Task 4); all enums (Task 2)
- Produces: `CloseAlertRequest` dataclass, `DispositionService.close_alert(alert_id, analyst_id, req, db) -> AlertDisposition`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_disposition_service.py`:
```python
import uuid
import pytest
from datetime import datetime, timezone, date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.disposition_service import DispositionService, CloseAlertRequest
from app.models.alert import Alert
from app.models.enums import AlertStatus, OutcomeCode, OutcomeReasonCode, OutcomeSource
from app.core.exceptions import AlertAlreadyClosedError, InvalidDispositionError

def make_alert(status=AlertStatus.OPEN):
    return Alert(
        id=uuid.uuid4(), external_id="EXT-T1", rule_id="7.1", client_id="C1",
        amount=Decimal("100000"), alert_dt=datetime.now(timezone.utc), status=status,
    )

def make_req(**overrides):
    defaults = dict(
        outcome_code=OutcomeCode.CLOSED_NO_RISK,
        outcome_reason_code=None,
        escalated_flag=False,
        escalated_dt=None,
        case_id=None,
        sar_flag=False,
        sar_dt=None,
        sar_number=None,
        parent_alert_id=None,
        outcome_source=OutcomeSource.LIVE,
        review_minutes=None,
    )
    defaults.update(overrides)
    return CloseAlertRequest(**defaults)

@pytest.fixture
def svc():
    alert_repo = MagicMock()
    disp_repo = MagicMock()
    return DispositionService(alert_repo, disp_repo), alert_repo, disp_repo

def test_already_closed_raises(svc):
    service, alert_repo, _ = svc
    alert = make_alert(status=AlertStatus.CLOSED)
    alert_repo.get_by_id.return_value = alert
    with pytest.raises(AlertAlreadyClosedError):
        service.close_alert(alert.id, uuid.uuid4(), make_req(), MagicMock())

def test_closed_fp_without_reason_raises(svc):
    service, alert_repo, _ = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    req = make_req(outcome_code=OutcomeCode.CLOSED_FP, outcome_reason_code=None)
    with pytest.raises(InvalidDispositionError, match="outcome_reason_code"):
        service.close_alert(alert.id, uuid.uuid4(), req, MagicMock())

def test_duplicate_without_parent_raises(svc):
    service, alert_repo, _ = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    req = make_req(outcome_code=OutcomeCode.DUPLICATE, parent_alert_id=None)
    with pytest.raises(InvalidDispositionError, match="parent_alert_id"):
        service.close_alert(alert.id, uuid.uuid4(), req, MagicMock())

def test_escalated_without_dt_raises(svc):
    service, alert_repo, _ = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    req = make_req(escalated_flag=True, escalated_dt=None)
    with pytest.raises(InvalidDispositionError, match="escalated_dt"):
        service.close_alert(alert.id, uuid.uuid4(), req, MagicMock())

def test_sar_without_dt_raises(svc):
    service, alert_repo, _ = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    req = make_req(sar_flag=True, sar_dt=None)
    with pytest.raises(InvalidDispositionError, match="sar_dt"):
        service.close_alert(alert.id, uuid.uuid4(), req, MagicMock())

def test_valid_close_creates_disposition_and_closes_alert(svc):
    service, alert_repo, disp_repo = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    db = MagicMock()
    req = make_req(outcome_code=OutcomeCode.CLOSED_NO_RISK, review_minutes=10)
    result = service.close_alert(alert.id, uuid.uuid4(), req, db)
    assert result.outcome_code == OutcomeCode.CLOSED_NO_RISK
    assert result.review_minutes == 10
    disp_repo.create.assert_called_once()
    alert_repo.update_status.assert_called_once_with(alert.id, AlertStatus.CLOSED, db)
    db.commit.assert_called_once()

def test_closed_fp_with_reason_succeeds(svc):
    service, alert_repo, _ = svc
    alert = make_alert()
    alert_repo.get_by_id.return_value = alert
    req = make_req(
        outcome_code=OutcomeCode.CLOSED_FP,
        outcome_reason_code=OutcomeReasonCode.FP_THRESHOLD_LOW,
    )
    result = service.close_alert(alert.id, uuid.uuid4(), req, MagicMock())
    assert result.outcome_code == OutcomeCode.CLOSED_FP
    assert result.outcome_reason_code == OutcomeReasonCode.FP_THRESHOLD_LOW
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=backend pytest tests/unit/test_disposition_service.py -v
```
Expected: FAIL — `DispositionService` not found.

- [ ] **Step 3: Create `backend/app/services/disposition_service.py`**

```python
from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.disposition import AlertDisposition
from app.models.enums import AlertStatus, OutcomeCode, OutcomeReasonCode, OutcomeSource
from app.repositories.alert_repo import AlertRepo
from app.repositories.disposition_repo import DispositionRepo
from app.core.exceptions import AlertAlreadyClosedError, InvalidDispositionError

@dataclass
class CloseAlertRequest:
    outcome_code: OutcomeCode
    outcome_reason_code: Optional[OutcomeReasonCode]
    escalated_flag: bool
    escalated_dt: Optional[datetime]
    case_id: Optional[str]
    sar_flag: bool
    sar_dt: Optional[date]
    sar_number: Optional[str]
    parent_alert_id: Optional[uuid.UUID]
    outcome_source: OutcomeSource
    review_minutes: Optional[int]

class DispositionService:
    def __init__(self, alert_repo: AlertRepo, disposition_repo: DispositionRepo):
        self._alert_repo = alert_repo
        self._disposition_repo = disposition_repo

    def close_alert(
        self,
        alert_id: uuid.UUID,
        analyst_id: uuid.UUID,
        req: CloseAlertRequest,
        db: Session,
    ) -> AlertDisposition:
        alert = self._alert_repo.get_by_id(alert_id, db)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")
        if alert.status == AlertStatus.CLOSED:
            raise AlertAlreadyClosedError(alert_id)

        if req.outcome_code == OutcomeCode.CLOSED_FP and not req.outcome_reason_code:
            raise InvalidDispositionError("outcome_reason_code is required when outcome_code is CLOSED_FP")
        if req.outcome_code == OutcomeCode.DUPLICATE and not req.parent_alert_id:
            raise InvalidDispositionError("parent_alert_id is required when outcome_code is DUPLICATE")
        if req.escalated_flag and not req.escalated_dt:
            raise InvalidDispositionError("escalated_dt is required when escalated_flag is True")
        if req.sar_flag and not req.sar_dt:
            raise InvalidDispositionError("sar_dt is required when sar_flag is True")

        disposition = AlertDisposition(
            id=uuid.uuid4(),
            alert_id=alert_id,
            rule_id=alert.rule_id,
            outcome_code=req.outcome_code,
            outcome_reason_code=req.outcome_reason_code,
            outcome_dt=datetime.now(timezone.utc),
            analyst_id=analyst_id,
            escalated_flag=req.escalated_flag,
            escalated_dt=req.escalated_dt,
            case_id=req.case_id,
            sar_flag=req.sar_flag,
            sar_dt=req.sar_dt,
            sar_number=req.sar_number,
            parent_alert_id=req.parent_alert_id,
            outcome_source=req.outcome_source,
            review_minutes=req.review_minutes,
        )
        self._disposition_repo.create(disposition, db)
        self._alert_repo.update_status(alert_id, AlertStatus.CLOSED, db)
        db.commit()
        return disposition
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=backend pytest tests/unit/test_disposition_service.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: DispositionService — close_alert with all 5 business invariants"
```

---

## Task 6: AlertService + CSV Import

**Files:**
- Create: `backend/app/services/alert_service.py`
- Test: `tests/unit/test_alert_service.py`

**Interfaces:**
- Consumes: `AlertRepo` (Task 3); `Alert`, `AlertStatus` (Task 2)
- Produces: `ImportResult` dataclass, `AlertService.import_from_csv(file_content: bytes, db: Session) -> ImportResult`

CSV format expected (header row required):
`external_id,rule_id,client_id,amount,alert_dt`
`alert_dt` — ISO 8601 string, e.g. `2026-08-01T10:30:00`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_alert_service.py`:
```python
import uuid
import pytest
from app.services.alert_service import AlertService, ImportResult
from app.repositories.alert_repo import AlertRepo

VALID_CSV = b"""external_id,rule_id,client_id,amount,alert_dt
EXT-A1,7.1,CLIENT-1,500000.00,2026-08-01T10:00:00
EXT-A2,7.1,CLIENT-2,200000.00,2026-08-02T11:00:00
"""

INVALID_AMOUNT_CSV = b"""external_id,rule_id,client_id,amount,alert_dt
EXT-B1,7.1,CLIENT-1,-100,2026-08-01T10:00:00
"""

MISSING_FIELD_CSV = b"""external_id,rule_id,client_id,alert_dt
EXT-C1,7.1,CLIENT-1,2026-08-01T10:00:00
"""

def test_import_valid_csv(db):
    from app.models.rule import Rule
    rule = Rule(id="7.1", name="Порог расходов", status="ACTIVE")
    db.add(rule)
    db.commit()
    svc = AlertService(AlertRepo())
    result = svc.import_from_csv(VALID_CSV, db)
    assert result.imported == 2
    assert result.skipped == 0
    assert result.errors == []

def test_import_idempotent(db):
    from app.models.rule import Rule
    rule = Rule(id="7.1", name="Порог расходов", status="ACTIVE")
    db.add(rule)
    db.commit()
    svc = AlertService(AlertRepo())
    svc.import_from_csv(VALID_CSV, db)
    result2 = svc.import_from_csv(VALID_CSV, db)
    assert result2.imported == 0
    assert result2.skipped == 2

def test_import_invalid_amount_reports_error(db):
    from app.models.rule import Rule
    rule = Rule(id="7.1", name="Порог расходов", status="ACTIVE")
    db.add(rule)
    db.commit()
    svc = AlertService(AlertRepo())
    result = svc.import_from_csv(INVALID_AMOUNT_CSV, db)
    assert result.imported == 0
    assert len(result.errors) == 1
    assert "amount" in result.errors[0]

def test_import_missing_field_reports_error(db):
    svc = AlertService(AlertRepo())
    result = svc.import_from_csv(MISSING_FIELD_CSV, db)
    assert result.imported == 0
    assert len(result.errors) >= 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=backend pytest tests/unit/test_alert_service.py -v
```
Expected: FAIL — `AlertService` not found.

- [ ] **Step 3: Create `backend/app/services/alert_service.py`**

```python
from __future__ import annotations
import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.enums import AlertStatus
from app.repositories.alert_repo import AlertRepo

@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

class AlertService:
    def __init__(self, alert_repo: AlertRepo):
        self._alert_repo = alert_repo

    def import_from_csv(self, file_content: bytes, db: Session) -> ImportResult:
        result = ImportResult()
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError:
            result.errors.append("File encoding error: expected UTF-8")
            return result

        reader = csv.DictReader(io.StringIO(text))
        for i, row in enumerate(reader, start=2):
            try:
                external_id = row["external_id"].strip()
                rule_id = row["rule_id"].strip()
                client_id = row["client_id"].strip()
                amount_str = row["amount"].strip()
                alert_dt_str = row["alert_dt"].strip()
            except KeyError as e:
                result.errors.append(f"Row {i}: missing column {e}")
                continue

            if not external_id:
                result.errors.append(f"Row {i}: external_id is empty")
                continue

            try:
                amount = Decimal(amount_str)
            except InvalidOperation:
                result.errors.append(f"Row {i}: amount '{amount_str}' is not a valid number")
                continue

            if amount <= 0:
                result.errors.append(f"Row {i}: amount must be positive, got {amount}")
                continue

            try:
                alert_dt = datetime.fromisoformat(alert_dt_str)
            except ValueError:
                result.errors.append(f"Row {i}: alert_dt '{alert_dt_str}' is not a valid ISO datetime")
                continue

            if self._alert_repo.get_by_external_id(external_id, db):
                result.skipped += 1
                continue

            alert = Alert(
                id=uuid.uuid4(),
                external_id=external_id,
                rule_id=rule_id,
                client_id=client_id,
                amount=amount,
                alert_dt=alert_dt,
                status=AlertStatus.OPEN,
                raw_payload={k: v for k, v in row.items()},
            )
            self._alert_repo.create(alert, db)
            result.imported += 1

        db.commit()
        return result
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=backend pytest tests/unit/test_alert_service.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: AlertService — CSV import with idempotent upsert and error reporting"
```

---

## Task 7: ReportService

**Files:**
- Create: `backend/app/services/report_service.py`
- Test: `tests/unit/test_report_service.py`

**Interfaces:**
- Consumes: `ReportRepo` (Task 3)
- Produces:
  - `ReportService.rule_month_matrix(db, rule_id, from_ym, to_ym) -> list[dict]`
  - `ReportService.to_csv(rows: list[dict]) -> str`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_report_service.py`:
```python
from app.services.report_service import ReportService
from unittest.mock import MagicMock
from app.models.enums import OutcomeCode

def test_to_csv_empty():
    svc = ReportService(MagicMock())
    csv_str = svc.to_csv([])
    assert "rule_id" in csv_str
    assert "count" in csv_str

def test_to_csv_with_rows():
    svc = ReportService(MagicMock())
    rows = [
        {"rule_id": "7.1", "month": "2026-08", "outcome_code": OutcomeCode.CLOSED_FP,
         "outcome_reason_code": "FP_THRESHOLD_LOW", "count": 12},
        {"rule_id": "7.1", "month": "2026-08", "outcome_code": OutcomeCode.CLOSED_NO_RISK,
         "outcome_reason_code": None, "count": 5},
    ]
    csv_str = svc.to_csv(rows)
    assert "7.1" in csv_str
    assert "12" in csv_str
    assert "FP_THRESHOLD_LOW" in csv_str

def test_rule_month_matrix_delegates(db):
    from app.repositories.report_repo import ReportRepo
    from app.repositories.alert_repo import AlertRepo
    from app.repositories.disposition_repo import DispositionRepo
    from app.services.alert_service import AlertService
    from app.services.disposition_service import DispositionService, CloseAlertRequest
    from app.models.rule import Rule
    from app.models.user import User
    from app.models.enums import UserRole, OutcomeCode, OutcomeSource
    from app.core.security import hash_password
    import uuid

    rule = Rule(id="7.1", name="Порог расходов", status="ACTIVE")
    user = User(id=uuid.uuid4(), username="a1", hashed_password=hash_password("p"), role=UserRole.ANALYST)
    db.add_all([rule, user])
    db.commit()

    csv_bytes = b"external_id,rule_id,client_id,amount,alert_dt\nEXT-R1,7.1,C1,100000,2026-08-01T10:00:00\n"
    AlertService(AlertRepo()).import_from_csv(csv_bytes, db)

    from app.repositories.alert_repo import AlertRepo as AR
    alerts = AR().list_all(db)
    alert = alerts[0]
    req = CloseAlertRequest(
        outcome_code=OutcomeCode.CLOSED_FP,
        outcome_reason_code=None,
        escalated_flag=False, escalated_dt=None, case_id=None,
        sar_flag=False, sar_dt=None, sar_number=None, parent_alert_id=None,
        outcome_source=OutcomeSource.LIVE, review_minutes=None,
    )
    # Will raise because reason_code missing — that's fine, just testing report
    try:
        DispositionService(AlertRepo(), DispositionRepo()).close_alert(alert.id, user.id, req, db)
    except Exception:
        pass

    # Close properly
    from app.models.enums import OutcomeReasonCode
    req2 = CloseAlertRequest(
        outcome_code=OutcomeCode.CLOSED_FP,
        outcome_reason_code=OutcomeReasonCode.FP_THRESHOLD_LOW,
        escalated_flag=False, escalated_dt=None, case_id=None,
        sar_flag=False, sar_dt=None, sar_number=None, parent_alert_id=None,
        outcome_source=OutcomeSource.LIVE, review_minutes=None,
    )
    DispositionService(AlertRepo(), DispositionRepo()).close_alert(alert.id, user.id, req2, db)

    svc = ReportService(ReportRepo())
    rows = svc.rule_month_matrix(db, rule_id="7.1")
    assert len(rows) == 1
    assert rows[0]["count"] == 1
    assert rows[0]["rule_id"] == "7.1"
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=backend pytest tests/unit/test_report_service.py -v
```
Expected: FAIL — `ReportService` not found.

- [ ] **Step 3: Create `backend/app/services/report_service.py`**

```python
from __future__ import annotations
import csv
import io
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.report_repo import ReportRepo

class ReportService:
    def __init__(self, report_repo: ReportRepo):
        self._report_repo = report_repo

    def rule_month_matrix(
        self,
        db: Session,
        rule_id: Optional[str] = None,
        from_ym: Optional[str] = None,
        to_ym: Optional[str] = None,
    ) -> list[dict]:
        return self._report_repo.rule_month_matrix(db, rule_id=rule_id, from_ym=from_ym, to_ym=to_ym)

    def to_csv(self, rows: list[dict]) -> str:
        output = io.StringIO()
        fieldnames = ["rule_id", "month", "outcome_code", "outcome_reason_code", "count"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "rule_id": row.get("rule_id", ""),
                "month": row.get("month", ""),
                "outcome_code": row.get("outcome_code", ""),
                "outcome_reason_code": row.get("outcome_reason_code") or "",
                "count": row.get("count", 0),
            })
        return output.getvalue()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=backend pytest tests/unit/test_report_service.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: ReportService — rule×month×outcome matrix + CSV export"
```

---

## Task 8: Routers + Templates

**Files:**
- Create: `backend/app/routers/alerts.py`
- Create: `backend/app/routers/reports.py`
- Create: `backend/app/templates/alerts/list.html`
- Create: `backend/app/templates/alerts/detail.html`
- Create: `backend/app/templates/alerts/close.html`
- Create: `backend/app/templates/alerts/import.html`
- Create: `backend/app/templates/reports/matrix.html`
- Modify: `backend/app/main.py` — include new routers

**Interfaces:**
- Consumes: all services (Tasks 5–7), `get_current_user`, `require_role` (Task 4), `get_db` (Task 1)
- Produces: HTML pages at `/alerts`, `/alerts/{id}`, `/alerts/import`, `/reports/matrix`

- [ ] **Step 1: Create `backend/app/routers/alerts.py`**

```python
from __future__ import annotations
import uuid
import pathlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.enums import UserRole, OutcomeCode, OutcomeReasonCode, OutcomeSource
from app.repositories.alert_repo import AlertRepo
from app.repositories.disposition_repo import DispositionRepo
from app.services.alert_service import AlertService
from app.services.disposition_service import DispositionService, CloseAlertRequest
from app.core.exceptions import AlertAlreadyClosedError, InvalidDispositionError

router = APIRouter(prefix="/alerts", tags=["alerts"])
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent.parent / "templates"))

def _svc(db: Session) -> DispositionService:
    return DispositionService(AlertRepo(), DispositionRepo())

@router.get("")
def list_alerts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AlertRepo()
    alerts = repo.list_all(db, limit=100)
    open_count = repo.count_open(db)
    return templates.TemplateResponse("alerts/list.html", {
        "request": request,
        "alerts": alerts,
        "open_count": open_count,
        "user": current_user,
    })

@router.get("/import")
def import_form(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    return templates.TemplateResponse("alerts/import.html", {"request": request, "result": None, "user": current_user})

@router.post("/import")
async def import_alerts(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    content = await file.read()
    svc = AlertService(AlertRepo())
    result = svc.import_from_csv(content, db)
    return templates.TemplateResponse("alerts/import.html", {
        "request": request,
        "result": result,
        "user": current_user,
    })

@router.get("/{alert_id}")
def alert_detail(
    alert_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = AlertRepo().get_by_id(alert_id, db)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    disposition = DispositionRepo().get_by_alert_id(alert_id, db)
    return templates.TemplateResponse("alerts/detail.html", {
        "request": request,
        "alert": alert,
        "disposition": disposition,
        "user": current_user,
        "OutcomeCode": OutcomeCode,
    })

@router.get("/{alert_id}/close")
def close_form(
    alert_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = AlertRepo().get_by_id(alert_id, db)
    if not alert:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("alerts/close.html", {
        "request": request,
        "alert": alert,
        "user": current_user,
        "OutcomeCode": OutcomeCode,
        "OutcomeReasonCode": OutcomeReasonCode,
        "OutcomeSource": OutcomeSource,
        "error": None,
    })

@router.post("/{alert_id}/close")
def close_alert(
    alert_id: uuid.UUID,
    request: Request,
    outcome_code: str = Form(...),
    outcome_reason_code: Optional[str] = Form(None),
    escalated_flag: bool = Form(False),
    escalated_dt: Optional[str] = Form(None),
    case_id: Optional[str] = Form(None),
    sar_flag: bool = Form(False),
    sar_dt: Optional[str] = Form(None),
    sar_number: Optional[str] = Form(None),
    parent_alert_id: Optional[str] = Form(None),
    outcome_source: str = Form("LIVE"),
    review_minutes: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = AlertRepo().get_by_id(alert_id, db)
    if not alert:
        raise HTTPException(status_code=404)

    req = CloseAlertRequest(
        outcome_code=OutcomeCode(outcome_code),
        outcome_reason_code=OutcomeReasonCode(outcome_reason_code) if outcome_reason_code else None,
        escalated_flag=escalated_flag,
        escalated_dt=datetime.fromisoformat(escalated_dt) if escalated_dt else None,
        case_id=case_id or None,
        sar_flag=sar_flag,
        sar_dt=datetime.fromisoformat(sar_dt).date() if sar_dt else None,
        sar_number=sar_number or None,
        parent_alert_id=uuid.UUID(parent_alert_id) if parent_alert_id else None,
        outcome_source=OutcomeSource(outcome_source),
        review_minutes=review_minutes,
    )
    try:
        svc = DispositionService(AlertRepo(), DispositionRepo())
        svc.close_alert(alert_id, current_user.id, req, db)
    except (AlertAlreadyClosedError, InvalidDispositionError) as e:
        return templates.TemplateResponse("alerts/close.html", {
            "request": request,
            "alert": alert,
            "user": current_user,
            "OutcomeCode": OutcomeCode,
            "OutcomeReasonCode": OutcomeReasonCode,
            "OutcomeSource": OutcomeSource,
            "error": str(e),
        })
    return RedirectResponse(url=f"/alerts/{alert_id}", status_code=302)
```

- [ ] **Step 2: Create `backend/app/routers/reports.py`**

```python
from __future__ import annotations
import pathlib
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.report_repo import ReportRepo
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent.parent / "templates"))

@router.get("/matrix")
def matrix(
    request: Request,
    rule_id: Optional[str] = Query(None),
    from_ym: Optional[str] = Query(None),
    to_ym: Optional[str] = Query(None),
    fmt: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ReportService(ReportRepo())
    rows = svc.rule_month_matrix(db, rule_id=rule_id, from_ym=from_ym, to_ym=to_ym)
    if fmt == "csv":
        csv_data = svc.to_csv(rows)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=aml_report.csv"},
        )
    return templates.TemplateResponse("reports/matrix.html", {
        "request": request,
        "rows": rows,
        "rule_id": rule_id or "",
        "from_ym": from_ym or "",
        "to_ym": to_ym or "",
        "user": current_user,
    })
```

- [ ] **Step 3: Update `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.routers import auth, alerts, reports
import pathlib

app = FastAPI(title="AML Governance Platform")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))

app.include_router(auth.router, tags=["auth"])
app.include_router(alerts.router)
app.include_router(reports.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Create `backend/app/templates/alerts/list.html`**

```html
{% extends "base.html" %}
{% block title %}Алерты — AML Platform{% endblock %}
{% block content %}
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <h2 style="margin:0">Алерты <span style="font-size:14px;color:#888">(открытых: {{ open_count }})</span></h2>
  {% if user.role == 'admin' %}
  <a href="/alerts/import" class="btn btn-sm">Импорт CSV</a>
  {% endif %}
</div>
<table>
  <thead><tr><th>external_id</th><th>Правило</th><th>Клиент</th><th>Сумма</th><th>Дата</th><th>Статус</th><th></th></tr></thead>
  <tbody>
  {% for a in alerts %}
  <tr>
    <td>{{ a.external_id }}</td>
    <td>{{ a.rule_id }}</td>
    <td>{{ a.client_id }}</td>
    <td>{{ "{:,.0f}".format(a.amount) }}</td>
    <td>{{ a.alert_dt.strftime("%Y-%m-%d %H:%M") }}</td>
    <td class="{{ 'badge-open' if a.status.value == 'OPEN' else 'badge-closed' }}">{{ a.status.value }}</td>
    <td><a href="/alerts/{{ a.id }}" class="btn btn-sm">Открыть</a></td>
  </tr>
  {% else %}
  <tr><td colspan="7" style="text-align:center;color:#888">Нет алертов</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Create `backend/app/templates/alerts/detail.html`**

```html
{% extends "base.html" %}
{% block title %}Алерт {{ alert.external_id }}{% endblock %}
{% block content %}
<h2>Алерт: {{ alert.external_id }}</h2>
<table style="width:auto;min-width:400px">
  <tr><th>Правило</th><td>{{ alert.rule_id }}</td></tr>
  <tr><th>Клиент</th><td>{{ alert.client_id }}</td></tr>
  <tr><th>Сумма</th><td>{{ "{:,.2f}".format(alert.amount) }}</td></tr>
  <tr><th>Дата срабатывания</th><td>{{ alert.alert_dt.strftime("%Y-%m-%d %H:%M:%S") }}</td></tr>
  <tr><th>Статус</th><td class="{{ 'badge-open' if alert.status.value == 'OPEN' else 'badge-closed' }}">{{ alert.status.value }}</td></tr>
</table>
{% if disposition %}
<h3>Исход</h3>
<table style="width:auto;min-width:400px">
  <tr><th>Код исхода (D1)</th><td><strong>{{ disposition.outcome_code.value }}</strong></td></tr>
  <tr><th>Причина FP (D2)</th><td>{{ disposition.outcome_reason_code.value if disposition.outcome_reason_code else "—" }}</td></tr>
  <tr><th>Аналитик</th><td>{{ disposition.analyst_id }}</td></tr>
  <tr><th>Дата закрытия</th><td>{{ disposition.outcome_dt.strftime("%Y-%m-%d %H:%M:%S") }}</td></tr>
  <tr><th>Источник</th><td>{{ disposition.outcome_source.value }}</td></tr>
  <tr><th>Эскалация</th><td>{{ "Да" if disposition.escalated_flag else "Нет" }}</td></tr>
  <tr><th>СПО</th><td>{{ "Да — " + disposition.sar_number if disposition.sar_flag else "Нет" }}</td></tr>
  <tr><th>Трудозатраты (мин)</th><td>{{ disposition.review_minutes or "—" }}</td></tr>
</table>
{% elif alert.status.value == 'OPEN' %}
<br>
<a href="/alerts/{{ alert.id }}/close" class="btn">Закрыть алерт</a>
{% endif %}
<br><br><a href="/alerts">← Все алерты</a>
{% endblock %}
```

- [ ] **Step 6: Create `backend/app/templates/alerts/close.html`**

```html
{% extends "base.html" %}
{% block title %}Закрыть алерт {{ alert.external_id }}{% endblock %}
{% block content %}
<h2>Закрыть алерт: {{ alert.external_id }} ({{ alert.rule_id }})</h2>
{% if error %}<div class="alert-msg error">{{ error }}</div>{% endif %}
<form method="post" action="/alerts/{{ alert.id }}/close">

  <label>Исход (D1) *</label>
  <select name="outcome_code" required id="oc">
    {% for code in OutcomeCode %}
    {% if code.value != 'PENDING' %}
    <option value="{{ code.value }}">{{ code.value }}</option>
    {% endif %}
    {% endfor %}
  </select>

  <label>Причина FP (D2) — обязательно при CLOSED_FP</label>
  <select name="outcome_reason_code" id="rc">
    <option value="">— нет —</option>
    {% for code in OutcomeReasonCode %}
    <option value="{{ code.value }}">{{ code.value }}</option>
    {% endfor %}
  </select>

  <label>Источник данных</label>
  <select name="outcome_source">
    <option value="LIVE">LIVE (текущая работа)</option>
    <option value="RETRO">RETRO (историческая разметка)</option>
  </select>

  <label><input type="checkbox" name="escalated_flag" value="true"> Эскалация</label>
  <label>Дата эскалации</label>
  <input type="datetime-local" name="escalated_dt">

  <label><input type="checkbox" name="sar_flag" value="true"> СПО направлено</label>
  <label>Дата СПО</label>
  <input type="date" name="sar_dt">
  <label>Номер СПО</label>
  <input type="text" name="sar_number" placeholder="регистрационный номер">

  <label>ID родительского алерта (при DUPLICATE)</label>
  <input type="text" name="parent_alert_id" placeholder="UUID">

  <label>Трудозатраты (минуты)</label>
  <input type="number" name="review_minutes" min="0">

  <label>Номер дела (case_id)</label>
  <input type="text" name="case_id">

  <br><br>
  <button class="btn" type="submit">Закрыть алерт</button>
  <a href="/alerts/{{ alert.id }}" style="margin-left:12px">Отмена</a>
</form>
{% endblock %}
```

- [ ] **Step 7: Create `backend/app/templates/alerts/import.html`**

```html
{% extends "base.html" %}
{% block title %}Импорт алертов{% endblock %}
{% block content %}
<h2>Импорт алертов из CSV</h2>
<p style="color:#555;font-size:14px">Формат CSV: <code>external_id,rule_id,client_id,amount,alert_dt</code><br>
alert_dt — ISO 8601, например: <code>2026-08-01T10:30:00</code></p>
{% if result %}
<div class="alert-msg">
  Импортировано: <strong>{{ result.imported }}</strong> &nbsp;|&nbsp;
  Пропущено (дубли): <strong>{{ result.skipped }}</strong>
  {% if result.errors %}
  <br><br>Ошибки:
  <ul>{% for e in result.errors %}<li class="error">{{ e }}</li>{% endfor %}</ul>
  {% endif %}
</div>
{% endif %}
<form method="post" action="/alerts/import" enctype="multipart/form-data">
  <label>CSV-файл *</label>
  <input type="file" name="file" accept=".csv" required>
  <br><br>
  <button class="btn" type="submit">Загрузить</button>
</form>
{% endblock %}
```

- [ ] **Step 8: Create `backend/app/templates/reports/matrix.html`**

```html
{% extends "base.html" %}
{% block title %}Отчёт: правило × месяц × исход{% endblock %}
{% block content %}
<h2>Отчёт: правило × месяц × исход × причина</h2>
<form method="get" style="display:flex;gap:12px;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap">
  <div>
    <label style="display:block;font-size:12px">Правило</label>
    <input name="rule_id" value="{{ rule_id }}" placeholder="7.1" style="width:120px">
  </div>
  <div>
    <label style="display:block;font-size:12px">С (YYYY-MM)</label>
    <input name="from_ym" value="{{ from_ym }}" placeholder="2026-01" style="width:110px">
  </div>
  <div>
    <label style="display:block;font-size:12px">По (YYYY-MM)</label>
    <input name="to_ym" value="{{ to_ym }}" placeholder="2026-08" style="width:110px">
  </div>
  <button class="btn" type="submit">Фильтр</button>
  <a href="/reports/matrix?rule_id={{ rule_id }}&from_ym={{ from_ym }}&to_ym={{ to_ym }}&fmt=csv" class="btn" style="background:#4a7a4a">CSV ↓</a>
</form>

{% if rows %}
<table>
  <thead><tr><th>Правило</th><th>Месяц</th><th>Исход (D1)</th><th>Причина FP (D2)</th><th>Кол-во</th></tr></thead>
  <tbody>
  {% for r in rows %}
  <tr>
    <td>{{ r.rule_id }}</td>
    <td>{{ r.month }}</td>
    <td>{{ r.outcome_code.value if r.outcome_code else r.outcome_code }}</td>
    <td>{{ r.outcome_reason_code.value if r.outcome_reason_code else "—" }}</td>
    <td><strong>{{ r.count }}</strong></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p style="color:#888">Нет данных. Закройте алерты с исходами, чтобы данные появились здесь.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 9: Run all unit tests**

```bash
PYTHONPATH=backend pytest tests/ -v --ignore=tests/integration
```
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "feat: routers + Jinja2 templates — alerts list/detail/close/import, report matrix"
```

---

## Task 9: Integration Tests + Seed Data + Smoke Run

**Files:**
- Create: `tests/integration/test_alerts_flow.py`
- Create: `backend/app/seed.py` — creates admin user on first startup

**Interfaces:**
- Consumes: all previous tasks

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_alerts_flow.py`:
```python
import uuid
import pytest
from app.models.rule import Rule
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import hash_password

CSV_DATA = b"""external_id,rule_id,client_id,amount,alert_dt
INT-001,7.1,CLIENT-A,750000.00,2026-08-01T09:00:00
INT-002,7.1,CLIENT-B,820000.00,2026-08-02T10:00:00
"""

@pytest.fixture
def seeded_client(client, db):
    rule = Rule(id="7.1", name="Порог расходов ЮЛ", status="ACTIVE", alerts_per_year=4710)
    admin = User(id=uuid.uuid4(), username="admin", hashed_password=hash_password("admin123"), role=UserRole.ADMIN)
    db.add_all([rule, admin])
    db.commit()
    # Login
    client.post("/login", data={"username": "admin", "password": "admin123"})
    return client

def test_full_flow(seeded_client, db):
    client = seeded_client

    # 1. Import CSV
    resp = client.post("/alerts/import", files={"file": ("alerts.csv", CSV_DATA, "text/csv")})
    assert resp.status_code == 200
    assert "Импортировано: <strong>2</strong>" in resp.text

    # 2. List alerts — 2 open
    resp = client.get("/alerts")
    assert resp.status_code == 200
    assert "INT-001" in resp.text
    assert "INT-002" in resp.text

    # 3. Get alert detail
    from app.repositories.alert_repo import AlertRepo
    alerts = AlertRepo().list_all(db)
    alert_id = str(alerts[0].id)
    resp = client.get(f"/alerts/{alert_id}")
    assert resp.status_code == 200
    assert "Закрыть алерт" in resp.text

    # 4. Close alert — CLOSED_FP without reason should fail
    resp = client.post(f"/alerts/{alert_id}/close", data={
        "outcome_code": "CLOSED_FP",
        "outcome_source": "LIVE",
        "escalated_flag": False,
        "sar_flag": False,
    })
    assert resp.status_code == 200
    assert "outcome_reason_code" in resp.text.lower() or "required" in resp.text.lower() or "error" in resp.text.lower()

    # 5. Close alert properly
    resp = client.post(f"/alerts/{alert_id}/close", data={
        "outcome_code": "CLOSED_FP",
        "outcome_reason_code": "FP_THRESHOLD_LOW",
        "outcome_source": "LIVE",
        "escalated_flag": False,
        "sar_flag": False,
    }, follow_redirects=False)
    assert resp.status_code == 302

    # 6. Alert detail now shows disposition
    resp = client.get(f"/alerts/{alert_id}")
    assert "CLOSED_FP" in resp.text
    assert "FP_THRESHOLD_LOW" in resp.text
    assert "Закрыть алерт" not in resp.text

    # 7. Report shows the closed alert
    resp = client.get("/reports/matrix?rule_id=7.1")
    assert resp.status_code == 200
    assert "7.1" in resp.text
    assert "CLOSED_FP" in resp.text

    # 8. CSV export works
    resp = client.get("/reports/matrix?rule_id=7.1&fmt=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "CLOSED_FP" in resp.text

def test_idempotent_import(seeded_client):
    client = seeded_client
    client.post("/alerts/import", files={"file": ("a.csv", CSV_DATA, "text/csv")})
    resp = client.post("/alerts/import", files={"file": ("a.csv", CSV_DATA, "text/csv")})
    assert "Пропущено (дубли): <strong>2</strong>" in resp.text

def test_report_empty(seeded_client):
    resp = seeded_client.get("/reports/matrix")
    assert resp.status_code == 200
    assert "Нет данных" in resp.text
```

- [ ] **Step 2: Run integration tests**

```bash
PYTHONPATH=backend pytest tests/integration/ -v
```
Expected: all PASS.

- [ ] **Step 3: Create `backend/app/seed.py`** — run once to create admin user

```python
"""Run: PYTHONPATH=backend python -m app.seed"""
from app.db.session import SessionLocal
from app.models.user import User
from app.models.rule import Rule
from app.models.enums import UserRole
from app.core.security import hash_password
import uuid

def seed():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(id=uuid.uuid4(), username="admin", hashed_password=hash_password("admin123"), role=UserRole.ADMIN)
            db.add(admin)
            print("Created admin user (admin / admin123)")

        rules = [
            Rule(id="7.1",    name="Порог расходов ЮЛ",       status="ACTIVE", alerts_per_year=4710),
            Rule(id="№4",     name="Закупка наличной выручки", status="ACTIVE", alerts_per_year=4222),
            Rule(id="РС_103", name="Крупный оборот",           status="ACTIVE", alerts_per_year=4047),
            Rule(id="№3",     name="НДС-разрыв",               status="ACTIVE", alerts_per_year=1517),
            Rule(id="РС_101", name="Веер от ЮЛ",              status="ACTIVE", alerts_per_year=261),
            Rule(id="РС_102", name="Веер от ИП",              status="ACTIVE", alerts_per_year=7),
            Rule(id="РС_104", name="Корп.карта ТСП",          status="ACTIVE", alerts_per_year=289),
            Rule(id="РС_105", name="Платежи красный ЗСК",     status="ACTIVE", alerts_per_year=25),
            Rule(id="РС_110", name="Бюджет→новая орг/ФЛ",    status="ACTIVE", alerts_per_year=26),
        ]
        for r in rules:
            if not db.query(Rule).filter(Rule.id == r.id).first():
                db.add(r)
                print(f"Created rule {r.id}")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
```

- [ ] **Step 4: Run full test suite**

```bash
PYTHONPATH=backend pytest tests/ -v
```
Expected: ALL tests PASS.

- [ ] **Step 5: Local smoke run**

```bash
docker compose up --build -d
# wait ~10s for postgres healthcheck
docker compose logs app
# should show: "Uvicorn running on http://0.0.0.0:8000"

# Seed data
docker compose exec app python -m app.seed

# Test
curl http://localhost:8001/health
# → {"status":"ok"}
```
Open `http://localhost:8001/login` — login with `admin / admin123`.

- [ ] **Step 6: Verify acceptance criteria**

- [ ] Fields in `alert_dispositions` match spec (check via `\d alert_dispositions` in psql)
- [ ] POST `/alerts/{id}/close` without outcome_code → 422
- [ ] POST `/alerts/{id}/close` with CLOSED_FP + no reason_code → form error shown
- [ ] POST `/alerts/{id}/close` properly → redirects to detail, disposition shown
- [ ] GET `/reports/matrix?fmt=csv` → downloads CSV with `rule_id,month,outcome_code,outcome_reason_code,count`
- [ ] `docker compose down && docker compose up` → migrations re-apply, data persists via volume

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: integration tests, seed data — DATA-1 complete"
```

---

## Acceptance Checklist

- [ ] `pytest tests/ -v` → all green
- [ ] `docker compose up --build` → app starts, migrations auto-apply
- [ ] Login, import CSV, close alert with CLOSED_FP + reason, view report, download CSV
- [ ] Attempt to re-close closed alert → form error
- [ ] `GET /health` → 200

**DATA-1 ✅ — feedback loop established. FB-1 / TUN-1 / TUN-2 / ARCH-1 now unblocked.**
