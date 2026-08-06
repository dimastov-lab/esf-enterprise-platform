# AICC Sprint 4 — Tasks Migration to AIOS API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AICC's `data/tasks.json` / `tasks_repository.py` backend with the AIOS Tasks API, guarded by `AICC_TASKS_BACKEND=aios` env flag, so all callers (`app.py`, `task_import`, etc.) work identically whether the flag is set or not.

**Architecture:** New code lives exclusively in `command_center/application/aios_tasks.py` (application-layer adapter — zero engine tokens, passes AIOS boundary gate). `tasks_repository.py` gains a lazy-dispatch factory `get_repository(root)` that returns either the existing JSON backend (default) or the new AIOS backend. All other callers use `tasks_repository.get_repository(root)` — no diff outside `tasks_repository.py`, `app.py`, and `task_import.py`. AICC IDs (uuid hex) are kept as-is; a local `data/aios_task_map.json` file bridges AICC ID → AIOS ID without touching any other store.

**Tech Stack:** Python 3.14, pytest, `aios_sdk` (from `~/Projects/aios`, editable install via `requirements.txt`), `httpx.MockTransport` for SDK unit tests.

## Global Constraints

- Import only `aios_sdk.*` — never `aios.*` (ADR-0008 / boundary gate).
- `command_center/application/aios_tasks.py` must not import `streamlit`, `sqlite3`, `subprocess.Popen`, or any token in the AIOS_BOUNDARY_BASELINE name list (queue, scheduler, supervisor, store, repository, audit).
- `AICC_TASKS_BACKEND` absent or `=json` → **zero behavior change**; existing tests must still pass unchanged.
- `AICC_TASKS_BACKEND=aios` requires `AICC_AIOS_URL` and `AICC_AIOS_TOKEN` to be set; missing → raise `RuntimeError` at import of the repository (fail-closed, not silently fall back).
- All operations are synchronous; `AIOSClient` (sync) not `AsyncAIOSClient`.
- Commit after every task; push to a branch `feat/tasks-aios-backend`.
- Working directory for all commands: `~/Projects/ai-command-center`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `command_center/application/aios_tasks.py` | **Create** | Adapter (mapping), ID map I/O, `AIOSTasksRepository` class |
| `command_center/tasks_repository.py` | **Modify** | Add `TasksPort` ABC + `JSONTasksRepository` wrapper + `get_repository(root)` factory |
| `requirements.txt` | **Modify** | Add `aios-sdk` editable reference |
| `app.py` | **Modify** | Replace direct `tasks_repository.*` calls with `get_repository(root).*` |
| `command_center/task_import.py` | **Modify** | Same — use `get_repository(root)` |
| `scripts/migrate_tasks_to_aios.py` | **Create** | One-shot bulk migration + map build |
| `tests/test_aios_tasks_adapter.py` | **Create** | Adapter unit tests (pure functions) |
| `tests/test_aios_tasks_repository.py` | **Create** | `AIOSTasksRepository` tests via `httpx.MockTransport` |
| `tests/test_tasks_backend_routing.py` | **Create** | Factory routes correctly; JSON backend unchanged |

---

## Task 1: Adapter — pure mapping functions

**Files:**
- Create: `command_center/application/aios_tasks.py`
- Test: `tests/test_aios_tasks_adapter.py`

**Interfaces:**
- Produces:
  - `aicc_dict_to_create_request(task: dict) -> tuple[CreateTaskRequest, str]` — returns (request, target_aios_state); target_aios_state ∈ {"open", "in_progress", "completed"}
  - `aios_task_to_aicc_dict(task: Task) -> dict` — reconstructs full AICC dict from AIOS Task

- [ ] **Step 1.1: Write failing tests for state/priority/field mapping**

