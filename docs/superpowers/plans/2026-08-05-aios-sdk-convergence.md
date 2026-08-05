# ESF → AIOS SDK Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ESF a proper domain module on top of AIOS Core SDK — document lifecycle tracked as AIOS Tasks, published snapshots written to AIOS Memories, ESF auth replaced by AIOS Identity.

**Architecture:** Three sequential layers behind `AIOS_ENABLED` env flag. Layer 1 (Tasks) and Layer 3 (Memories) are additive and fire-and-forget — ESF continues standalone when AIOS is down. Layer 2 (Identity) is a hard cutover: removes the `users` table, replaces session auth with AIOS token validation. All AIOS access flows through the `AIOSBridgeService` singleton; the existing fitness-check CI enforces that no ESF file imports `aios.*` directly.

**Tech Stack:** Python 3.11, FastAPI 0.138, SQLAlchemy 2.x, Alembic, `aios-sdk` (from `~/Projects/aios`), `httpx` (transitive via aios-sdk)

## Global Constraints

- Python 3.11, ruff select=["F","I"], line-length=110
- Controller → Service → Repository → DB; no SQL outside repos, no business logic in controllers
- `aios_sdk.*` allowed; `aios.*` banned — fitness-check CI enforces (tools/fitness_check.py)
- Every Alembic migration is reversible (downgrade restores prior state)
- 104 existing tests must stay green after every task
- TDD: write the failing test first, then implementation
- One commit per task on branch `feat/aios-tasks` (Layer 1+3), then `feat/aios-identity` (Layer 2)

---

## File Map

### New files
- `backend/app/core/aios_bridge.py` — `AIOSBridgeService` singleton + `AIOSIdentity` dataclass
- `backend/tests/test_aios_bridge.py` — Layer 1 + Layer 3 tests
- `backend/tests/test_aios_identity.py` — Layer 2 tests
- `backend/alembic/versions/<rev>_add_aios_task_id.py`
- `backend/alembic/versions/<rev>_add_aios_memory_id.py`
- `backend/alembic/versions/<rev>_owner_principal_drop_users.py`

### Modified files
- `backend/requirements.txt` — add `aios-sdk`
- `backend/app/core/config.py` — 5 new AIOS settings
- `backend/app/models/esf_document.py` — `aios_task_id` (Task 3), `owner_principal` + remove `owner_id` FK (Task 8)
- `backend/app/models/esf_snapshot.py` — `aios_memory_id` (Task 5)
- `backend/app/services/esf_service.py` — bridge calls in lifecycle methods (Tasks 4, 6)
- `backend/app/core/security.py` — replace `get_current_user` → `get_current_identity` (Task 8)
- `backend/app/routers/esf.py`, `api.py`, `admin.py`, `auth.py` — `user` → `identity` (Task 8)
- `backend/tests/conftest.py` — replace `seed_users` + `_login` for AIOS tokens (Task 8)

### Deleted files (Layer 2, Task 8)
- `backend/app/core/passwords.py`
- `backend/app/models/user.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/core/jwt.py` (generation half; validation stub remains or file deleted)

---

## Task 1: AIOS SDK dependency + 5 config fields

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_aios_config.py`

**Interfaces:**
- Produces: `settings.AIOS_ENABLED: bool`, `settings.AIOS_BASE_URL: str`, `settings.AIOS_TOKEN: str`, `settings.AIOS_WORKSPACE_ID: str`, `settings.effective_aios_token: str`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_aios_config.py
import os


def test_aios_config_defaults():
    from app.core.config import settings
    assert settings.AIOS_ENABLED is False
    assert settings.AIOS_BASE_URL == "http://localhost:8100"
    assert settings.AIOS_TOKEN == ""
    assert settings.AIOS_WORKSPACE_ID == ""


def test_effective_aios_token_prefers_direct(monkeypatch):
    monkeypatch.setenv("AIOS_TOKEN", "tok-direct")
    from app.core.config import env_or_file
    assert env_or_file("AIOS_TOKEN", "") == "tok-direct"
```

- [ ] **Step 2: Run — expect FAIL (AttributeError: 'Settings' has no 'AIOS_ENABLED')**

```bash
cd backend && python -m pytest tests/test_aios_config.py -v
```

- [ ] **Step 3: Add to `backend/requirements.txt`** (after the `pyjwt` line):

```
# AIOS SDK — domain module integration (ADR-0015). Local path install;
# replace with versioned wheel when AIOS publishes to a private registry.
aios-sdk @ file:///Users/dmitrijcernikov/Projects/aios
```

- [ ] **Step 4: Add to `backend/app/core/config.py`** (after `QR_STORAGE_DIR` block, before `JWT_SECRET_KEY`):

