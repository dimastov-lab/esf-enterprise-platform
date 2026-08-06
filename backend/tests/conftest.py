"""Pytest fixtures — module-level connection sharing + per-test SAVEPOINT isolation.

v2 architecture:
  _module_conn    module-scoped | one DB connection per module, outer BEGIN tx
  _module_seed    module-scoped | t_admin / t_issuer created once per module
  db_session      function-scoped | SAVEPOINT on _module_conn; rolls back per test
  _admin_state    module-scoped | logs in once, caches cookies + CSRF
  _issuer_state   module-scoped | same for t_issuer
  admin / issuer  function-scoped | fresh TestClient reusing cached credentials
"""
import os
import tempfile

os.environ.setdefault("ENVIRONMENT", "development")
# Disable lock_timeout for tests: module-scoped outer BEGIN transactions hold
# an uncommitted INSERT on t_admin, and parallel workers seeding the same
# username would time out at 5 s. Setting 0 means "wait indefinitely" in PG.
os.environ.setdefault("DB_LOCK_TIMEOUT_MS", "0")

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("QR_STORAGE_DIR", tempfile.mkdtemp(prefix="esf-test-qr-"))

import re  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core import ratelimit  # noqa: E402
import app.core.passwords as _pwd_module  # noqa: E402
from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth_service import ROLE_ADMIN, ROLE_ISSUER, AuthService  # noqa: E402


# ---------------------------------------------------------------------------
# Session-wide: replace production Argon2id with cheap params (18× faster)
# ---------------------------------------------------------------------------

_TEST_PH = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, hash_len=32, salt_len=16)


@pytest.fixture(scope="session", autouse=True)
def _fast_argon2():
    original = _pwd_module._ph
    _pwd_module._ph = _TEST_PH
    yield
    _pwd_module._ph = original


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    ratelimit.clear_all()
    yield
    ratelimit.clear_all()


# ---------------------------------------------------------------------------
# Module-scoped DB infrastructure
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _module_conn():
    """One connection per module with a wrapping outer transaction.
    All per-test SAVEPOINTs nest inside it; ROLLBACK at module end wipes
    seed data without touching the physical database.
    """
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture(scope="module")
def _module_seed(_module_conn):
    """Seed t_admin and t_issuer once per module.

    Uses a nested transaction (SAVEPOINT → RELEASE) so the inserts land in the
    outer BEGIN that _module_conn rolls back at module teardown.
    """
    with _module_conn.begin_nested():          # SAVEPOINT seed_sp
        Session = sessionmaker(bind=_module_conn)
        sess = Session()
        try:
            svc = AuthService(sess)
            svc.create_user("t_admin",  "pw", ROLE_ADMIN,  enforce_password_policy=False)
            svc.create_user("t_issuer", "pw", ROLE_ISSUER, enforce_password_policy=False)
            sess.flush()
        finally:
            sess.close()
    # context-manager __exit__ commits (RELEASE SAVEPOINT) → data in outer BEGIN


# ---------------------------------------------------------------------------
# Per-test DB session — SAVEPOINT on the module connection
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(_module_conn, _module_seed):
    """Function-scoped SAVEPOINT on the module connection.

    Test-written data rolls back to this savepoint on teardown; the seed users
    (written before this savepoint) survive across all tests in the module.
    """
    sp = _module_conn.begin_nested()           # SAVEPOINT sp_test
    Session = sessionmaker(bind=_module_conn)
    session = Session()
    session.begin_nested()                     # inner SAVEPOINT for restart-on-commit

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()
        try:
            sp.rollback()
        except Exception:
            pass   # transaction already deassociated (e.g. DB error in test)


@pytest.fixture
def override_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Module-scoped login cache
# ---------------------------------------------------------------------------

@dataclass
class _LoginState:
    cookies: dict = field(default_factory=dict)
    csrf: str | None = None


def _capture_login(username: str, conn) -> _LoginState:
    """Log in via HTTP once, return cached (cookies, csrf).

    Temporarily overrides get_db so the login request sees users on `conn`.
    Safe within a single worker because module setup is sequential.
    """
    Session = sessionmaker(bind=conn)
    sess = Session()
    try:
        app.dependency_overrides[get_db] = lambda: sess
        c = TestClient(app)
        r = c.post("/login", data={"username": username, "password": "pw"})
        assert r.status_code in (200, 303), f"login failed for {username}: {r.status_code}"
        text = c.get("/dashboard").text
        m = (re.search(r'name="csrf_token" value="([^"]+)"', text)
             or re.search(r'var CSRF = "([^"]+)"', text))
        return _LoginState(cookies=dict(c.cookies), csrf=m.group(1) if m else None)
    finally:
        app.dependency_overrides.pop(get_db, None)
        sess.close()


@pytest.fixture(scope="module")
def _admin_state(_module_conn, _module_seed) -> _LoginState:
    return _capture_login("t_admin", _module_conn)


@pytest.fixture(scope="module")
def _issuer_state(_module_conn, _module_seed) -> _LoginState:
    return _capture_login("t_issuer", _module_conn)


# ---------------------------------------------------------------------------
# Public test fixtures
# ---------------------------------------------------------------------------

def _make_authenticated_client(state: _LoginState) -> TestClient:
    c = TestClient(app)
    c.cookies.update(state.cookies)
    if state.csrf:
        c.headers["X-CSRF-Token"] = state.csrf
    return c


@pytest.fixture
def admin(override_db, _admin_state):
    """Admin TestClient — login is cached per module, DB is per-test."""
    return _make_authenticated_client(_admin_state)


@pytest.fixture
def issuer(override_db, _issuer_state):
    """Issuer TestClient — login is cached per module, DB is per-test."""
    return _make_authenticated_client(_issuer_state)


@pytest.fixture
def issuer2(override_db, db_session):
    """Second issuer for IDOR tests — unique per test, logs in per test."""
    AuthService(db_session).create_user(
        "t_issuer2", "pw", ROLE_ISSUER, enforce_password_policy=False)
    db_session.commit()
    c = TestClient(app)
    r = c.post("/login", data={"username": "t_issuer2", "password": "pw"})
    assert r.status_code in (200, 303)
    text = c.get("/dashboard").text
    m = (re.search(r'name="csrf_token" value="([^"]+)"', text)
         or re.search(r'var CSRF = "([^"]+)"', text))
    if m:
        c.headers["X-CSRF-Token"] = m.group(1)
    return c


@pytest.fixture
def anon(override_db):
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def client(override_db):
    return TestClient(app)


@pytest.fixture
def seed_users(_module_seed):
    """Backward-compat alias — seeding is now module-scoped via _module_seed."""


@pytest.fixture
def auth_headers(client):
    resp = client.post("/auth/token", data={"username": "t_admin", "password": "pw"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