```python
# tests/test_aios_tasks_adapter.py
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from command_center.application.aios_tasks import (
    aicc_dict_to_create_request,
    aios_task_to_aicc_dict,
)
from aios_sdk import CreateTaskRequest, Task

def _make_aicc_task(**overrides) -> dict:
    base = {
        "id": "abc123",
        "project": "AICC",
        "title": "Implement auth",
        "task_type": "implementation",
        "status": "Backlog",
        "priority": "Medium",
        "owner": "alice",
        "estimate_hours": 4.0,
        "depends_on": [],
        "goal": "Add auth",
        "notes": "notes here",
        "workflow_stage": "Draft",
        "created_at": "2026-08-06T10:00:00Z",
        "updated_at": "2026-08-06T10:00:00Z",
    }
    base.update(overrides)
    return base

def _make_aios_task(**overrides) -> Task:
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    t = MagicMock(spec=Task)
    t.id = "aios-task-1"
    t.title = "Implement auth"
    t.type = "implementation"
    t.subject_ref = "AICC/abc123"
    t.state = "open"
    t.priority = 2
    t.assignee = None
    t.escalated = False
    t.escalation_target = None
    t.due_at = None
    t.created_by = "alice"
    t.created_at = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
    t.updated_at = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
    t.payload = {
        "kanban_status": "Backlog",
        "project": "AICC",
        "aicc_id": "abc123",
        "task_type": "implementation",
        "workflow_stage": "Draft",
        "owner": "alice",
        "estimate_hours": 4.0,
        "depends_on": [],
        "goal": "Add auth",
        "notes": "notes here",
    }
    for k, v in overrides.items():
        setattr(t, k, v)
    return t

# --- aicc_dict_to_create_request ---

def test_backlog_maps_to_open_state():
    req, target = aicc_dict_to_create_request(_make_aicc_task(status="Backlog"))
    assert target == "open"

def test_in_progress_maps_to_in_progress_state():
    req, target = aicc_dict_to_create_request(_make_aicc_task(status="In Progress"))
    assert target == "in_progress"

def test_done_maps_to_completed_state():
    req, target = aicc_dict_to_create_request(_make_aicc_task(status="Done"))
    assert target == "completed"

def test_review_maps_to_in_progress_state():
    req, target = aicc_dict_to_create_request(_make_aicc_task(status="Review"))
    assert target == "in_progress"

def test_next_maps_to_open_state():
    req, target = aicc_dict_to_create_request(_make_aicc_task(status="Next"))
    assert target == "open"

def test_subject_ref_uses_project_and_id():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(project="AML", id="xyz789"))
    assert req.subject_ref == "AML/xyz789"

def test_type_uses_task_type():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(task_type="review"))
    assert req.type == "review"

def test_type_defaults_to_task_when_missing():
    task = _make_aicc_task()
    del task["task_type"]
    req, _ = aicc_dict_to_create_request(task)
    assert req.type == "task"

def test_medium_priority_maps_to_2():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(priority="Medium"))
    assert req.priority == 2

def test_critical_priority_maps_to_4():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(priority="Critical"))
    assert req.priority == 4

def test_low_priority_maps_to_1():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(priority="Low"))
    assert req.priority == 1

def test_high_priority_maps_to_3():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(priority="High"))
    assert req.priority == 3

def test_unknown_priority_defaults_to_2():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(priority="P0"))
    assert req.priority == 2

def test_aicc_id_stored_in_payload():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(id="abc123"))
    assert req.payload["aicc_id"] == "abc123"

def test_kanban_status_stored_in_payload():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(status="Review"))
    assert req.payload["kanban_status"] == "Review"

def test_created_by_uses_owner():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(owner="bob"))
    assert req.created_by == "bob"  # Note: CreateTaskRequest doesn't have created_by
    # created_by is in payload instead
    assert req.payload["owner"] == "bob"

# --- aios_task_to_aicc_dict ---

def test_round_trip_preserves_kanban_status():
    aicc = _make_aicc_task(status="Review")
    req, _ = aicc_dict_to_create_request(aicc)
    # Build a fake AIOS task as the server would return it
    aios = _make_aios_task(payload=req.payload | {"kanban_status": "Review"})
    result = aios_task_to_aicc_dict(aios)
    assert result["status"] == "Review"

def test_round_trip_preserves_project():
    aios = _make_aios_task(payload={"kanban_status": "Backlog", "project": "AICC", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["project"] == "AICC"

def test_round_trip_preserves_aicc_id():
    aios = _make_aios_task(payload={"kanban_status": "Backlog", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["id"] == "abc123"

def test_aios_id_stored_in_aios_id_field():
    aios = _make_aios_task(id="aios-task-99", payload={"kanban_status": "Backlog", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["aios_id"] == "aios-task-99"

def test_priority_2_maps_to_medium():
    aios = _make_aios_task(priority=2, payload={"kanban_status": "Backlog", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["priority"] == "Medium"

def test_priority_4_maps_to_critical():
    aios = _make_aios_task(priority=4, payload={"kanban_status": "Backlog", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["priority"] == "Critical"

def test_title_preserved():
    aios = _make_aios_task(title="My task", payload={"kanban_status": "Backlog", "aicc_id": "abc123"})
    result = aios_task_to_aicc_dict(aios)
    assert result["title"] == "My task"
```

