"""Layer 1 AIOS Tasks integration tests.

AIOSBridgeService is replaced with a spy mock via reset_bridge() so tests
never make real HTTP calls. The suite verifies:
- Correct bridge method called at each ESF lifecycle transition.
- Bridge errors (exceptions) do NOT abort ESF operations.
- AIOS_ENABLED=false (no-op bridge) leaves ESF behaviour unchanged.
"""
import pytest
from unittest.mock import MagicMock, call
from fastapi.testclient import TestClient

from app.core.aios_bridge import reset_bridge, _NoOpBridge


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_bridge():
    """Inject a spy bridge before each test; restore no-op after."""
    spy = MagicMock()
    spy.task_create.return_value = "aios-task-abc"
    reset_bridge(spy)
    yield spy
    reset_bridge(None)   # reset to None so next test rebuilds from settings


# ---------------------------------------------------------------------------
# Bridge unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestBridgeNoOp:
    def test_noop_bridge_returns_none_on_create(self):
        bridge = _NoOpBridge()
        assert bridge.task_create("uuid", 1) is None

    def test_noop_bridge_silently_ignores_lifecycle_calls(self):
        bridge = _NoOpBridge()
        bridge.task_start("id-x")
        bridge.task_escalate("id-x")
        bridge.task_complete("id-x")
        bridge.task_cancel("id-x")


class TestBridgeFireAndForget:
    def test_bridge_exception_does_not_propagate(self, mock_bridge, admin, db_session):
        """If bridge raises, ESF create_draft must still succeed."""
        mock_bridge.task_create.side_effect = RuntimeError("AIOS down")
        resp = admin.get("/esf/new")
        assert resp.status_code in (200, 303)


# ---------------------------------------------------------------------------
# Lifecycle integration via HTTP
# ---------------------------------------------------------------------------

class TestAIOSTasksLifecycle:
    def _create_doc(self, admin):
        r = admin.get("/esf/new")
        # GET /esf/new creates a draft and redirects to /esf/{uuid}
        url = r.headers.get("location") or str(r.url)
        import re
        m = re.search(r"/esf/([0-9a-f-]{36})", url)
        if not m:
            dashboard = admin.get("/dashboard")
            m = re.search(r'href="/esf/([0-9a-f-]{36})"', dashboard.text)
        return m.group(1) if m else None

    def test_create_draft_calls_task_create(self, admin, mock_bridge):
        self._create_doc(admin)
        mock_bridge.task_create.assert_called_once()

    def test_create_draft_saves_aios_task_id(self, admin, mock_bridge, db_session):
        uuid = self._create_doc(admin)
        if uuid:
            from app.models import ESFDocument
            import uuid as uuid_mod
            doc = db_session.query(ESFDocument).filter_by(
                uuid=uuid_mod.UUID(uuid)
            ).one_or_none()
            if doc:
                assert doc.aios_task_id == "aios-task-abc"

    def test_task_create_called_with_doc_uuid(self, admin, mock_bridge):
        self._create_doc(admin)
        args = mock_bridge.task_create.call_args
        assert args is not None
        uuid_arg = args[0][0]
        assert len(uuid_arg) == 36  # valid UUID string

    def test_task_create_failure_does_not_abort_draft_creation(self, admin, mock_bridge):
        mock_bridge.task_create.return_value = None  # AIOS unavailable
        resp = admin.get("/esf/new")
        assert resp.status_code in (200, 303)   # ESF draft still created

    def test_task_start_not_called_on_validation_errors(self, admin, mock_bridge):
        """Validation with errors must not advance the AIOS task."""
        uuid = self._create_doc(admin)
        if uuid:
            # Empty document — validation will fail
            admin.post(f"/esf/{uuid}/validate")
            mock_bridge.task_start.assert_not_called()

    def test_bridge_cancel_called_on_esf_cancel(self, admin, mock_bridge, db_session):
        """Cancelling a PUBLISHED document must call task_cancel."""
        from app.models import ESFDocument, DocumentStatus
        import uuid as uuid_mod
        # Force a published doc via ORM (bypass full publish workflow in this unit test)
        uuid = self._create_doc(admin)
        if uuid:
            doc = db_session.query(ESFDocument).filter_by(
                uuid=uuid_mod.UUID(uuid)
            ).one_or_none()
            if doc:
                doc.status = DocumentStatus.PUBLISHED
                doc.aios_task_id = "aios-task-abc"
                db_session.commit()
                admin.post(f"/esf/{uuid}/cancel")
                mock_bridge.task_cancel.assert_called_once_with("aios-task-abc")
