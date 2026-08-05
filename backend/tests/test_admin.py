"""Admin route tests — user management."""
import re

import pytest
from fastapi.testclient import TestClient

from app.services.credential_service import CredentialService


class TestDeactivateUser:
    def test_deactivate_sets_inactive(self, anon, override_db, seed_users, db_session):
        from app.models import User
        issuer = db_session.query(User).filter_by(username="t_issuer").one()
        issuer_id = issuer.id

        resp = anon.post("/login", data={"username": "t_admin", "password": "pw"},
                         follow_redirects=False)
        assert resp.status_code in (302, 303)

        page_resp = anon.get("/admin/users")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page_resp.text)
        assert csrf, "csrf_token not found in page"
        token = csrf.group(1)

        resp = anon.post(
            f"/admin/users/{issuer_id}/deactivate",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        db_session.refresh(issuer)
        assert issuer.is_active is False

    def test_deactivate_revokes_credentials(self, anon, override_db, seed_users, db_session):
        from app.models import User
        issuer = db_session.query(User).filter_by(username="t_issuer").one()
        svc = CredentialService(db_session)
        cred, _ = svc.issue(issuer, label="to-be-revoked")
        assert cred.revoked_at is None

        anon.post("/login", data={"username": "t_admin", "password": "pw"},
                  follow_redirects=False)
        page_resp = anon.get("/admin/users")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page_resp.text).group(1)
        anon.post(
            f"/admin/users/{issuer.id}/deactivate",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        db_session.refresh(cred)
        assert cred.revoked_at is not None

    def test_deactivate_requires_admin(self, anon, override_db, seed_users, db_session):
        anon.post("/login", data={"username": "t_issuer", "password": "pw"},
                  follow_redirects=False)
        page_resp = anon.get("/admin/users")
        assert page_resp.status_code == 403
