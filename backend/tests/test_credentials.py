"""Tests for long-lived API credential PG-store.

Covers:
- CredentialService: issue, validate, revoke, list, revoke_all
- /auth/credentials endpoints: POST, GET, DELETE
- security.py: esf_-prefixed bearer accepted by get_current_api_user
"""
import pytest
from fastapi.testclient import TestClient

from app.services.auth_service import ROLE_ADMIN, AuthService
from app.services.credential_service import CredentialService, _hash_token


# ---------------------------------------------------------------------------
# CredentialService unit tests (db_session, no HTTP)
# ---------------------------------------------------------------------------

class TestCredentialService:
    def test_issue_returns_raw_token_with_prefix(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user, label="test")
        assert raw.startswith("esf_")
        assert len(raw) > 10

    def test_token_not_stored_plaintext(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user)
        # The stored hash must NOT equal the raw token
        assert cred.token_hash != raw
        assert cred.token_hash == _hash_token(raw)

    def test_validate_active_credential(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user)
        found = svc.validate(raw)
        assert found is not None
        assert found.id == cred.id

    def test_validate_unknown_token_returns_none(self, db_session):
        svc = CredentialService(db_session)
        assert svc.validate("esf_totallyunknown") is None

    def test_validate_non_prefixed_token_returns_none(self, db_session):
        svc = CredentialService(db_session)
        assert svc.validate("some-jwt-looking-string") is None

    def test_validate_updates_last_used_at(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user)
        assert cred.last_used_at is None
        svc.validate(raw)
        db_session.refresh(cred)
        assert cred.last_used_at is not None

    def test_revoke_credential(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user)
        ok = svc.revoke(cred.id, user)
        assert ok is True
        assert svc.validate(raw) is None

    def test_revoke_wrong_user_returns_false(self, db_session, seed_users):
        from app.models import User
        admin = db_session.query(User).filter_by(username="t_admin").one()
        issuer = db_session.query(User).filter_by(username="t_issuer").one()
        svc = CredentialService(db_session)
        cred, _ = svc.issue(admin)
        assert svc.revoke(cred.id, issuer) is False

    def test_revoke_already_revoked_returns_false(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, _ = svc.issue(user)
        svc.revoke(cred.id, user)
        assert svc.revoke(cred.id, user) is False

    def test_expired_credential_inactive(self, db_session, seed_users):
        from datetime import datetime, timedelta
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user, expires_in_days=0)
        # Force expiry in the past
        from app.repositories.credential_repository import CredentialRepository
        repo = CredentialRepository(db_session)
        cred.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db_session.commit()
        assert svc.validate(raw) is None
        assert not cred.is_active

    def test_no_expiry_credential_stays_active(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user, expires_in_days=None)
        assert cred.expires_at is None
        assert cred.is_active
        assert svc.validate(raw) is not None

    def test_list_for_user(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        svc.issue(user, label="a")
        svc.issue(user, label="b")
        creds = svc.list_for_user(user)
        assert len(creds) == 2

    def test_revoke_all_for_user(self, db_session, seed_users):
        from app.models import User
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        svc.issue(user, label="x")
        svc.issue(user, label="y")
        count = svc.revoke_all_for_user(user)
        assert count == 2
        for c in svc.list_for_user(user):
            assert c.revoked_at is not None


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

def _get_bearer_client(anon, username="t_admin"):
    """Return (TestClient with Bearer header, token)."""
    resp = anon.post("/auth/token", data={"username": username, "password": "pw"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    # Clone headers so we don't mutate the shared client
    from fastapi.testclient import TestClient
    from app.main import app as _app
    c = TestClient(_app)
    c.headers["Authorization"] = f"Bearer {token}"
    return c, token


class TestCredentialEndpoints:
    def test_issue_credential_requires_auth(self, anon):
        resp = anon.post("/auth/credentials")
        assert resp.status_code == 401

    def test_issue_credential_returns_token(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        resp = client.post("/auth/credentials", data={"label": "CI pipeline"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token"].startswith("esf_")
        assert body["label"] == "CI pipeline"
        assert "note" in body

    def test_issue_credential_without_expiry(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        resp = client.post("/auth/credentials")
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is None

    def test_issue_credential_with_expiry(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        resp = client.post("/auth/credentials", data={"expires_in_days": "30"})
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is not None

    def test_list_credentials(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        client.post("/auth/credentials", data={"label": "first"})
        client.post("/auth/credentials", data={"label": "second"})
        resp = client.get("/auth/credentials")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        labels = {i["label"] for i in items}
        assert "first" in labels
        assert "second" in labels

    def test_list_does_not_expose_raw_token(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        client.post("/auth/credentials", data={"label": "secret"})
        resp = client.get("/auth/credentials")
        body = str(resp.json())
        assert "esf_" not in body

    def test_revoke_credential(self, anon, override_db, seed_users, db_session):
        client, _ = _get_bearer_client(anon)
        issue_resp = client.post("/auth/credentials", data={"label": "to revoke"})
        cred_id = issue_resp.json()["id"]
        raw_token = issue_resp.json()["token"]

        # Revoke it
        del_resp = client.delete(f"/auth/credentials/{cred_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["revoked"] is True

        # Validate should return None now
        svc = CredentialService(db_session)
        assert svc.validate(raw_token) is None

    def test_revoke_nonexistent_returns_404(self, anon, override_db, seed_users):
        client, _ = _get_bearer_client(anon)
        resp = client.delete("/auth/credentials/999999")
        assert resp.status_code == 404

    def test_issued_credential_authenticates_api(self, anon, override_db, seed_users):
        """An esf_-prefixed credential issued via the endpoint can authenticate other API calls."""
        client, _ = _get_bearer_client(anon)
        issue_resp = client.post("/auth/credentials", data={"label": "api"})
        raw_token = issue_resp.json()["token"]

        # Use the long-lived credential to authenticate another call
        from fastapi.testclient import TestClient
        from app.main import app as _app
        api_client = TestClient(_app)
        api_client.headers["Authorization"] = f"Bearer {raw_token}"
        list_resp = api_client.get("/auth/credentials")
        assert list_resp.status_code == 200

    def test_revoked_credential_rejected_by_api(self, anon, override_db, seed_users, db_session):
        client, _ = _get_bearer_client(anon)
        issue_resp = client.post("/auth/credentials", data={"label": "revokeme"})
        cred_id = issue_resp.json()["id"]
        raw_token = issue_resp.json()["token"]

        # Revoke then try to use
        client.delete(f"/auth/credentials/{cred_id}")

        from fastapi.testclient import TestClient
        from app.main import app as _app
        api_client = TestClient(_app)
        api_client.headers["Authorization"] = f"Bearer {raw_token}"
        resp = api_client.get("/auth/credentials")
        assert resp.status_code == 401