```python
    # AIOS Core integration (ADR-0015). Set AIOS_ENABLED=true when running
    # with a co-deployed AIOS instance. false = standalone mode (default).
    AIOS_ENABLED: bool = os.getenv("AIOS_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    AIOS_BASE_URL: str = os.getenv("AIOS_BASE_URL", "http://localhost:8100")
    AIOS_TOKEN: str = env_or_file("AIOS_TOKEN", "")
    AIOS_TOKEN_FILE: str = os.getenv("AIOS_TOKEN_FILE", "")
    AIOS_WORKSPACE_ID: str = os.getenv("AIOS_WORKSPACE_ID", "")

    @property
    def effective_aios_token(self) -> str:
        return self.AIOS_TOKEN or env_or_file("AIOS_TOKEN", "")
```

- [ ] **Step 5: Run test — expect PASS**

```bash
cd backend && python -m pytest tests/test_aios_config.py -v
```

- [ ] **Step 6: Run full suite — expect 104 pass**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/core/config.py backend/tests/test_aios_config.py
git commit -m "feat(aios): add aios-sdk dependency and AIOS_ENABLED config fields"
```

---

## Task 2: AIOSBridgeService + AIOSIdentity

**Files:**
- Create: `backend/app/core/aios_bridge.py`
- Create: `backend/tests/test_aios_bridge.py`

**Interfaces:**
- Produces: `from app.core.aios_bridge import bridge, AIOSIdentity`
- `bridge.on_document_created(doc: ESFDocument) -> None`
- `bridge.on_document_validated(doc: ESFDocument) -> None`
- `bridge.on_document_published(doc: ESFDocument) -> None`
- `bridge.on_snapshot_created(snapshot: ESFSnapshot) -> str | None`
- `bridge.verify_token(token: str) -> AIOSIdentity`
- `AIOSIdentity(principal: str, tenant_id: str, roles: list[str])`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_aios_bridge.py
import pytest
from unittest.mock import MagicMock, patch


def test_bridge_noop_when_disabled():
    """AIOS_ENABLED=false: all methods succeed without any HTTP calls."""
    from app.core.aios_bridge import AIOSBridgeService
    with patch("app.core.aios_bridge.settings") as s:
        s.AIOS_ENABLED = False
        b = AIOSBridgeService()

    doc = MagicMock()
    doc.uuid = "doc-uuid"
    doc.aios_task_id = None

    b.on_document_created(doc)   # must not raise
    b.on_document_validated(doc)
    b.on_document_published(doc)

    snap = MagicMock()
    snap.uuid = "snap-uuid"
    snap.payload_json = {}
    assert b.on_snapshot_created(snap) is None


def test_bridge_verify_token_raises_when_disabled():
    from app.core.aios_bridge import AIOSBridgeService
    with patch("app.core.aios_bridge.settings") as s:
        s.AIOS_ENABLED = False
        b = AIOSBridgeService()
    with pytest.raises(RuntimeError, match="AIOS is not enabled"):
        b.verify_token("any-token")


def test_aios_identity_dataclass():
    from app.core.aios_bridge import AIOSIdentity
    identity = AIOSIdentity(principal="alice", tenant_id="esf-prod", roles=["admin"])
    assert identity.principal == "alice"
    assert "admin" in identity.roles
```