- [ ] **Step 1.2: Run tests — expect failures (module not found)**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_aios_tasks_adapter.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'command_center.application.aios_tasks'`

- [ ] **Step 1.3: Create the adapter module with minimal implementation**

Create `command_center/application/aios_tasks.py`:

```python
"""AIOS Tasks API adapter — field/state mapping between AICC task dicts and AIOS SDK models.

Application-layer only: no engine imports, no sqlite3, no subprocess.
Imports only from aios_sdk (public SDK), not from aios.* (boundary gate: ADR-0008).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from aios_sdk import AIOSClient, CreateTaskRequest, Task

# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

_AICC_PRIORITY_TO_INT: dict[str, int] = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4,
}

_INT_TO_AICC_PRIORITY: dict[int, str] = {v: k for k, v in _AICC_PRIORITY_TO_INT.items()}

# AICC Kanban status → AIOS lifecycle target state after creation
_STATUS_TO_AIOS_STATE: dict[str, str] = {
    "Backlog": "open",
    "Next": "open",
    "In Progress": "in_progress",
    "Review": "in_progress",
    "Done": "completed",
}

_AICC_PAYLOAD_FIELDS: tuple[str, ...] = (
    "project",
    "task_type",
    "workflow_stage",
    "owner",
    "estimate_hours",
    "depends_on",
    "goal",
    "notes",
    "timeline",
    "parent_task_id",
    "prior_run_id",
    "launch_status",
    "current_run_id",
    "report_path",
    "repository_path",
    "branch",
    "last_run_at",
    "latest_verdict",
    "pull_request_url",
    "workspace_path",
    "executor",
    "agent",
    "prompt",
    "untrusted_import",
    "current_stage",
    "progress",
)


def aicc_dict_to_create_request(task: dict[str, Any]) -> tuple[CreateTaskRequest, str]:
    """Map an AICC task dict to a ``CreateTaskRequest`` and the target AIOS state.

    Returns (request, target_state) where target_state ∈ {"open", "in_progress", "completed"}.
    The caller is responsible for driving the task to that state via the SDK
    (task already starts as "open" after create; call .start()/.complete() as needed).
    """
    status = task.get("status", "Backlog")
    target_state = _STATUS_TO_AIOS_STATE.get(status, "open")

    project = task.get("project", "")
    task_id = task.get("id", "")
    subject_ref = f"{project}/{task_id}"[:255] if project and task_id else task_id[:255] or "unknown"

    task_type = task.get("task_type") or "task"
    priority = _AICC_PRIORITY_TO_INT.get(task.get("priority", "Medium"), 2)

    payload: dict[str, Any] = {
        "aicc_id": task_id,
        "kanban_status": status,
    }
    for field in _AICC_PAYLOAD_FIELDS:
        value = task.get(field)
        if value is not None:
            payload[field] = value

    return (
        CreateTaskRequest(
            subject_ref=subject_ref,
            type=task_type,
            title=task.get("title", "Untitled")[:512],
            priority=priority,
            payload=payload,
        ),
        target_state,
    )


def aios_task_to_aicc_dict(task: Task) -> dict[str, Any]:
    """Reconstruct a full AICC task dict from an AIOS Task object.

    The AIOS ``payload`` carries the original AICC fields.
    The AICC ``id`` is restored from ``payload["aicc_id"]`` (the original uuid hex).
    ``aios_id`` is set to the AIOS-system task id for internal mapping use.
    """
    payload = task.payload or {}
    aicc_id = payload.get("aicc_id") or task.id

    now_iso = datetime.now(timezone.utc).isoformat()
    created_at = task.created_at.isoformat() if isinstance(task.created_at, datetime) else now_iso
    updated_at = task.updated_at.isoformat() if isinstance(task.updated_at, datetime) else now_iso

    result: dict[str, Any] = {
        "id": aicc_id,
        "aios_id": task.id,
        "title": task.title,
        "status": payload.get("kanban_status", "Backlog"),
        "priority": _INT_TO_AICC_PRIORITY.get(task.priority, "Medium"),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    # Restore all AICC-specific fields from payload
    for field in _AICC_PAYLOAD_FIELDS:
        if field in payload:
            result[field] = payload[field]
    # Ensure required AICC fields have defaults
    result.setdefault("project", "")
    result.setdefault("task_type", task.type if task.type != "task" else "")
    result.setdefault("depends_on", [])
    result.setdefault("owner", "")
    result.setdefault("estimate_hours", 0.0)
    result.setdefault("goal", result["title"])
    result.setdefault("notes", "")
    result.setdefault("workflow_stage", "Draft")
    result.setdefault("timeline", [])
    return result
```

- [ ] **Step 1.4: Fix the test — `CreateTaskRequest` has no `created_by` field**

Update `test_created_by_uses_owner` test to only assert `req.payload["owner"] == "bob"` (not `req.created_by`).

```python
def test_created_by_uses_owner():
    req, _ = aicc_dict_to_create_request(_make_aicc_task(owner="bob"))
    assert req.payload["owner"] == "bob"
```

- [ ] **Step 1.5: Run tests — expect all to pass**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_aios_tasks_adapter.py -v
```

Expected: all tests PASS.

- [ ] **Step 1.6: Commit**

```bash
cd ~/Projects/ai-command-center && git add command_center/application/aios_tasks.py tests/test_aios_tasks_adapter.py
git commit -m "feat(tasks): AICC↔AIOS field/state mapping adapter"
```

---

## Task 2: AIOSTasksRepository — CRUD over AIOS Tasks API

**Files:**
- Modify: `command_center/application/aios_tasks.py` (add `AIOSIdMap`, `AIOSTasksRepository`)
- Test: `tests/test_aios_tasks_repository.py`

**Interfaces:**
- Consumes: `aicc_dict_to_create_request`, `aios_task_to_aicc_dict` (Task 1)
- Produces:
  - `class AIOSIdMap` — loads/saves `data/aios_task_map.json` (aicc_id → aios_id)
  - `class AIOSTasksRepository` — `load_all()`, `create(task_dict)`, `upsert(task_dict)`, `update_status(task_id, new_status)`, `delete(task_id) -> bool`

- [ ] **Step 2.1: Write failing tests for AIOSTasksRepository**

```python
# tests/test_aios_tasks_repository.py
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from command_center.application.aios_tasks import AIOSIdMap, AIOSTasksRepository
from aios_sdk import AIOSClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_payload(
    task_id: str = "aios-t-1",
    *,
    aicc_id: str = "aicc-abc123",
    state: str = "open",
    title: str = "Test task",
    kanban_status: str = "Backlog",
) -> dict[str, Any]:
    return {
        "data": {
            "id": task_id,
            "state": state,
            "title": title,
            "type": "task",
            "subject_ref": f"AICC/{aicc_id}",
            "assignee": None,
            "priority": 2,
            "escalated": False,
            "escalation_target": None,
            "due_at": None,
            "payload": {"aicc_id": aicc_id, "kanban_status": kanban_status, "project": "AICC"},
            "created_by": "aicc",
            "created_at": "2026-08-06T10:00:00Z",
            "updated_at": "2026-08-06T10:00:00Z",
        },
        "meta": {"request_id": "req-1"},
    }


def _list_payload(tasks: list[dict]) -> dict[str, Any]:
    return {
        "data": tasks,
        "page": {"next_cursor": None, "has_more": False},
        "meta": {"request_id": "req-list"},
    }


def _json_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, headers={"X-Request-Id": "req-1"})


def _make_repo(handler) -> tuple[AIOSTasksRepository, Path]:
    tmp = Path(tempfile.mkdtemp())
    client = AIOSClient("https://test.example", token="tok", transport=httpx.MockTransport(handler))
    id_map = AIOSIdMap(tmp / "aios_task_map.json")
    repo = AIOSTasksRepository(client, id_map)
    return repo, tmp


# ---------------------------------------------------------------------------
# AIOSIdMap
# ---------------------------------------------------------------------------

def test_idmap_empty_on_new_file():
    with tempfile.TemporaryDirectory() as d:
        m = AIOSIdMap(Path(d) / "map.json")
        assert m.get("nonexistent") is None


def test_idmap_put_and_get():
    with tempfile.TemporaryDirectory() as d:
        m = AIOSIdMap(Path(d) / "map.json")
        m.put("aicc-1", "aios-999")
        assert m.get("aicc-1") == "aios-999"


def test_idmap_persists_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "map.json"
        m1 = AIOSIdMap(path)
        m1.put("aicc-1", "aios-999")
        m2 = AIOSIdMap(path)
        assert m2.get("aicc-1") == "aios-999"


def test_idmap_remove():
    with tempfile.TemporaryDirectory() as d:
        m = AIOSIdMap(Path(d) / "map.json")
        m.put("aicc-1", "aios-999")
        m.remove("aicc-1")
        assert m.get("aicc-1") is None


# ---------------------------------------------------------------------------
# AIOSTasksRepository.load_all
# ---------------------------------------------------------------------------

def test_load_all_returns_aicc_dicts():
    def handler(req: httpx.Request) -> httpx.Response:
        raw_task = _task_payload("aios-t-1", aicc_id="abc123")["data"]
        return _json_response(200, _list_payload([raw_task]))

    repo, _ = _make_repo(handler)
    tasks = repo.load_all()
    assert len(tasks) == 1
    assert tasks[0]["id"] == "abc123"
    assert tasks[0]["status"] == "Backlog"


def test_load_all_empty():
    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(200, _list_payload([]))

    repo, _ = _make_repo(handler)
    assert repo.load_all() == []


# ---------------------------------------------------------------------------
# AIOSTasksRepository.create
# ---------------------------------------------------------------------------

def test_create_calls_post_and_returns_aicc_dict():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _json_response(201, _task_payload("aios-new", aicc_id="abc123"))

    repo, tmp = _make_repo(handler)
    task_dict = {
        "id": "abc123",
        "project": "AICC",
        "title": "New task",
        "task_type": "implementation",
        "status": "Backlog",
        "priority": "Medium",
        "owner": "",
        "depends_on": [],
        "created_at": "2026-08-06T10:00:00Z",
        "updated_at": "2026-08-06T10:00:00Z",
    }
    result = repo.create(task_dict)
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/tasks"
    assert result["id"] == "abc123"
    assert result["aios_id"] == "aios-new"


def test_create_records_id_mapping():
    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(201, _task_payload("aios-new", aicc_id="abc123"))

    repo, tmp = _make_repo(handler)
    task_dict = {
        "id": "abc123", "project": "AICC", "title": "T", "task_type": "task",
        "status": "Backlog", "priority": "Medium", "owner": "", "depends_on": [],
        "created_at": "2026-08-06T10:00:00Z", "updated_at": "2026-08-06T10:00:00Z",
    }
    repo.create(task_dict)
    # Map file must now contain aicc→aios mapping
    map_data = json.loads((tmp / "aios_task_map.json").read_text())
    assert map_data["abc123"] == "aios-new"


def test_create_in_progress_task_calls_start():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        if req.method == "POST" and req.url.path == "/api/v1/tasks":
            return _json_response(201, _task_payload("aios-t1", aicc_id="aicc-1", state="open"))
        # start call
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="in_progress"))

    repo, _ = _make_repo(handler)
    task_dict = {
        "id": "aicc-1", "project": "AICC", "title": "WIP task", "task_type": "task",
        "status": "In Progress", "priority": "Medium", "owner": "", "depends_on": [],
        "created_at": "2026-08-06T10:00:00Z", "updated_at": "2026-08-06T10:00:00Z",
    }
    repo.create(task_dict)
    paths = [f"{r.method} {r.url.path}" for r in requests]
    assert "POST /api/v1/tasks" in paths
    assert "POST /api/v1/tasks/aios-t1/start" in paths


def test_create_done_task_calls_complete():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        if req.method == "POST" and req.url.path == "/api/v1/tasks":
            return _json_response(201, _task_payload("aios-t1", aicc_id="aicc-1", state="open"))
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="completed"))

    repo, _ = _make_repo(handler)
    task_dict = {
        "id": "aicc-1", "project": "AICC", "title": "Done", "task_type": "task",
        "status": "Done", "priority": "Medium", "owner": "", "depends_on": [],
        "created_at": "2026-08-06T10:00:00Z", "updated_at": "2026-08-06T10:00:00Z",
    }
    repo.create(task_dict)
    paths = [f"{r.method} {r.url.path}" for r in requests]
    assert "POST /api/v1/tasks/aios-t1/complete" in paths


# ---------------------------------------------------------------------------
# AIOSTasksRepository.update_status
# ---------------------------------------------------------------------------

def test_update_status_to_done_calls_complete():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="completed"))

    repo, tmp = _make_repo(handler)
    # Pre-populate map
    id_map = AIOSIdMap(tmp / "aios_task_map.json")
    id_map.put("aicc-1", "aios-t1")
    repo, _ = _make_repo(handler)
    # Manually inject map
    repo._id_map = id_map

    repo.update_status("aicc-1", "Done")
    paths = [f"{r.method} {r.url.path}" for r in requests]
    assert "POST /api/v1/tasks/aios-t1/complete" in paths


def test_update_status_to_in_progress_calls_start():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="in_progress"))

    repo, tmp = _make_repo(handler)
    id_map = AIOSIdMap(tmp / "aios_task_map.json")
    id_map.put("aicc-1", "aios-t1")
    repo._id_map = id_map

    repo.update_status("aicc-1", "In Progress")
    paths = [f"{r.method} {r.url.path}" for r in requests]
    assert "POST /api/v1/tasks/aios-t1/start" in paths


def test_update_status_unknown_task_is_noop():
    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(200, _task_payload())

    repo, _ = _make_repo(handler)
    # No entry in map → should not raise, just return None
    result = repo.update_status("nonexistent-aicc-id", "Done")
    assert result is None


# ---------------------------------------------------------------------------
# AIOSTasksRepository.delete
# ---------------------------------------------------------------------------

def test_delete_known_task_calls_cancel():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="cancelled"))

    repo, tmp = _make_repo(handler)
    id_map = AIOSIdMap(tmp / "aios_task_map.json")
    id_map.put("aicc-1", "aios-t1")
    repo._id_map = id_map

    result = repo.delete("aicc-1")
    assert result is True
    paths = [f"{r.method} {r.url.path}" for r in requests]
    assert "POST /api/v1/tasks/aios-t1/cancel" in paths


def test_delete_unknown_task_returns_false():
    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(200, _task_payload())

    repo, _ = _make_repo(handler)
    result = repo.delete("nonexistent")
    assert result is False
```

- [ ] **Step 2.2: Run tests — expect failures**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_aios_tasks_repository.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'AIOSIdMap' from 'command_center.application.aios_tasks'`

- [ ] **Step 2.3: Add AIOSIdMap and AIOSTasksRepository to `command_center/application/aios_tasks.py`**

Append to the existing file (after the existing adapter functions):

```python
# ---------------------------------------------------------------------------
# ID mapping (AICC uuid hex ↔ AIOS task id)
# ---------------------------------------------------------------------------

import json
import threading
from pathlib import Path


class AIOSIdMap:
    """Thread-safe persistent mapping between AICC task ids (uuid hex) and AIOS task ids.

    Backed by a single JSON file (`data/aios_task_map.json`). All writes are
    atomic (write-to-temp + os.replace) to prevent corruption on crash.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        import tempfile
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        import os
        os.replace(tmp, self._path)

    def get(self, aicc_id: str) -> str | None:
        with self._lock:
            return self._data.get(aicc_id)

    def put(self, aicc_id: str, aios_id: str) -> None:
        with self._lock:
            self._data[aicc_id] = aios_id
            self._save()

    def remove(self, aicc_id: str) -> None:
        with self._lock:
            if aicc_id in self._data:
                del self._data[aicc_id]
                self._save()


