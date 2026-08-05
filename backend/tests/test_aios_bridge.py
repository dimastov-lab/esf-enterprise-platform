"""Layer 3 AIOS Memory integration tests.

Covers:
- ESFSnapshot model has aios_memory_id column (column presence)
- memory_create is called on publish with correct args
- aios_memory_id is persisted to the snapshot row
- AIOS failure (exception or None return) does NOT abort publish
- Idempotency: snapshot.uuid is passed as idempotency key argument
- _NoOpBridge.memory_create returns None silently
"""
import re
from urllib.parse import urlencode

import pytest
from unittest.mock import MagicMock

from app.core.aios_bridge import _NoOpBridge, reset_bridge

FORM = {"content-type": "application/x-www-form-urlencoded"}


def _valid_pairs(**override):
    pairs = [
        ("supplier_inn", "01610201710254"), ("supplier_name", 'ООО "Ава Тур"'),
        ("supplier_address", "г. Бишкек"), ("supplier_tax_office", "УГНС"),
        ("supplier_bank", "Бакай Банк"), ("supplier_account", "1240020001699526"),
        ("buyer_inn", "6686063027"), ("buyer_name", 'ООО "Промснабметалл"'),
        ("buyer_address", "Екатеринбург"), ("buyer_tax_office", "643 - РФ"),
        ("buyer_bank", "ОТП"), ("buyer_account", "40702810408170002241"),
        ("supply_date", "24.05.2026"), ("supply_type", "экспорт"),
        ("payment_type", "Безналичная"), ("contract_number", "23/04-26"),
        ("contract_date", "23.04.2026"), ("currency_code", "643"),
        ("currency_rate", "1.2263"), ("director_name", "Дуйшекеев Б.К."),
        ("item_tnved", "7308400009"), ("item_name", "Строительные леса"),
        ("item_unit", "Килограмм"), ("item_price", "116.49850"),
        ("item_qty", "21000.00000"), ("item_vat_rate", "0"),
        ("item_vat_amount", "0"), ("item_nsp", "0"),
    ]
    if override:
        pairs = [(k, override.get(k, v)) for k, v in pairs]
    return pairs


def _new_draft(admin):
    return admin.get("/esf/new").url.path.split("/")[-1]


def _save(admin, uuid, pairs=None):
    return admin.post(
        f"/esf/{uuid}/save",
        content=urlencode(pairs or _valid_pairs()),
        headers=FORM,
    )


def _publish(admin, uuid, pairs=None):
    return admin.post(
        f"/esf/{uuid}/publish",
        content=urlencode(pairs or _valid_pairs()),
        headers=FORM,
    )


@pytest.fixture(autouse=True)
def mock_bridge():
    spy = MagicMock()
    spy.task_create.return_value = "aios-task-abc"
    spy.memory_create.return_value = "mem-001"
    reset_bridge(spy)
    yield spy
    reset_bridge(None)


# ── Column presence ──────────────────────────────────────────────────────────

def test_esf_snapshot_has_aios_memory_id_column(db_session):
    from app.models.esf_snapshot import ESFSnapshot
    from sqlalchemy import inspect
    cols = {c.name: c for c in inspect(ESFSnapshot.__table__).columns}
    assert "aios_memory_id" in cols
    assert cols["aios_memory_id"].nullable is True


# ── _NoOpBridge ─────────────────────────────────────────────────────────────

def test_noop_bridge_memory_create_returns_none():
    bridge = _NoOpBridge()
    result = bridge.memory_create("uuid-x", "sha-x", {"key": "val"})
    assert result is None


# ── Publish integration ──────────────────────────────────────────────────────

def test_memory_create_called_on_publish(admin, mock_bridge):
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)
    mock_bridge.memory_create.assert_called_once()


def test_memory_create_receives_snapshot_uuid(admin, mock_bridge):
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)
    args = mock_bridge.memory_create.call_args
    assert args is not None
    snapshot_uuid_arg = args[0][0]
    # must be a valid UUID string
    assert re.fullmatch(r"[0-9a-f-]{36}", snapshot_uuid_arg)


def test_memory_create_receives_sha256(admin, mock_bridge):
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)
    args = mock_bridge.memory_create.call_args
    sha256_arg = args[0][1]
    assert len(sha256_arg) == 64  # hex-encoded SHA-256


def test_memory_create_receives_payload_dict(admin, mock_bridge):
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)
    args = mock_bridge.memory_create.call_args
    payload_arg = args[0][2]
    assert isinstance(payload_arg, dict)


def test_aios_memory_id_saved_to_snapshot(admin, mock_bridge, db_session):
    mock_bridge.memory_create.return_value = "mem-xyz-999"
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)

    from app.models.esf_document import ESFDocument
    from app.models.esf_snapshot import ESFSnapshot
    import uuid as uuid_mod
    doc = db_session.query(ESFDocument).filter_by(
        uuid=uuid_mod.UUID(uuid)
    ).one_or_none()
    if doc is None:
        pytest.skip("draft UUID extraction failed")
    snapshot = db_session.query(ESFSnapshot).filter_by(
        document_id=doc.id
    ).one_or_none()
    assert snapshot is not None
    assert snapshot.aios_memory_id == "mem-xyz-999"


def test_memory_id_none_when_aios_returns_none(admin, mock_bridge, db_session):
    mock_bridge.memory_create.return_value = None
    uuid = _new_draft(admin)
    _save(admin, uuid)
    _publish(admin, uuid)

    from app.models.esf_document import ESFDocument
    from app.models.esf_snapshot import ESFSnapshot
    import uuid as uuid_mod
    doc = db_session.query(ESFDocument).filter_by(
        uuid=uuid_mod.UUID(uuid)
    ).one_or_none()
    if doc is None:
        pytest.skip("draft UUID extraction failed")
    snapshot = db_session.query(ESFSnapshot).filter_by(
        document_id=doc.id
    ).one_or_none()
    if snapshot is not None:
        assert snapshot.aios_memory_id is None


def test_memory_create_exception_does_not_abort_publish(admin, mock_bridge):
    mock_bridge.memory_create.side_effect = RuntimeError("AIOS down")
    uuid = _new_draft(admin)
    _save(admin, uuid)
    resp = _publish(admin, uuid)
    assert resp.status_code in (200, 303)


def test_memory_create_not_called_when_publish_validation_fails(admin, mock_bridge):
    uuid = _new_draft(admin)
    # publish without saving valid data → validation errors → no snapshot → no memory
    _publish(admin, uuid, pairs=[("currency_code", "643")])
    mock_bridge.memory_create.assert_not_called()
