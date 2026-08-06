"""Layer 2 AIOS Identity integration tests.

Covers:
- async_identity_verify not called when AIOS_ENABLED=false
- async_identity_verify called for non-esf_ Bearer tokens when AIOS_ENABLED=true
- Valid AIOS claims + known username → user returned (200)
- Valid AIOS claims + unknown username → 401 (no fallback to ESF JWT)
- AIOS unavailable (async_identity_verify=None) → fallback to ESF JWT
- esf_ PG credentials not affected by AIOS identity path
- _NoOpBridge.identity_verify / async_identity_verify return None
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.core.aios_bridge import _NoOpBridge, get_bridge, reset_bridge
from app.core.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_client(override_db, seed_users) -> TestClient:
    """Return a bare TestClient (no session cookie, no default headers)."""
    return TestClient(app, raise_server_exceptions=True)


def _jwt_for(anon, username="t_admin") -> str:
    resp = anon.post("/auth/token", data={"username": username, "password": "pw"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# _NoOpBridge
# ---------------------------------------------------------------------------

def test_noop_bridge_identity_verify_returns_none():
    assert _NoOpBridge().identity_verify("any-token") is None


@pytest.mark.anyio
async def test_noop_bridge_async_identity_verify_returns_none():
    assert await _NoOpBridge().async_identity_verify("any-token") is None


# ---------------------------------------------------------------------------
# identity_verify not called when AIOS_ENABLED=false (default)
# ---------------------------------------------------------------------------

def test_identity_verify_not_called_when_aios_disabled(
    anon, override_db, seed_users, monkeypatch
):
    spy = MagicMock()
    spy.async_identity_verify = AsyncMock(return_value={"preferred_username": "t_admin"})
    reset_bridge(spy)
    monkeypatch.setattr(settings, "AIOS_ENABLED", False)
    try:
        token = _jwt_for(anon)
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {token}"
        resp = c.get("/auth/credentials")
        # ESF JWT validated without touching AIOS
        assert resp.status_code == 200
        spy.async_identity_verify.assert_not_called()
    finally:
        reset_bridge(None)


# ---------------------------------------------------------------------------
# AIOS_ENABLED=true: identity path
# ---------------------------------------------------------------------------

class TestAIOSIdentityEnabled:
    @pytest.fixture(autouse=True)
    def enable_aios(self, monkeypatch):
        monkeypatch.setattr(settings, "AIOS_ENABLED", True)

    @pytest.fixture(autouse=True)
    def clean_bridge(self):
        yield
        reset_bridge(None)

    def test_identity_verify_called_for_bearer_token(self, anon, override_db, seed_users):
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(return_value=None)  # unavailable → fallback
        reset_bridge(spy)
        token = _jwt_for(anon)
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {token}"
        c.get("/auth/credentials")
        spy.async_identity_verify.assert_called_once_with(token)

    def test_aios_identity_token_resolves_user(self, anon, override_db, seed_users):
        """A token AIOS validates is mapped to the local user by preferred_username."""
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(
            return_value={"preferred_username": "t_admin", "sub": "x"}
        )
        reset_bridge(spy)
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer some-aios-token"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 200

    def test_aios_identity_via_sub_claim(self, anon, override_db, seed_users):
        """Fallback to sub when preferred_username is absent."""
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(return_value={"sub": "t_admin"})
        reset_bridge(spy)
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer some-aios-token"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 200

    def test_aios_identity_unknown_username_returns_401(self, anon, override_db, seed_users):
        """AIOS verifies token but username has no ESF account → 401, no JWT fallback."""
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(
            return_value={"preferred_username": "ghost@aios.io"}
        )
        reset_bridge(spy)
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer some-aios-token"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 401
        assert "AIOS identity" in resp.json().get("detail", "")

    def test_aios_unavailable_falls_back_to_esf_jwt(self, anon, override_db, seed_users):
        """If AIOS returns None (unreachable), ESF JWT still authenticates the user."""
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(return_value=None)  # AIOS down
        reset_bridge(spy)
        token = _jwt_for(anon)
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {token}"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 200

    def test_esf_credential_not_sent_to_aios_identity(self, anon, override_db, seed_users):
        """esf_-prefixed PG credentials bypass the AIOS identity path entirely."""
        spy = MagicMock()
        spy.task_create.return_value = None
        spy.async_identity_verify = AsyncMock(return_value=None)  # fallback if called
        reset_bridge(spy)
        # Issue a PG credential via session client
        token = _jwt_for(anon)
        session_c = TestClient(app)
        session_c.headers["Authorization"] = f"Bearer {token}"
        cred_resp = session_c.post("/auth/credentials")
        assert cred_resp.status_code == 200
        esf_token = cred_resp.json()["token"]
        # Use the PG credential on a fresh client
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {esf_token}"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 200
        # AIOS identity must NOT have been called for the esf_ token
        for call in spy.async_identity_verify.call_args_list:
            assert not call.args[0].startswith("esf_"), (
                "async_identity_verify must not be called with esf_ credential"
            )

    def test_invalid_token_and_aios_unavailable_returns_401(
        self, anon, override_db, seed_users
    ):
        """Garbage token + AIOS down → both paths fail → 401."""
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(return_value=None)
        reset_bridge(spy)
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer totally-invalid-garbage"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 401