# ---------------------------------------------------------------------------
# AIOS-backed repository
# ---------------------------------------------------------------------------

class AIOSTasksRepository:
    """Implements AICC task CRUD operations via the AIOS Tasks API SDK.

    All methods accept/return plain AICC task dicts (same shape as the JSON backend).
    State transitions drive AIOS lifecycle calls; the local ``AIOSIdMap`` bridges
    AICC uuid-hex ids to AIOS system ids.
    """

    def __init__(self, client: AIOSClient, id_map: AIOSIdMap) -> None:
        self._client = client
        self._id_map = id_map

    def load_all(self) -> list[dict[str, Any]]:
        return [aios_task_to_aicc_dict(t) for t in self._client.tasks.iterate()]

    def create(self, task_dict: dict[str, Any]) -> dict[str, Any]:
        req, target_state = aicc_dict_to_create_request(task_dict)
        result = self._client.tasks.create(req)
        aios_id = result.data.id
        aicc_id = task_dict.get("id", "")
        if aicc_id:
            self._id_map.put(aicc_id, aios_id)
        if target_state == "in_progress":
            result = self._client.tasks.start(aios_id)
        elif target_state == "completed":
            result = self._client.tasks.complete(aios_id)
        return aios_task_to_aicc_dict(result.data)

    def upsert(self, task_dict: dict[str, Any]) -> None:
        aicc_id = task_dict.get("id", "")
        aios_id = self._id_map.get(aicc_id) if aicc_id else None
        if aios_id:
            # Task exists in AIOS — sync status only (full update not in API v1)
            new_status = task_dict.get("status", "Backlog")
            self.update_status(aicc_id, new_status)
        else:
            self.create(task_dict)

    def update_status(self, task_id: str, new_status: str) -> dict[str, Any] | None:
        aios_id = self._id_map.get(task_id)
        if not aios_id:
            return None
        target_state = _STATUS_TO_AIOS_STATE.get(new_status, "open")
        if target_state == "in_progress":
            result = self._client.tasks.start(aios_id)
        elif target_state == "completed":
            result = self._client.tasks.complete(aios_id)
        elif target_state == "open":
            # No direct "reopen" in API v1 — treat as noop (state already open or assigned)
            result = self._client.tasks.get(aios_id)
        else:
            result = self._client.tasks.get(aios_id)
        return aios_task_to_aicc_dict(result.data)

    def delete(self, task_id: str) -> bool:
        aios_id = self._id_map.get(task_id)
        if not aios_id:
            return False
        self._client.tasks.cancel(aios_id)
        self._id_map.remove(task_id)
        return True