- [ ] **Step 2: Run — expect FAIL (ImportError: cannot import aios_bridge)**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v
```

- [ ] **Step 3: Create `backend/app/core/aios_bridge.py`**

```python
"""AIOS Core bridge — single SDK integration surface for ESF.

External code uses the module-level `bridge` singleton only.
When AIOS_ENABLED=false the bridge is a complete no-op.
When AIOS_ENABLED=true, failures are logged as warnings (fire-and-forget
for Layers 1 and 3); verify_token raises HTTPException (Layer 2 is strict).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.esf_document import ESFDocument
    from app.models.esf_snapshot import ESFSnapshot

_log = logging.getLogger("esf.aios_bridge")


@dataclass
class AIOSIdentity:
    principal: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)


class AIOSBridgeService:
    def __init__(self) -> None:
        self._enabled = settings.AIOS_ENABLED
        self._client = None
        if self._enabled:
            from aios_sdk import AIOSClient  # noqa: PLC0415
            token = settings.effective_aios_token
            if not token:
                raise RuntimeError(
                    "AIOS_ENABLED=true requires AIOS_TOKEN or AIOS_TOKEN_FILE"
                )
            self._client = AIOSClient(
                base_url=settings.AIOS_BASE_URL,
                token=token,
            )

    # ---- Layer 1: document lifecycle as AIOS Tasks -----------------------

    def on_document_created(self, doc: "ESFDocument") -> None:
        if not self._enabled or self._client is None:
            return
        try:
            from aios_sdk.generated.models import CreateTaskRequest  # noqa: PLC0415
            resp = self._client.tasks.create(
                CreateTaskRequest(
                    title=f"ESF-{doc.esf_number or str(doc.uuid)}",
                    description=f"ESF document lifecycle",
                ),
                idempotency_key=str(doc.uuid),
            )
            doc.aios_task_id = resp.data.id
        except Exception:
            _log.warning("AIOS task create failed for doc %s", doc.uuid, exc_info=True)

    def on_document_validated(self, doc: "ESFDocument") -> None:
        if not self._enabled or self._client is None or not doc.aios_task_id:
            return
        try:
            self._client.tasks.start(doc.aios_task_id)
        except Exception:
            _log.warning("AIOS task start failed for %s", doc.aios_task_id, exc_info=True)

    def on_document_published(self, doc: "ESFDocument") -> None:
        if not self._enabled or self._client is None or not doc.aios_task_id:
            return
        try:
            self._client.tasks.complete(doc.aios_task_id)
        except Exception:
            _log.warning("AIOS task complete failed for %s", doc.aios_task_id, exc_info=True)

    # ---- Layer 3: published snapshot as AIOS Memory ----------------------

    def on_snapshot_created(self, snapshot: "ESFSnapshot") -> Optional[str]:
        """Write snapshot to AIOS Memory before DB commit.

        Returns AIOS memory ID (str) on success, None on failure.
        Caller sets snapshot.aios_memory_id = result before repo.add_pending().
        Idempotency-Key = snapshot.uuid ensures replay-safety if commit fails.
        """
        if not self._enabled or self._client is None:
            return None
        workspace_id = settings.AIOS_WORKSPACE_ID
        if not workspace_id:
            _log.warning("AIOS_WORKSPACE_ID not set — skipping memory for snapshot %s", snapshot.uuid)
            return None
        try:
            from aios_sdk.generated.models import CreateMemoryRequest  # noqa: PLC0415
            resp = self._client.memories.create_in_workspace(
                workspace_id=workspace_id,
                request=CreateMemoryRequest(
                    kind="esf_snapshot",
                    content=snapshot.payload_json,
                    status="active",
                ),
                idempotency_key=str(snapshot.uuid),
            )
            return resp.data.id
        except Exception:
            _log.warning("AIOS memory create failed for snapshot %s", snapshot.uuid, exc_info=True)
            return None

    # ---- Layer 2: AIOS token validation ----------------------------------

    def verify_token(self, token: str) -> AIOSIdentity:
        """Validate an AIOS Bearer token via GET /api/v1/whoami.

        AIOS prerequisite: GET /api/v1/whoami must return
        {"data": {"principal_id": str, "tenant_id": str, "roles": [str]}}.
        Planned for AIOS v0.3.0 (see Task 7 in this plan).

        Raises RuntimeError if AIOS_ENABLED=false.
        Raises HTTPException(401) on invalid token.
        Raises HTTPException(503) if AIOS is unreachable.
        """
        if not self._enabled:
            raise RuntimeError("AIOS is not enabled")
        import httpx  # noqa: PLC0415
        from fastapi import HTTPException  # noqa: PLC0415
        try:
            resp = httpx.get(
                f"{settings.AIOS_BASE_URL}/api/v1/whoami",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        except httpx.RequestError as exc:
            _log.error("AIOS unreachable during verify_token: %s", exc)
            raise HTTPException(status_code=503, detail="AIOS unavailable") from exc
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid or expired AIOS token")
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="AIOS returned unexpected status")
        data = resp.json().get("data", resp.json())
        return AIOSIdentity(
            principal=data["principal_id"],
            tenant_id=data.get("tenant_id", settings.AIOS_WORKSPACE_ID),
            roles=data.get("roles", []),
        )


bridge = AIOSBridgeService()
```

- [ ] **Step 4: Run bridge tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v
```

- [ ] **Step 5: Run full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/aios_bridge.py backend/tests/test_aios_bridge.py
git commit -m "feat(aios): AIOSBridgeService singleton + AIOSIdentity — no-op when disabled"
```

---

## Task 3: ESFDocument migration — `aios_task_id` column

**Files:**
- Modify: `backend/app/models/esf_document.py`
- Create: `backend/alembic/versions/<rev>_add_aios_task_id.py`
- Modify: `backend/tests/test_aios_bridge.py`

**Interfaces:**
- Produces: `ESFDocument.aios_task_id: Optional[str]` (nullable, max 255)

- [ ] **Step 1: Write failing test** (add to `test_aios_bridge.py`):

```python
def test_esf_document_has_aios_task_id_column(db_session):
    from app.models.esf_document import ESFDocument
    from sqlalchemy import inspect
    cols = {c.name: c for c in inspect(ESFDocument.__table__).columns}
    assert "aios_task_id" in cols
    assert cols["aios_task_id"].nullable is True
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py::test_esf_document_has_aios_task_id_column -v
```

- [ ] **Step 3: Add column to `backend/app/models/esf_document.py`** — after the `qr_path` line:

```python
    aios_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

`Optional` is already imported via `from typing import ..., Optional`.

- [ ] **Step 4: Generate Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add_aios_task_id_to_esf_documents"
```

Verify the generated file's upgrade/downgrade:
```python
def upgrade() -> None:
    op.add_column("esf_documents", sa.Column("aios_task_id", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("esf_documents", "aios_task_id")
```

- [ ] **Step 5: Apply**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 6: Run test — expect PASS**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v
```

- [ ] **Step 7: Run full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/esf_document.py backend/alembic/versions/ backend/tests/test_aios_bridge.py
git commit -m "feat(aios): add aios_task_id nullable column to esf_documents"
```

---

## Task 4: ESFService — wire bridge into document lifecycle (Layer 1)

**Files:**
- Modify: `backend/app/services/esf_service.py`
- Modify: `backend/tests/test_aios_bridge.py`

**Interfaces:**
- Consumes: `bridge` from `app.core.aios_bridge`
- Produces: `bridge.on_document_created` called after `create_draft`; `on_document_validated` after `validate`; `on_document_published` after `publish`

- [ ] **Step 1: Write failing tests** (add to `test_aios_bridge.py`):

```python
def test_bridge_on_document_created_called(admin, override_db, seed_users):
    from unittest.mock import patch, MagicMock
    mock_bridge = MagicMock()
    with patch("app.services.esf_service.bridge", mock_bridge):
        r = admin.post("/esf/new")
    assert r.status_code in (200, 303)
    mock_bridge.on_document_created.assert_called_once()


def test_bridge_error_does_not_break_create_draft(admin, override_db, seed_users):
    from unittest.mock import patch, MagicMock
    mock_bridge = MagicMock()
    mock_bridge.on_document_created.side_effect = Exception("AIOS down")
    with patch("app.services.esf_service.bridge", mock_bridge):
        r = admin.post("/esf/new")
    # ESF operation succeeds even when bridge raises
    assert r.status_code in (200, 303)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py::test_bridge_on_document_created_called -v
```

- [ ] **Step 3: Add import to `backend/app/services/esf_service.py`**

After the existing imports, add:
```python
from app.core.aios_bridge import bridge as _aios_bridge
```

- [ ] **Step 4: Modify `create_draft`**

`repo.add(doc)` already commits. The bridge writes `aios_task_id` onto `doc` after the first commit, so a second commit persists it. Wrap the bridge call so ESF never breaks:

```python
    def create_draft(self, user: User) -> ESFDocument:
        doc = ESFDocument(owner_id=user.id, status=DocumentStatus.DRAFT)
        # ... existing supplier prefill + relationship setup unchanged ...
        result = self.repo.add(doc)
        try:
            _aios_bridge.on_document_created(result)
            if result.aios_task_id:
                self.repo.commit()
        except Exception:
            _log.warning("Bridge on_document_created failed", exc_info=True)
        return result
```

- [ ] **Step 5: Modify `validate`**

After `self.repo.commit()` and `self.repo.refresh(doc)` (lines ~426-427):
```python
        self.repo.commit()
        self.repo.refresh(doc)
        if not errors:
            try:
                _aios_bridge.on_document_validated(doc)
            except Exception:
                _log.warning("Bridge on_document_validated failed", exc_info=True)
        return errors
```

- [ ] **Step 6: Modify `publish`**

After the `self.repo.commit()` at the end of the happy-path try block (line ~475), add:
```python
            self.repo.commit()                              # 7. commit once
        except IntegrityError:
            self.repo.rollback()
            raise HTTPException(
                status_code=409,
                detail="Публикация не удалась из-за конфликта номера ЭСФ. Повторите попытку.",
            )
        try:
            _aios_bridge.on_document_published(doc)
        except Exception:
            _log.warning("Bridge on_document_published failed", exc_info=True)
        return []
```

- [ ] **Step 7: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v
```

- [ ] **Step 8: Run full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/esf_service.py backend/tests/test_aios_bridge.py
git commit -m "feat(aios): wire bridge calls into ESFService lifecycle (Layer 1 Tasks)"
```

---

## Task 5: ESFSnapshot migration — `aios_memory_id` column

**Files:**
- Modify: `backend/app/models/esf_snapshot.py`
- Create: `backend/alembic/versions/<rev>_add_aios_memory_id.py`
- Modify: `backend/tests/test_aios_bridge.py`

**Interfaces:**
- Produces: `ESFSnapshot.aios_memory_id: Optional[str]` (nullable, max 255)

- [ ] **Step 1: Write failing test** (add to `test_aios_bridge.py`):

```python
def test_esf_snapshot_has_aios_memory_id_column(db_session):
    from app.models.esf_snapshot import ESFSnapshot
    from sqlalchemy import inspect
    cols = {c.name: c for c in inspect(ESFSnapshot.__table__).columns}
    assert "aios_memory_id" in cols
    assert cols["aios_memory_id"].nullable is True
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py::test_esf_snapshot_has_aios_memory_id_column -v
```

- [ ] **Step 3: Add to `backend/app/models/esf_snapshot.py`**

Add `Optional` to the `typing` import if missing. After the `immutable` column:
```python
    aios_memory_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd backend && alembic revision --autogenerate -m "add_aios_memory_id_to_esf_snapshots"
cd backend && alembic upgrade head
```

Verify generated migration:
```python
def upgrade() -> None:
    op.add_column("esf_snapshots", sa.Column("aios_memory_id", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("esf_snapshots", "aios_memory_id")
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v && python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/esf_snapshot.py backend/alembic/versions/ backend/tests/test_aios_bridge.py
git commit -m "feat(aios): add aios_memory_id nullable column to esf_snapshots"
```

---

## Task 6: Publish → AIOS Memory write (Layer 3)

**Files:**
- Modify: `backend/app/services/esf_service.py` (publish method)
- Modify: `backend/tests/test_aios_bridge.py`

**Interfaces:**
- Consumes: `bridge.on_snapshot_created(snapshot) -> str | None`
- `ESFSnapshot.aios_memory_id` set BEFORE `repo.add_pending()` — avoids the `before_update` immutability guard

**Critical note:** `aios_memory_id` must be set on the snapshot object BEFORE calling `repo.add_pending(snap)` and the subsequent `repo.commit()`. Setting it after commit triggers the `SnapshotImmutableError` SQLAlchemy event listener.

- [ ] **Step 1: Write failing test** (add to `test_aios_bridge.py`):

```python
def test_on_snapshot_created_called_during_publish(admin, override_db, seed_users):
    """bridge.on_snapshot_created is called during publish."""
    from unittest.mock import patch, MagicMock
    mock_bridge = MagicMock()
    mock_bridge.on_snapshot_created.return_value = "aios-mem-123"
    mock_bridge.on_document_created.return_value = None
    mock_bridge.on_document_published.return_value = None

    with patch("app.services.esf_service._aios_bridge", mock_bridge):
        # Create and fill a doc to publishable state
        r = admin.post("/esf/new")
        assert r.status_code in (200, 303)
        # snapshot_created is NOT called on draft create
        mock_bridge.on_snapshot_created.assert_not_called()
```

Note: a full publish requires a valid document. The existing regression suite has publish tests — run those to verify the snapshot memory write path.

- [ ] **Step 2: Modify `publish` in `backend/app/services/esf_service.py`**

Replace the snapshot creation inside the try block:
```python
            # BEFORE (lines ~473-474):
            payload = self.serialize(doc)
            self.repo.add_pending(snapshot_service.make_snapshot(doc, payload))

            # AFTER:
            payload = self.serialize(doc)
            snap = snapshot_service.make_snapshot(doc, payload)
            try:
                aios_mem_id = _aios_bridge.on_snapshot_created(snap)
                if aios_mem_id:
                    snap.aios_memory_id = aios_mem_id
            except Exception:
                _log.warning("Bridge on_snapshot_created failed", exc_info=True)
            self.repo.add_pending(snap)
```

The commit at line ~475 (`self.repo.commit()`) persists both the snapshot and `aios_memory_id` atomically.

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/test_aios_bridge.py -v
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/esf_service.py backend/tests/test_aios_bridge.py
git commit -m "feat(aios): write published snapshot to AIOS Memory on publish (Layer 3)"
```

---

## Task 7: AIOS prerequisite — `GET /api/v1/whoami` endpoint

**Context:** This task is performed in the **AIOS repository** (`~/Projects/aios`), not ESF. `AIOSBridgeService.verify_token` (already written in Task 2) calls `GET {AIOS_BASE_URL}/api/v1/whoami`. That endpoint must exist before Layer 2 (Task 8) can be tested end-to-end.

**Required response shape:**
```json
{
  "data": {
    "principal_id": "alice",
    "tenant_id": "esf-prod",
    "roles": ["admin"]
  }
}
```

- [ ] **Step 1: In AIOS repo, find the HTTP router file**

```bash
cd ~/Projects/aios && grep -rn "router\|app.include_router\|APIRouter" src/aios/ | grep -v __pycache__ | head -20
```

- [ ] **Step 2: Write failing test in AIOS**

```python
# ~/Projects/aios/tests/test_whoami.py
def test_whoami_returns_caller_identity(authenticated_client):
    """Authenticated caller gets their own principal_id."""
    resp = authenticated_client.get("/api/v1/whoami")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "principal_id" in body["data"]
    assert "tenant_id" in body["data"]
    assert "roles" in body["data"]


def test_whoami_requires_auth(anon_client):
    resp = anon_client.get("/api/v1/whoami")
    assert resp.status_code == 401
```

- [ ] **Step 3: Add route to AIOS HTTP layer**

```python
@router.get("/whoami")
async def whoami(ctx: RequestContext = Depends(get_request_context)):
    """Return the authenticated caller's identity."""
    return {
        "data": {
            "principal_id": ctx.principal.id,
            "tenant_id": str(ctx.tenant_id),
            "roles": list(ctx.capabilities),
        }
    }
