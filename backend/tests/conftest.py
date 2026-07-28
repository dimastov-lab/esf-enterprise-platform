"""Pytest fixtures with per-test transaction isolation.

Each test runs inside a SAVEPOINT-wrapped transaction that is rolled back at the
end, so the regression suite leaves the dev database unchanged and is repeatable.
"""
# ENVIRONMENT now defaults to "production" (safe-by-default); the test app needs
# the development profile (dev-admin seed, non-secure cookies). Set it BEFORE any
# app import so app.core.config picks it up.
import os

os.environ.setdefault("ENVIRONMENT", "development")

import re  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.core import ratelimit
from app.db.session import engine, get_db
from app.main import app
from app.services.auth_service import ROLE_ADMIN, ROLE_ISSUER, AuthService


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    ratelimit.clear_all()
    yield
    ratelimit.clear_all()


@pytest.fixture
def db_session():
    connection = engine.connect()
    trans = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def override_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def seed_users(db_session):
    svc = AuthService(db_session)
    svc.create_user("t_admin", "pw", ROLE_ADMIN, enforce_password_policy=False)
    svc.create_user("t_issuer", "pw", ROLE_ISSUER, enforce_password_policy=False)
    db_session.commit()


def _login(username):
    c = TestClient(app)
    r = c.post("/login", data={"username": username, "password": "pw"})
    assert r.status_code in (200, 303)
    # Fetch the session CSRF token and attach it as a default header for all POSTs.
    # The hidden form input only renders when the dashboard has rows, so on a fresh
    # database fall back to the always-present `var CSRF = "..."` JS token.
    text = c.get("/dashboard").text
    m = (re.search(r'name="csrf_token" value="([^"]+)"', text)
         or re.search(r'var CSRF = "([^"]+)"', text))
    if m:
        c.headers["X-CSRF-Token"] = m.group(1)
    return c


@pytest.fixture
def admin(override_db, seed_users):
    return _login("t_admin")


@pytest.fixture
def issuer(override_db, seed_users):
    return _login("t_issuer")


@pytest.fixture
def issuer2(override_db, seed_users, db_session):
    """A SECOND issuer, for cross-user (IDOR) denial tests."""
    AuthService(db_session).create_user(
        "t_issuer2", "pw", ROLE_ISSUER, enforce_password_policy=False)
    db_session.commit()
    return _login("t_issuer2")


@pytest.fixture
def anon(override_db):
    return TestClient(app, follow_redirects=False)