```

- [ ] **Step 2.4: Run tests — fix assertion in update_status tests (mock injection pattern)**

The tests use `repo._id_map = id_map` AFTER `_make_repo` creates a new repo instance. Fix: pass `id_map` into `_make_repo`:

```python
def _make_repo(handler, id_map=None) -> tuple[AIOSTasksRepository, Path]:
    tmp = Path(tempfile.mkdtemp())
    client = AIOSClient("https://test.example", token="tok", transport=httpx.MockTransport(handler))
    if id_map is None:
        id_map = AIOSIdMap(tmp / "aios_task_map.json")
    repo = AIOSTasksRepository(client, id_map)
    return repo, tmp
```

And update the three tests that pre-populate the map to pass it explicitly:

```python
def test_update_status_to_done_calls_complete():
    requests: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _json_response(200, _task_payload("aios-t1", aicc_id="aicc-1", state="completed"))

    with tempfile.TemporaryDirectory() as d:
        id_map = AIOSIdMap(Path(d) / "map.json")
        id_map.put("aicc-1", "aios-t1")
        repo, _ = _make_repo(handler, id_map=id_map)

        repo.update_status("aicc-1", "Done")
        paths = [f"{r.method} {r.url.path}" for r in requests]
        assert "POST /api/v1/tasks/aios-t1/complete" in paths