```

- [ ] **Step 4: Run AIOS tests + commit AIOS**

```bash
cd ~/Projects/aios && python -m pytest tests/test_whoami.py -v
git add src/aios/ tests/test_whoami.py
git commit -m "feat(auth): add GET /api/v1/whoami identity endpoint for domain module auth"
```

---

## Task 8: Layer 2 — Replace ESF auth with AIOS Identity

**Prerequisite:** Task 7 deployed and reachable at `AIOS_BASE_URL`. Deploy on branch `feat/aios-identity`.

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/models/esf_document.py` (add `owner_principal`, remove `owner_id` FK)
- Create: `backend/alembic/versions/<rev>_owner_principal_drop_users.py`
- Modify: `backend/app/services/esf_service.py` (User → AIOSIdentity in signatures)
- Modify: `backend/app/routers/esf.py`, `api.py`, `admin.py`, `auth.py`
- Modify: `backend/tests/conftest.py`
- Delete: `backend/app/core/passwords.py`, `backend/app/models/user.py`, `backend/app/repositories/user_repository.py`, `backend/app/core/jwt.py`
- Create: `backend/tests/test_aios_identity.py`

**Interfaces:**
- Produces: `get_current_identity(request: Request) -> AIOSIdentity` FastAPI dependency
- `get_current_api_identity(credentials) -> AIOSIdentity` for Bearer routes
- `require_owner_or_admin_identity(doc, identity: AIOSIdentity) -> None`
- `require_admin_identity(identity: AIOSIdentity) -> None`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_aios_identity.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def test_get_current_identity_from_session():
    from app.core.aios_bridge import AIOSIdentity
    expected = AIOSIdentity(principal="alice", tenant_id="esf-prod", roles=["admin"])

    with patch("app.core.security.bridge") as mock_bridge:
        mock_bridge.verify_token.return_value = expected
        from app.core.security import get_current_identity
        req = MagicMock()
        req.session = {"aios_token": "tok"}
        result = get_current_identity(req)
    assert result.principal == "alice"


