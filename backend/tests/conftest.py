"""Pytest fixtures — session-scoped committed seed + per-test SAVEPOINT isolation.

Architecture
============
_session_seed   session, autouse  | INSERT t_admin/t_issuer committed to the real DB.
                                    pg_advisory_xact_lock serialises concurrent workers:
                                    only the first commits; others find the row already
                                    committed and skip.  Lock held for milliseconds only.
db_session      function-scoped   | own connection + SAVEPOINT per test; rolls back all
                                    test-local writes; seed users are visible (committed).
override_db     function-scoped   | wires db_session into get_db
_admin_state    module-scoped     | POST /login once per module (no DB override needed —
                                    t_admin is in the real DB); caches cookies + CSRF
_issuer_state   module-scoped     | same for t_issuer
admin / issuer  function-scoped   | TestClient with cached creds + per-test db_session

Why session-scoped committed seed (not module-scoped)?
  Module-scoped _module_conn holds an open BEGIN transaction for the entire module.
  Parallel xdist workers each INSERT t_admin inside their own open transactions →
  row-lock conflict → LockNotAvailable at 5 s.

  Session-scoped with advisory lock: only the first worker INSERTs and COMMITs
  (releases the row lock in milliseconds).  Later workers find the row already
  committed via the check inside the advisory lock and skip.  Zero lock contention.
"""
import os
import tempfile

os.environ.setdefault("ENVIRONMENT", "development")

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("QR_STORAGE_DIR", tempfile.mkdtemp(prefix="esf-test-qr-"))

import re  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event, text  # noqa: E402
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
# Session-scoped seed — committed to the REAL DB, visible to all workers
# ---------------------------------------------------------------------------

_SEED_LOCK = 987_654_321  # arbitrary pg advisory-lock id


@pytest.fixture(scope="session", autouse=True)
def _session_seed():
    """Commit t_admin / t_issuer once per worker session.

    pg_advisory_xact_lock(id) serialises concurrent xdist workers.
    The first worker to acquire the lock INSERTs and COMMITs (row lock released
    immediately after commit — milliseconds, not seconds).  Subsequent workers
    acquire the lock, find the rows already committed, and skip the INSERT.
    """
    from app.models.user import User

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(f"SELECT pg_advisory_xact_lock({_SEED_LOCK})"))
            sess = sessionmaker(bind=conn)()
            try:
                if not sess.query(User).filter_by(username="t_admin").first():
                    AuthService(sess).create_user(
                        "t_admin", "pw", ROLE_ADMIN, enforce_password_policy=False
                    )
                if not sess.query(User).filter_by(username="t_issuer").first():
                    AuthService(sess).create_user(
                        "t_issuer", "pw", ROLE_ISSUER, enforce_password_policy=False
                    )
                sess.flush()
            finally:
                sess.close()
    yield


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Delete test users after the full run.

    In xdist mode this hook runs in the controller/master process
    (PYTEST_XDIST_WORKER is unset there), which means every worker is already
    done.  In single-process mode it runs once at the end.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE username IN ('t_admin', 't_issuer')")
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-test DB session — own connection + SAVEPOINT isolation
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session(_session_seed):
    """Function-scoped connection; SAVEPOINT rolls back test-local writes.

    Seed users (t_admin, t_issuer) are committed and visible through standard
    MVCC — no special setup needed.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = sessionmaker(bind=conn)()
    session.begin_nested()  # SAVEPOINT — restarted on every commit

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
            trans.rollback()
        except Exception:
            pass
        conn.close()


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


def _capture_login(username: str) -> _LoginState:
    """Log in without overriding get_db.

    t_admin / t_issuer are in the real (committed) DB, so a plain TestClient
    uses the normal connection pool and finds them.
    """
    c = TestClient(app)
    r = c.post("/login", data={"username": username, "password": "pw"})
    assert r.status_code in (200, 303), f"login failed for {username}: {r.status_code}"
    page = c.get("/dashboard").text
    m = re.search(r'name="csrf_token" value="([^"]+)"', page) or re.search(
        r'var CSRF = "([^"]+)"', page
    )
    return _LoginState(cookies=dict(c.cookies), csrf=m.group(1) if m else None)


@pytest.fixture(scope="module")
def _admin_state(_session_seed) -> _LoginState:
    return _capture_login("t_admin")


@pytest.fixture(scope="module")
def _issuer_state(_session_seed) -> _LoginState:
    return _capture_login("t_issuer")


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
    """Admin TestClient — login cached per module; DB isolated per test."""
    return _make_authenticated_client(_admin_state)


@pytest.fixture
def issuer(override_db, _issuer_state):
    """Issuer TestClient — login cached per module; DB isolated per test."""
    return _make_authenticated_client(_issuer_state)


@pytest.fixture
def issuer2(override_db, db_session):
    """Second issuer for IDOR tests — created and logged in per test."""
    AuthService(db_session).create_user(
        "t_issuer2", "pw", ROLE_ISSUER, enforce_password_policy=False
    )
    db_session.commit()
    c = TestClient(app)
    r = c.post("/login", data={"username": "t_issuer2", "password": "pw"})
    assert r.status_code in (200, 303)
    page = c.get("/dashboard").text
    m = re.search(r'name="csrf_token" value="([^"]+)"', page) or re.search(
        r'var CSRF = "([^"]+)"', page
    )
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
def seed_users(_session_seed):
    """Backward-compat alias — seed users are committed at session start."""


@pytest.fixture
def auth_headers(client):
    resp = client.post("/auth/token", data={"username": "t_admin", "password": "pw"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
