"""Tests for Argon2id migration and /auth/token JWT endpoint."""
import pytest

from app.core.jwt import create_access_token, decode_access_token
from app.core.passwords import hash_password, needs_rehash, verify_password

# ---------------------------------------------------------------------------
# Argon2id hashing
# ---------------------------------------------------------------------------

class TestPasswords:
    def test_hash_and_verify(self):
        h = hash_password("correct-horse-battery")
        assert verify_password("correct-horse-battery", h)

    def test_wrong_password_rejected(self):
        h = hash_password("correct-horse-battery")
        assert not verify_password("wrong-password", h)

    def test_empty_hash_rejected(self):
        assert not verify_password("anything", "")

    def test_new_hash_does_not_need_rehash(self):
        h = hash_password("correct-horse-battery")
        assert not needs_rehash(h)

    def test_bcrypt_hash_detected_as_legacy(self):
        import bcrypt
        legacy = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
        assert needs_rehash(legacy)

    def test_bcrypt_hash_verifiable(self):
        import bcrypt
        raw = "correct-horse-battery"
        legacy = bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt()).decode()
        assert verify_password(raw, legacy)
        assert not verify_password("wrong", legacy)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

class TestJWT:
    def test_roundtrip(self):
        token = create_access_token(42)
        assert decode_access_token(token) == 42

    def test_tampered_token_rejected(self):
        import jwt as pyjwt
        token = create_access_token(1)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(tampered)

    def test_expired_token_rejected(self):
        import datetime

        import jwt as pyjwt

        from app.core.config import settings
        past = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        token = pyjwt.encode(
            {"sub": "1", "iat": past, "exp": past + datetime.timedelta(minutes=1)},
            settings.effective_jwt_secret,
            algorithm="HS256",
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(token)


# ---------------------------------------------------------------------------
# /auth/token endpoint
# ---------------------------------------------------------------------------

class TestTokenEndpoint:
    def test_valid_credentials_return_bearer(self, anon, seed_users):
        resp = anon.post(
            "/auth/token",
            data={"username": "t_admin", "password": "pw"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert "access_token" in body
        assert body["expires_in"] == 3600  # default 60 min

    def test_wrong_password_returns_401(self, anon, seed_users):
        resp = anon.post(
            "/auth/token",
            data={"username": "t_admin", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_nonexistent_user_returns_401(self, anon):
        resp = anon.post(
            "/auth/token",
            data={"username": "ghost", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_token_decodes_to_correct_user(self, anon, seed_users, db_session):
        resp = anon.post(
            "/auth/token",
            data={"username": "t_admin", "password": "pw"},
        )
        assert resp.status_code == 200
        from app.core.jwt import decode_access_token
        from app.models import User
        user_id = decode_access_token(resp.json()["access_token"])
        user = db_session.query(User).filter_by(id=user_id).one()
        assert user.username == "t_admin"

    def test_rate_limit_on_token_endpoint(self, anon):
        for _ in range(10):
            anon.post("/auth/token", data={"username": "probe", "password": "bad"})
        resp = anon.post("/auth/token", data={"username": "probe", "password": "bad"})
        assert resp.status_code == 429