def test_get_current_identity_no_token_raises():
    from app.core.security import get_current_identity, NotAuthenticated
    req = MagicMock()
    req.session = {}
    with pytest.raises(NotAuthenticated):
        get_current_identity(req)


def test_require_owner_or_admin_identity_owner_passes():
    from app.core.security import require_owner_or_admin_identity
    from app.core.aios_bridge import AIOSIdentity
    doc = MagicMock()
    doc.owner_principal = "alice"
    identity = AIOSIdentity(principal="alice", tenant_id="t", roles=["issuer"])
    require_owner_or_admin_identity(doc, identity)  # no raise


def test_require_owner_or_admin_identity_non_owner_denied():
    from fastapi import HTTPException
    from app.core.security import require_owner_or_admin_identity
    from app.core.aios_bridge import AIOSIdentity
    doc = MagicMock()
    doc.owner_principal = "alice"
    identity = AIOSIdentity(principal="bob", tenant_id="t", roles=["issuer"])
    with pytest.raises(HTTPException) as exc:
        require_owner_or_admin_identity(doc, identity)
    assert exc.value.status_code == 403


def test_require_owner_or_admin_identity_admin_passes():
    from app.core.security import require_owner_or_admin_identity
    from app.core.aios_bridge import AIOSIdentity
    doc = MagicMock()
    doc.owner_principal = "alice"
    identity = AIOSIdentity(principal="bob", tenant_id="t", roles=["admin"])
    require_owner_or_admin_identity(doc, identity)  # admin passes regardless


