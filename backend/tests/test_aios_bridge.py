"""Layer 2 AIOS Memory integration tests.

Tests that ESFSnapshot has the aios_memory_id column to support
storing AIOS memory event IDs for audit trail linking.
"""
import pytest


def test_esf_snapshot_has_aios_memory_id_column(db_session):
    """Verify ESFSnapshot has aios_memory_id nullable column."""
    from app.models.esf_snapshot import ESFSnapshot
    from sqlalchemy import inspect
    cols = {c.name: c for c in inspect(ESFSnapshot.__table__).columns}
    assert "aios_memory_id" in cols
    assert cols["aios_memory_id"].nullable is True