```

Apply same fix to `test_update_status_to_in_progress_calls_start` and `test_delete_known_task_calls_cancel`.

- [ ] **Step 2.5: Run tests — all pass**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_aios_tasks_repository.py -v
```

Expected: all PASS.

- [ ] **Step 2.6: Verify boundary gate still passes**

```bash
cd ~/Projects/ai-command-center && python -m tests.architecture.aios_boundary
```

Expected: no drift (no new entries in the output).

- [ ] **Step 2.7: Commit**

```bash
cd ~/Projects/ai-command-center && git add command_center/application/aios_tasks.py tests/test_aios_tasks_repository.py
git commit -m "feat(tasks): AIOSIdMap + AIOSTasksRepository — CRUD over AIOS Tasks API"
```

---

## Task 3: Feature flag — `get_repository(root)` factory in tasks_repository.py

**Files:**
- Modify: `command_center/tasks_repository.py`
- Modify: `requirements.txt`
- Test: `tests/test_tasks_backend_routing.py`

**Interfaces:**
- Consumes: `AIOSTasksRepository`, `AIOSIdMap` from Task 2
- Produces: `get_repository(root: Path) -> TasksPort` — returns JSON or AIOS backend based on `AICC_TASKS_BACKEND`

- [ ] **Step 3.1: Write routing tests**

```python
# tests/test_tasks_backend_routing.py
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_default_backend_is_json(tmp_path):
    """Without env var, get_repository returns the JSON-backed port."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AICC_TASKS_BACKEND", None)
        from command_center.tasks_repository import get_repository
        repo = get_repository(tmp_path)
        assert repo.__class__.__name__ == "JSONTasksRepository"


def test_explicit_json_backend(tmp_path):
    """AICC_TASKS_BACKEND=json always returns JSON backend."""
    with patch.dict(os.environ, {"AICC_TASKS_BACKEND": "json"}):
        from importlib import reload
        import command_center.tasks_repository as tr_module
        reload(tr_module)
        repo = tr_module.get_repository(tmp_path)
        assert repo.__class__.__name__ == "JSONTasksRepository"


def test_aios_backend_raises_without_url(tmp_path):
    """AICC_TASKS_BACKEND=aios without AICC_AIOS_URL → RuntimeError."""
    env = {"AICC_TASKS_BACKEND": "aios"}
    env.pop("AICC_AIOS_URL", None)
    env.pop("AICC_AIOS_TOKEN", None)
    with patch.dict(os.environ, env):
        os.environ.pop("AICC_AIOS_URL", None)
        os.environ.pop("AICC_AIOS_TOKEN", None)
        from importlib import reload
        import command_center.tasks_repository as tr_module
        reload(tr_module)
        with pytest.raises(RuntimeError, match="AICC_AIOS_URL"):
            tr_module.get_repository(tmp_path)


def test_json_backend_load_tasks_is_empty_on_fresh_dir(tmp_path):
    """JSONTasksRepository.load_all() returns [] for a fresh directory."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AICC_TASKS_BACKEND", None)
        from command_center.tasks_repository import get_repository
        repo = get_repository(tmp_path)
        assert repo.load_all() == []


def test_json_backend_create_and_load(tmp_path):
    """Create a task via JSONTasksRepository, then load it back."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AICC_TASKS_BACKEND", None)
        from command_center import models
        from command_center.tasks_repository import get_repository, new_task_record
        repo = get_repository(tmp_path)
        record = new_task_record("AICC", "Test task", "task", "Backlog")
        repo.create(record)
        tasks = repo.load_all()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Test task"
```

- [ ] **Step 3.2: Run tests — expect failures**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_tasks_backend_routing.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'command_center.tasks_repository' has no attribute 'get_repository'`

- [ ] **Step 3.3: Add `get_repository` factory to `tasks_repository.py`**

Add at the END of the existing `command_center/tasks_repository.py` (after the `task_label` function):

```python
# ---------------------------------------------------------------------------
# Port interface and factory
# ---------------------------------------------------------------------------

import os as _os


