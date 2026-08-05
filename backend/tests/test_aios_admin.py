"""Tests for GET /admin/aios (AIOS operability status page)."""
import pytest
from unittest.mock import MagicMock

from app.core.aios_bridge import reset_bridge
from app.core.config import settings


@pytest.fixture(autouse=True)
def clean_bridge():
    yield
    reset_bridge(None)


class TestAdminAIOSRoute:
    def test_admin_can_access_aios_page(self, admin):
        resp = admin.get("/admin/aios")
        assert resp.status_code == 200
        assert "AIOS" in resp.text

    def test_issuer_redirected_from_aios_page(self, issuer):
        resp = issuer.get("/admin/aios")
        # require_admin raises 403
        assert resp.status_code == 403

    def test_anon_redirected_from_aios_page(self, anon, override_db, seed_users):
        resp = anon.get("/admin/aios")
        assert resp.status_code in (302, 303)

    def test_page_shows_disabled_when_aios_off(self, admin, monkeypatch):
        monkeypatch.setattr(settings, "AIOS_ENABLED", False)
        resp = admin.get("/admin/aios")
        assert resp.status_code == 200
        assert "выключен" in resp.text

    def test_page_shows_enabled_when_aios_on(self, admin, monkeypatch):
        spy = MagicMock()
        spy.ping.return_value = True
        reset_bridge(spy)
        monkeypatch.setattr(settings, "AIOS_ENABLED", True)
        resp = admin.get("/admin/aios")
        assert resp.status_code == 200
        assert "включён" in resp.text

    def test_page_shows_reachable_when_ping_ok(self, admin, monkeypatch):
        spy = MagicMock()
        spy.ping.return_value = True
        reset_bridge(spy)
        monkeypatch.setattr(settings, "AIOS_ENABLED", True)
        resp = admin.get("/admin/aios")
        assert "доступен" in resp.text
        spy.ping.assert_called_once()

    def test_page_shows_unreachable_when_ping_fails(self, admin, monkeypatch):
        spy = MagicMock()
        spy.ping.return_value = False
        reset_bridge(spy)
        monkeypatch.setattr(settings, "AIOS_ENABLED", True)
        resp = admin.get("/admin/aios")
        assert "недоступен" in resp.text

    def test_page_shows_stats(self, admin):
        resp = admin.get("/admin/aios")
        assert resp.status_code == 200
        # Stats section always rendered
        assert "AIOS Task ID" in resp.text
        assert "AIOS Memory ID" in resp.text

    def test_no_ping_when_aios_disabled(self, admin, monkeypatch):
        spy = MagicMock()
        reset_bridge(spy)
        monkeypatch.setattr(settings, "AIOS_ENABLED", False)
        admin.get("/admin/aios")
        spy.ping.assert_not_called()


class TestAIOSBridgePing:
    def test_noop_bridge_ping_returns_false(self):
        from app.core.aios_bridge import _NoOpBridge
        assert _NoOpBridge().ping() is False
