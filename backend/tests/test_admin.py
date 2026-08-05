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


class TestAdminDeactivate:
    """Tests for admin user deactivation endpoint."""

    def test_deactivate_sets_user_inactive(self, admin, db_session):
        from app.models import User
        from app.services.auth_service import AuthService
        svc = AuthService(db_session)
        target = svc.create_user("to_deactivate", "Password123!", "ISSUER")
        target_id = target.id
        db_session.commit()

        resp = admin.post(f"/admin/users/{target_id}/deactivate",
                          follow_redirects=False)
        assert resp.status_code == 303

        db_session.expire_all()
        updated = db_session.query(User).filter_by(id=target_id).one()
        assert not updated.is_active

    def test_deactivate_nonexistent_user_redirects_with_error(self, admin):
        resp = admin.post("/admin/users/99999/deactivate",
                          follow_redirects=False)
        assert resp.status_code == 303
        assert "error" in resp.headers.get("location", "")

    def test_deactivate_already_inactive_redirects_with_error(
        self, admin, db_session
    ):
        from app.services.auth_service import AuthService
        svc = AuthService(db_session)
        target = svc.create_user("already_inactive", "Password123!", "ISSUER")
        target.is_active = False
        db_session.commit()

        resp = admin.post(f"/admin/users/{target.id}/deactivate",
                          follow_redirects=False)
        assert resp.status_code == 303
        assert "error" in resp.headers.get("location", "")

    def test_deactivate_revokes_credentials_and_records_audit(
        self, admin, db_session
    ):
        from app.models import AuditLog
        from app.services.auth_service import AuthService
        from app.services.credential_service import CredentialService
        svc = AuthService(db_session)
        target = svc.create_user("cred_user", "Password123!", "ISSUER")
        CredentialService(db_session).issue(target, label="test")
        db_session.commit()

        resp = admin.post(f"/admin/users/{target.id}/deactivate",
                          follow_redirects=False)
        assert resp.status_code == 303

        db_session.expire_all()
        row = (
            db_session.query(AuditLog)
            .filter_by(action="CREDENTIAL_REVOKED")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.meta_json.get("deactivated_user_id") == target.id