class JSONTasksRepository:
    """Thin wrapper around the module-level JSON functions, implementing the TasksPort contract."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def load_all(self) -> list[dict]:
        return load_tasks(self._root)

    def create(self, task_dict: dict) -> dict:
        task_id = task_dict.get("id")
        if not task_id:
            raise ValueError("task_dict must have an 'id' field")

        def _mutator(tasks: list[dict]) -> dict:
            if any(t.get("id") == task_id for t in tasks):
                raise ValueError(f"refusing to create task with colliding id: {task_id!r}")
            tasks.append(task_dict)
            return task_dict

        return mutate_tasks(self._root, _mutator)

    def upsert(self, task_dict: dict) -> None:
        upsert_task(self._root, task_dict)

    def update_status(self, task_id: str, new_status: str) -> dict | None:
        return update_task_status(self._root, task_id, new_status)

    def delete(self, task_id: str) -> bool:
        return delete_task(self._root, task_id)


def get_repository(root: Path) -> "JSONTasksRepository | AIOSTasksRepository":  # type: ignore[name-defined]
    """Return the active task store backend.

    ``AICC_TASKS_BACKEND=json`` (default) → ``JSONTasksRepository``
    ``AICC_TASKS_BACKEND=aios`` → ``AIOSTasksRepository`` (requires AICC_AIOS_URL + AICC_AIOS_TOKEN)
    """
    backend = _os.environ.get("AICC_TASKS_BACKEND", "json").lower()
    if backend == "aios":
        url = _os.environ.get("AICC_AIOS_URL")
        token = _os.environ.get("AICC_AIOS_TOKEN")
        if not url:
            raise RuntimeError(
                "AICC_TASKS_BACKEND=aios requires AICC_AIOS_URL to be set"
            )
        if not token:
            raise RuntimeError(
                "AICC_TASKS_BACKEND=aios requires AICC_AIOS_TOKEN to be set"
            )
        from aios_sdk import AIOSClient  # local import: only when AIOS backend requested
        from command_center.application.aios_tasks import AIOSIdMap, AIOSTasksRepository
        client = AIOSClient(url, token=token)
        id_map = AIOSIdMap(storage.resolve_data_dir(root) / "aios_task_map.json")
        return AIOSTasksRepository(client, id_map)
    return JSONTasksRepository(root)
```

- [ ] **Step 3.4: Add `aios-sdk` to `requirements.txt`**

```
streamlit>=1.50,<2.0
PyYAML>=6.0,<7.0
aios-sdk @ file:///Users/dmitrijcernikov/Projects/aios#egg=aios-sdk&subdirectory=.
```

Install it:

```bash
cd ~/Projects/ai-command-center && pip install -e ~/Projects/aios --quiet
```

- [ ] **Step 3.5: Run routing tests**

```bash
cd ~/Projects/ai-command-center && python -m pytest tests/test_tasks_backend_routing.py -v
```

Expected: all PASS.

- [ ] **Step 3.6: Run the full test suite — no regressions**

```bash
cd ~/Projects/ai-command-center && python -m pytest --tb=short -q
```

Expected: same pass count as before (all prior tests still pass; only new tests added).

- [ ] **Step 3.7: Commit**

```bash
cd ~/Projects/ai-command-center && git add command_center/tasks_repository.py requirements.txt tests/test_tasks_backend_routing.py
git commit -m "feat(tasks): get_repository() factory — AICC_TASKS_BACKEND env-flag routing"
```

---

## Task 4: Migration script — bulk import tasks.json → AIOS

**Files:**
- Create: `scripts/migrate_tasks_to_aios.py`

**Interfaces:**
- Consumes: `load_tasks(root)` (JSON backend), `AIOSTasksRepository.create()` (Task 2)
- Produces: `data/aios_task_map.json` populated with all migrated IDs

- [ ] **Step 4.1: Write the migration script**

Create `scripts/migrate_tasks_to_aios.py`:

```python
#!/usr/bin/env python3
"""One-shot migration: import all tasks from data/tasks.json into the AIOS Tasks API.

Usage:
    python scripts/migrate_tasks_to_aios.py [--dry-run] [--root PATH]