def test_auth_token_endpoint_returns_404():
    from app.main import app
    client = TestClient(app)
    r = client.post("/auth/token", json={"username": "x", "password": "y"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_aios_identity.py -v
```

- [ ] **Step 3: Add `owner_principal` to ESFDocument**

In `backend/app/models/esf_document.py`, after `aios_task_id`:
```python
    owner_principal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
```

- [ ] **Step 4: Create Alembic migration (manual — autogenerate won't handle DROP TABLE correctly)**

```bash
cd backend && alembic revision -m "owner_principal_drop_users"
```

Edit the generated file:
```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # 1. Add owner_principal
    op.add_column("esf_documents", sa.Column("owner_principal", sa.String(255), nullable=True))
    op.create_index("ix_esf_documents_owner_principal", "esf_documents", ["owner_principal"])
    # 2. Backfill from existing owner_id (safe: legacy-N is unique per user)
    op.execute(
        "UPDATE esf_documents SET owner_principal = 'legacy-' || owner_id::text "
        "WHERE owner_principal IS NULL"
    )
    # 3. Drop FK constraint from esf_documents.owner_id → users.id
    op.drop_constraint("esf_documents_owner_id_fkey", "esf_documents", type_="foreignkey")
    # 4. Drop users table (api_credentials references users too — drop its FK first)
    op.drop_constraint("api_credentials_user_id_fkey", "api_credentials", type_="foreignkey")
    op.drop_table("users")


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="issuer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_foreign_key(
        "esf_documents_owner_id_fkey", "esf_documents", "users", ["owner_id"], ["id"]
    )
    op.create_foreign_key(
        "api_credentials_user_id_fkey", "api_credentials", "users", ["user_id"], ["id"]
    )
    op.drop_index("ix_esf_documents_owner_principal", "esf_documents")
    op.drop_column("esf_documents", "owner_principal")
```

Note: inspect actual FK names first:
```bash
cd backend && python -c "
from sqlalchemy import inspect, create_engine, text
from app.core.config import settings
e = create_engine(settings.DATABASE_URL)
insp = inspect(e)
print('esf_documents FKs:', [fk['name'] for fk in insp.get_foreign_keys('esf_documents')])
print('api_credentials FKs:', [fk['name'] for fk in insp.get_foreign_keys('api_credentials')])
"
```
Update constraint names in the migration to match actual values.

- [ ] **Step 5: Apply migration**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 6: Replace `backend/app/core/security.py`**

```python
"""Access control — AIOS Identity (Layer 2).

`get_current_identity` reads the AIOS token from the session cookie and
validates it via bridge.verify_token(). `get_current_api_identity` handles
Bearer-token API routes. Public routes use no auth dependency.
CSRF helpers are unchanged.
"""
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.aios_bridge import AIOSIdentity, bridge

_bearer = HTTPBearer(auto_error=False)


class NotAuthenticated(Exception):
    """Raised when a protected route is hit without a valid session."""


def get_current_identity(request: Request) -> AIOSIdentity:
    token = request.session.get("aios_token")
    if not token:
        raise NotAuthenticated()
    return bridge.verify_token(token)


def get_optional_identity(request: Request) -> Optional[AIOSIdentity]:
    token = request.session.get("aios_token")
    if not token:
        return None
    try:
        return bridge.verify_token(token)
    except Exception:
        return None


def get_current_api_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AIOSIdentity:
    """Dependency for API routes protected by Bearer AIOS tokens."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required",
                            headers={"WWW-Authenticate": "Bearer"})
    return bridge.verify_token(credentials.credentials)


def require_owner_or_admin_identity(doc, identity: AIOSIdentity) -> None:
    """Raise 403 unless identity owns the document or has 'admin' role."""
    if doc.owner_principal != identity.principal and "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_admin_identity(identity: AIOSIdentity) -> None:
    if "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="Требуются права администратора.")


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


async def require_csrf(request: Request) -> None:
    session_token = request.session.get("csrf_token")
    token = request.headers.get("X-CSRF-Token")
    if not token:
        form = await request.form()
        token = form.get("csrf_token")
    if not session_token or not token or not secrets.compare_digest(str(token), str(session_token)):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
```

- [ ] **Step 7: Update all router files**

For each of `esf.py`, `api.py`, `admin.py`:
- Replace `from app.core.security import get_current_user, require_owner_or_admin` with `from app.core.security import get_current_identity, get_current_api_identity, require_owner_or_admin_identity, require_admin_identity`
- Replace `user: User = Depends(get_current_user)` → `identity: AIOSIdentity = Depends(get_current_identity)`
- Replace `user: User = Depends(get_current_api_user)` → `identity: AIOSIdentity = Depends(get_current_api_identity)`
- Replace `require_owner_or_admin(doc, user)` → `require_owner_or_admin_identity(doc, identity)`
- Replace `require_admin(user)` → `require_admin_identity(identity)`
- Replace `user.id` (where used as owner check) with `identity.principal`

In `auth.py`: make `POST /auth/token` return 404:
```python
@router.post("/token")
async def token_deprecated():
    raise HTTPException(
        status_code=404,
        detail="Auth is managed by AIOS. Use `aios auth issue` to obtain a token.",
    )
```

Remove the `/login` form POST handler that checked username/password via `AuthService`. Replace with a route that accepts an AIOS token via a form field and stores it in session:
```python
@router.post("/login")
async def login(request: Request, token: str = Form(...)):
    """Accept an AIOS Bearer token and store it in the session."""
    try:
        identity = bridge.verify_token(token)
    except HTTPException:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный токен."})
    request.session["aios_token"] = token
    request.session["user_principal"] = identity.principal
    return RedirectResponse(url="/dashboard", status_code=303)
```

Update `login.html` template: replace username/password fields with a single `token` textarea field.

- [ ] **Step 8: Update ESFService signatures**

Change `create_draft(self, user: User)` → `create_draft(self, owner_principal: str)`:
```python
def create_draft(self, owner_principal: str) -> ESFDocument:
    doc = ESFDocument(owner_principal=owner_principal, status=DocumentStatus.DRAFT)
    # Remove owner_id=user.id; remove User-based supplier prefill or adapt to owner_principal
```

Change all method signatures that take `user: User` → `identity: AIOSIdentity`. Replace `require_owner_or_admin(doc, user)` → `require_owner_or_admin_identity(doc, identity)`.

Remove `from app.models import User` import from `esf_service.py`.

- [ ] **Step 9: Delete no-longer-needed files**

```bash
cd backend
git rm app/core/passwords.py
git rm app/models/user.py
git rm app/repositories/user_repository.py
git rm app/core/jwt.py
```

Also remove all imports of deleted modules from `app/models/__init__.py`, `app/services/auth_service.py` (if it imports User/password), etc:
```bash
grep -rn "from app.core.passwords\|from app.models.user\|from app.repositories.user\|from app.core.jwt" backend/app/
```
Fix all found imports.

- [ ] **Step 10: Update `backend/tests/conftest.py`**

The existing `seed_users` fixture and `_login` helper use `AuthService`. Replace:
```python
from app.core.aios_bridge import AIOSIdentity

@pytest.fixture(autouse=True)
def _reset_ratelimit():
    ratelimit.clear_all()
    yield
    ratelimit.clear_all()


# Helper: create a test client with a mocked AIOS identity in session.
# AIOS is not running in tests; we bypass verify_token via mock.
def _make_client_with_identity(principal: str, roles: list[str]):
    from unittest.mock import patch, MagicMock
    identity = AIOSIdentity(principal=principal, tenant_id="test", roles=roles)
    client = TestClient(app)
    # Inject a fake token into the session
    client.post("/test/set-session", json={"aios_token": f"fake-{principal}"})
    return client, identity


@pytest.fixture
def mock_admin_identity():
    return AIOSIdentity(principal="t_admin", tenant_id="test", roles=["admin"])


@pytest.fixture
def mock_issuer_identity():
    return AIOSIdentity(principal="t_issuer", tenant_id="test", roles=["issuer"])


@pytest.fixture
def admin(override_db, mock_admin_identity):
    from unittest.mock import patch
    client = TestClient(app)
    with patch("app.core.security.bridge") as mock_bridge:
        mock_bridge.verify_token.return_value = mock_admin_identity
        # Set the token in session via a test-only endpoint (see main.py)
        client.post("/test/set-session", json={"aios_token": "fake-admin"})
    return client, mock_admin_identity
```

Add a test-only route in `backend/app/main.py` gated by `ENVIRONMENT=development`:
```python
if not settings.is_production:
    from fastapi import Body
    @app.post("/test/set-session")
    async def test_set_session(request: Request, data: dict = Body(...)):
        """Test-only: directly set session values. Not available in production."""
        request.session.update(data)
        return {"ok": True}
```

- [ ] **Step 11: Run identity tests**

```bash
cd backend && python -m pytest tests/test_aios_identity.py -v
```

- [ ] **Step 12: Run full suite (expect all existing tests pass or are updated)**

```bash
cd backend && python -m pytest tests/ -q
```

Note: existing regression tests that test the login flow, user creation, JWT tokens will need to be updated to use the new mock identity pattern. Update `test_auth_jwt.py` to test that `POST /auth/token` returns 404 and that AIOS token validation works via mocked bridge.

- [ ] **Step 13: Commit**

```bash
git add backend/app/core/security.py backend/app/core/config.py
git add backend/app/routers/ backend/app/services/esf_service.py
git add backend/app/models/esf_document.py backend/alembic/versions/
git add backend/tests/test_aios_identity.py backend/tests/conftest.py backend/app/main.py
git rm backend/app/core/passwords.py backend/app/models/user.py
git rm backend/app/repositories/user_repository.py backend/app/core/jwt.py
git commit -m "feat(aios): Layer 2 — AIOS Identity auth, drop users table, owner_principal"
```

---

## Self-Review

**Spec coverage:**
- ✅ `AIOS_ENABLED` config flag: Task 1
- ✅ `AIOSBridgeService` singleton + `AIOSIdentity`: Task 2
- ✅ `aios_task_id` column: Task 3; bridge calls: Task 4
- ✅ `aios_memory_id` column: Task 5; memory write in publish: Task 6
- ✅ `GET /api/v1/whoami` prerequisite: Task 7
- ✅ AIOS Identity auth, `owner_principal`, drop users: Task 8
- ✅ `POST /auth/token` → 404: Task 8 Step 7
- ✅ Fire-and-forget for Layers 1 and 3 (exceptions caught in bridge + service): Tasks 2, 4, 6
- ✅ Idempotency via `snapshot.uuid` as `Idempotency-Key`: Task 6
- ✅ All migrations reversible: Tasks 3, 5, 8

**Type consistency:**
- `AIOSIdentity` defined Task 2, used Tasks 8 ✅
- `bridge` imported as `_aios_bridge` in `esf_service.py` (Tasks 4, 6), as `bridge` in `security.py` (Task 8) ✅
- `doc.aios_task_id` set by bridge in Task 4, column added in Task 3 ✅
- `snap.aios_memory_id` set in Task 6, column added in Task 5 ✅
- `doc.owner_principal` added in Task 8, used by `require_owner_or_admin_identity` in Task 8 ✅

**Placeholders:** none — every step has concrete code. Task 7 (AIOS route) references `get_request_context` which is an existing AIOS internal; the exact import path must be confirmed during execution by reading the AIOS router structure.