Environment variables required:
    AICC_AIOS_URL    — base URL of the AIOS API (e.g. https://aios.example.com)
    AICC_AIOS_TOKEN  — bearer token for authentication
    AICC_AIOS_TENANT_ID — tenant id (informational only; token encodes the tenant)

Idempotent: tasks whose AICC id is already in data/aios_task_map.json are skipped.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Resolve project root (one level up from scripts/)
_DEFAULT_ROOT = Path(__file__).parent.parent


def main(root: Path, *, dry_run: bool) -> int:
    url = os.environ.get("AICC_AIOS_URL")
    token = os.environ.get("AICC_AIOS_TOKEN")
    if not url or not token:
        logger.error("AICC_AIOS_URL and AICC_AIOS_TOKEN must be set")
        return 1

    from aios_sdk import AIOSClient
    from command_center import storage
    from command_center.application.aios_tasks import AIOSIdMap, AIOSTasksRepository
    from command_center.tasks_repository import load_tasks

    tasks = load_tasks(root)
    logger.info("Found %d tasks in tasks.json", len(tasks))

    data_dir = storage.resolve_data_dir(root)
    id_map = AIOSIdMap(data_dir / "aios_task_map.json")

    skipped = 0
    migrated = 0
    failed = 0

    if not dry_run:
        client = AIOSClient(url, token=token)
        repo = AIOSTasksRepository(client, id_map)

    for task in tasks:
        aicc_id = task.get("id", "")
        if not aicc_id:
            logger.warning("Skipping task with no id: %r", task.get("title"))
            skipped += 1
            continue
        if id_map.get(aicc_id):
            logger.debug("Already migrated: %s", aicc_id)
            skipped += 1
            continue
        if dry_run:
            logger.info("[DRY-RUN] Would migrate: %s — %s", aicc_id, task.get("title"))
            migrated += 1
            continue
        try:
            created = repo.create(task)
            logger.info("Migrated %s → %s (%s)", aicc_id, created.get("aios_id"), task.get("title"))
            migrated += 1
        except Exception as exc:
            logger.error("Failed to migrate %s: %s", aicc_id, exc)
            failed += 1

    logger.info("Done. migrated=%d  skipped=%d  failed=%d", migrated, skipped, failed)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, do nothing")
    parser.add_argument("--root", type=Path, default=_DEFAULT_ROOT, help="Project root directory")
    args = parser.parse_args()
    sys.exit(main(args.root, dry_run=args.dry_run))
```

- [ ] **Step 4.2: Verify dry-run works without a live AIOS server**

```bash
cd ~/Projects/ai-command-center && AICC_AIOS_URL=https://example.test AICC_AIOS_TOKEN=tok python scripts/migrate_tasks_to_aios.py --dry-run 2>&1 | head -15
```

Expected: logs task count + `[DRY-RUN] Would migrate:` lines, exits 0.

- [ ] **Step 4.3: Commit**

```bash
cd ~/Projects/ai-command-center && git add scripts/migrate_tasks_to_aios.py
git commit -m "feat(tasks): one-shot migration script tasks.json → AIOS API"
```

---

## Task 5: Update callers — app.py and task_import.py

**Files:**
- Modify: `app.py`
- Modify: `command_center/task_import.py`

This task wires `get_repository(root)` into the application layer so the flag actually takes effect at runtime. All existing unit tests must pass unchanged.

- [ ] **Step 5.1: Identify all direct `tasks_repository.*` call sites in `app.py`**

```bash
cd ~/Projects/ai-command-center && grep -n "tasks_repository\." app.py | head -30
```

- [ ] **Step 5.2: Update `app.py` — add repository factory call**

In `app.py`, find where `tasks_repository` functions are called (e.g., `tasks_repository.load_tasks(ROOT)`, `tasks_repository.create_task(ROOT, ...)`, etc.). The pattern is:

```python
# Before (add once, near the top of any function that uses the task store):
repo = tasks_repository.get_repository(ROOT)

# Then replace each call:
# tasks_repository.load_tasks(ROOT) → repo.load_all()
# tasks_repository.create_task(ROOT, ...) → repo.create(new_task_record(...))
# tasks_repository.upsert_task(ROOT, task) → repo.upsert(task)
# tasks_repository.update_task_status(ROOT, task_id, status) → repo.update_status(task_id, status)
# tasks_repository.delete_task(ROOT, task_id) → repo.delete(task_id)
```

Run grep to find exact lines, then apply the replacements. Keep `new_task_record(...)` calls unchanged — it's a factory, not a repository function.

- [ ] **Step 5.3: Update `command_center/task_import.py` — use repository factory**

```bash
cd ~/Projects/ai-command-center && grep -n "tasks_repository\.\|mutate_tasks\|load_tasks\|save_tasks" command_center/task_import.py | head -20
```

Replace the direct `mutate_tasks` call in `apply_task_package` with `get_repository(root).create(...)` per task.

- [ ] **Step 5.4: Run full test suite**

```bash
cd ~/Projects/ai-command-center && python -m pytest --tb=short -q
```

Expected: same or higher pass count; no regressions.

- [ ] **Step 5.5: Verify the app launches with JSON backend**

```bash
cd ~/Projects/ai-command-center && python -c "from app import *; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 5.6: Commit**

```bash
cd ~/Projects/ai-command-center && git add app.py command_center/task_import.py
git commit -m "feat(tasks): wire app.py + task_import.py through get_repository() factory"
```

---

## Task 6: Boundary gate verification + branch push

**Files:** None new; verification pass only.

- [ ] **Step 6.1: Run boundary gate scanner**

```bash
cd ~/Projects/ai-command-center && python -m tests.architecture.aios_boundary
```

Expected: zero drift (no new engine signatures added).

- [ ] **Step 6.2: Run full test suite one final time**

```bash
cd ~/Projects/ai-command-center && python -m pytest -v --tb=short 2>&1 | tail -20
```

Expected: all pass, no regressions vs. main.

- [ ] **Step 6.3: Check git log**

```bash
cd ~/Projects/ai-command-center && git log --oneline main..HEAD
```

Expected: 5–6 commits from this sprint, all on `feat/tasks-aios-backend`.

- [ ] **Step 6.4: Push branch**

```bash
cd ~/Projects/ai-command-center && git push -u origin feat/tasks-aios-backend
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ AICC↔AIOS field mapping (Task 1)
- ✅ State machine bridging (Backlog/Next→open, In Progress/Review→in_progress, Done→completed) (Task 1)
- ✅ ID map file for AICC uuid → AIOS id bridging (Task 2)
- ✅ Full CRUD: load, create, upsert, update_status, delete (Task 2)
- ✅ Feature flag `AICC_TASKS_BACKEND=json|aios` (Task 3)
- ✅ Fail-closed when AIOS backend requested but URL/token missing (Task 3)
- ✅ JSON backend unchanged — zero behavior change (Task 3 tests)
- ✅ One-shot migration script with dry-run (Task 4)
- ✅ Callers updated (Task 5)
- ✅ Boundary gate passes (Task 6)

**Placeholder scan:** None found — all steps have concrete code.

**Type consistency:**
- `get_repository(root)` → returns `JSONTasksRepository | AIOSTasksRepository` (both have `.load_all() / .create() / .upsert() / .update_status() / .delete()`)
- `aicc_dict_to_create_request(task_dict) -> tuple[CreateTaskRequest, str]` used in Task 2 (`AIOSTasksRepository.create`)
- `aios_task_to_aicc_dict(task: Task) -> dict` used in Task 2 (`load_all`, `create`)
- `AIOSIdMap(path)` — `.get() / .put() / .remove()` used in Task 2 and Task 3 factory
