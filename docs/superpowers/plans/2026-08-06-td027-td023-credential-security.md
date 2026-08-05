# TD-027 + TD-023 Credential Security Sprint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close TD-027 (API credential max TTL cap + correct audit actions + revoke-on-deactivate) and TD-023 (AIOS_BASE_URL `https://` enforcement in production).

**Architecture:** Layered — Controller → Service → Repository. No business logic in routers. Cross-service coordination (deactivate user + revoke credentials) belongs at the router level, not inside a service.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, PostgreSQL. No new dependencies.

## Global Constraints

- Architecture rule: no SQL outside repositories; no business logic in controllers.
- All new behaviour is tested with the existing pytest harness (`cd backend && python -m pytest tests/ -q`).
- No TODO/FIXME/HACK in production code.
- Audit writes are best-effort (already implemented in `audit_service.record` — do not change that pattern).
- Existing tests must continue to pass; do not delete or weaken them.
- Work on branch `main` in `/Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter`.

---

### Task 1: TD-023 — AIOS_BASE_URL `https://` enforcement

**Files:**
- Modify: `backend/app/core/config.py` — `Settings.validate_for_runtime()`
- Create: `backend/tests/test_config_validation.py`

**Interfaces:**
- Consumes: existing `Settings.validate_for_runtime()` (lines 129-162) and `Settings.is_production` property (line 125)
- Produces: nothing new — augments existing startup check

**Context:** `validate_for_runtime()` already fails closed on bad `SECRET_KEY` and on `salyk.kg` in `PUBLIC_BASE_URL`. We add a third check: when `AIOS_ENABLED=true` AND the deployment is production (`is_production=True`), reject any `AIOS_BASE_URL` that does not start with `https://`. Dev/test deployments (`ENVIRONMENT=development`) are exempt because `validate_for_runtime` exits early when not production (line 131).

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_config_validation.py`:

```python
"""Tests for Settings.validate_for_runtime() — production safety guards."""
import pytest
from app.core.config import Settings


def _prod_settings(**overrides) -> Settings:
    """Build a Settings-like object in production mode with a valid secret."""
    s = Settings.__new__(Settings)
    s.ENVIRONMENT = "production"
    s.SECRET_KEY = "x" * 64          # 64-char secret — passes existing checks
    s.PUBLIC_BASE_URL = "https://esf.example.com"
    s.AIOS_ENABLED = False
    s.AIOS_BASE_URL = "https://localhost:8100"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_aios_http_url_rejected_in_production():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="http://aios.internal")
    with pytest.raises(RuntimeError, match="https://"):
        s.validate_for_runtime()


def test_aios_https_url_accepted_in_production():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="https://aios.internal")
    s.validate_for_runtime()  # must not raise


def test_aios_http_url_allowed_in_development():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="http://localhost:8100")
    s.ENVIRONMENT = "development"
    s.validate_for_runtime()  # dev mode exits early — must not raise


def test_aios_http_url_allowed_when_aios_disabled():
    s = _prod_settings(AIOS_ENABLED=False, AIOS_BASE_URL="http://localhost:8100")
    s.validate_for_runtime()  # AIOS disabled — check must not fire
```

- [ ] **Step 2: Run test to confirm failure**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_config_validation.py -v
```

Expected: `test_aios_http_url_rejected_in_production` FAILS (no check yet).

- [ ] **Step 3: Add the check to `validate_for_runtime()`**

In `backend/app/core/config.py`, append the following block **inside** `validate_for_runtime()`, after the existing `salyk.kg` check (after line 162):

```python
        if self.AIOS_ENABLED:
            aios_url = (self.AIOS_BASE_URL or "").strip()
            if not aios_url.startswith("https://"):
                raise RuntimeError(
                    "AIOS_BASE_URL must start with https:// when AIOS_ENABLED=true "
                    "and ENVIRONMENT is production. Bearer tokens are relayed to this "
                    "URL; plaintext HTTP would expose them on the network. "
                    f"Current value: {aios_url!r}"
                )
```

- [ ] **Step 4: Run tests to confirm green**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_config_validation.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config_validation.py
git commit -m "fix(config): reject http:// AIOS_BASE_URL in production (TD-023)"
```

---

### Task 2: TD-027a — Enforce `MAX_TTL_DAYS = 90` in `CredentialService.issue()`

**Files:**
- Modify: `backend/app/services/credential_service.py`
- Modify: `backend/tests/test_credentials.py`

**Interfaces:**
- Consumes: `CredentialService.issue(user, label, expires_in_days)` (lines 44-66)
- Produces: `MAX_TTL_DAYS: int = 90` module-level constant; `issue()` raises `ValueError` when `expires_in_days > MAX_TTL_DAYS`

**Context:** Currently `expires_in_days` is caller-controlled with no server-side ceiling. A caller can issue a credential expiring in 10 years — or never (`None`). Fix: cap at 90 days. Raise `ValueError` (not silently clamp) so the caller learns the limit. `None` keeps its current meaning (no expiry is still valid; the existing `test_no_expiry_credential_stays_active` must keep passing).

The router (`auth.py` line 127) calls `CredentialService.issue(...)` directly. When `expires_in_days > 90` the service raises `ValueError`; the router must catch it and return 422. Add that handling in Task 3 (auth action audit refactor). For now, just implement the service rule and test it at the service level.

- [ ] **Step 1: Write failing test in `TestCredentialService`**

Add to the `TestCredentialService` class in `backend/tests/test_credentials.py`:

```python
    def test_issue_raises_when_expires_in_days_exceeds_max(self, db_session, seed_users):
        from app.models import User
        from app.services.credential_service import MAX_TTL_DAYS
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        with pytest.raises(ValueError, match="90"):
            svc.issue(user, expires_in_days=MAX_TTL_DAYS + 1)

    def test_issue_accepts_exactly_max_ttl(self, db_session, seed_users):
        from app.models import User
        from app.services.credential_service import MAX_TTL_DAYS
        user = db_session.query(User).filter_by(username="t_admin").one()
        svc = CredentialService(db_session)
        cred, raw = svc.issue(user, expires_in_days=MAX_TTL_DAYS)
        assert cred.expires_at is not None
        assert cred.is_active
```

- [ ] **Step 2: Run to confirm failure**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_credentials.py::TestCredentialService::test_issue_raises_when_expires_in_days_exceeds_max -v
```

Expected: FAIL — no ValueError raised yet.

- [ ] **Step 3: Add `MAX_TTL_DAYS` and enforce in `issue()`**

In `backend/app/services/credential_service.py`, after the `DEFAULT_TTL_DAYS` constant (after line 27):

```python
# Hard server-side ceiling on credential lifetime. Callers that omit
# expires_in_days (→ None) receive a non-expiring credential; callers that
# supply a value must stay within this bound.
MAX_TTL_DAYS: int = 90
```

Inside `issue()`, before the `raw_token = _generate_token()` line (after line 55), add:

```python
        if expires_in_days is not None and expires_in_days > MAX_TTL_DAYS:
            raise ValueError(
                f"expires_in_days must not exceed {MAX_TTL_DAYS} days. "
                f"Got {expires_in_days}."
            )
```

- [ ] **Step 4: Run tests**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_credentials.py -v
```

Expected: all existing tests pass + 2 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/credential_service.py backend/tests/test_credentials.py
git commit -m "fix(credentials): cap credential TTL at MAX_TTL_DAYS=90 (TD-027)"
```

---

### Task 3: TD-027b — Proper audit actions for credential issuance and revocation

**Files:**
- Modify: `backend/app/services/audit_service.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_credentials.py`

**Interfaces:**
- Produces: `CREDENTIAL_ISSUED = "CREDENTIAL_ISSUED"` and `CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"` constants in `audit_service`
- `issue_credential` router endpoint: raises 422 on `ValueError` from `CredentialService.issue()`; logs `CREDENTIAL_ISSUED` instead of `LOGIN`
- `revoke_credential` router endpoint: logs `CREDENTIAL_REVOKED` instead of `LOGOUT`

**Context:** Currently `issue_credential` logs with `audit_service.LOGIN` (line 131 of `auth.py`) and `revoke_credential` logs with `audit_service.LOGOUT` (line 176). These semantics are wrong — audit viewers see credential operations as login/logout events. The fix adds two distinct constants and uses them at the correct call sites. Also: wrap `CredentialService.issue()` in a try/except `ValueError` in the router to return 422 when `MAX_TTL_DAYS` is exceeded (Task 2's guard).

- [ ] **Step 1: Write failing tests**

Add to `TestCredentialEndpoints` in `backend/tests/test_credentials.py`:

```python
    def test_issue_too_long_ttl_returns_422(self, anon, override_db, seed_users):
        from app.services.credential_service import MAX_TTL_DAYS
        client, _ = _get_bearer_client(anon)
        resp = client.post(
            "/auth/credentials",
            data={"expires_in_days": str(MAX_TTL_DAYS + 1)},
        )
        assert resp.status_code == 422

    def test_issue_audit_action_is_credential_issued(self, anon, override_db, seed_users, db_session):
        client, _ = _get_bearer_client(anon)
        client.post("/auth/credentials", data={"label": "audit-test"})
        from app.models import AuditLog
        from app.services.audit_service import CREDENTIAL_ISSUED
        last = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert last is not None
        assert last.action == CREDENTIAL_ISSUED

    def test_revoke_audit_action_is_credential_revoked(self, anon, override_db, seed_users, db_session):
        client, _ = _get_bearer_client(anon)
        issue_resp = client.post("/auth/credentials", data={"label": "r"})
        cred_id = issue_resp.json()["id"]
        client.delete(f"/auth/credentials/{cred_id}")
        from app.models import AuditLog
        from app.services.audit_service import CREDENTIAL_REVOKED
        last = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert last is not None
        assert last.action == CREDENTIAL_REVOKED
```

- [ ] **Step 2: Run to confirm failure**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_credentials.py::TestCredentialEndpoints::test_issue_audit_action_is_credential_issued tests/test_credentials.py::TestCredentialEndpoints::test_issue_too_long_ttl_returns_422 -v
```

Expected: both FAIL.

- [ ] **Step 3: Add constants to `audit_service.py`**

In `backend/app/services/audit_service.py`, append after the last constant (`DOWNLOAD_PDF = "DOWNLOAD_PDF"` line):

```python
CREDENTIAL_ISSUED = "CREDENTIAL_ISSUED"
CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"
```

- [ ] **Step 4: Update `issue_credential` in `auth.py`**

Replace the `issue_credential` function body in `backend/app/routers/auth.py` (the entire function from `@router.post("/auth/credentials")` to the closing `}`):

```python
@router.post("/auth/credentials")
def issue_credential(
    label: Optional[str] = Form(None),
    expires_in_days: Optional[int] = Form(None),
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    """Issue a long-lived API credential for the authenticated user.

    Returns the raw token **once** — it cannot be retrieved again. Store it
    in a secrets manager immediately.

    - ``label`` — optional human-readable name (e.g. "CI pipeline").
    - ``expires_in_days`` — TTL in days (max 90); omit for a non-expiring credential.
    """
    try:
        cred, raw_token = CredentialService(db).issue(
            user, label=label, expires_in_days=expires_in_days
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit_service.record(
        db, audit_service.CREDENTIAL_ISSUED, user=user,
        meta={"credential_id": cred.id, "label": label,
              "expires_in_days": expires_in_days},
    )
    return {
        "id": cred.id,
        "token": raw_token,
        "label": cred.label,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "created_at": cred.created_at.isoformat(),
        "note": "Store this token securely — it will not be shown again.",
    }
```

- [ ] **Step 5: Update `revoke_credential` in `auth.py`**

In `revoke_credential`, change:
```python
    audit_service.record(
        db, audit_service.LOGOUT, user=user,
        meta={"action": "credential_revoked", "credential_id": credential_id},
    )
```
to:
```python
    audit_service.record(
        db, audit_service.CREDENTIAL_REVOKED, user=user,
        meta={"credential_id": credential_id},
    )
```

- [ ] **Step 6: Run all credential tests**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_credentials.py -v
```

Expected: all pass (including 3 new tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/audit_service.py backend/app/routers/auth.py backend/tests/test_credentials.py
git commit -m "fix(audit): CREDENTIAL_ISSUED/CREDENTIAL_REVOKED actions; 422 on TTL cap (TD-027)"
```

---

### Task 4: TD-027c — Deactivate user → revoke all credentials

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/routers/admin.py`
- Modify: `backend/app/templates/admin_users.html`
- Create/Modify: `backend/tests/test_admin.py` (or add to `test_credentials.py`)

**Interfaces:**
- Consumes: existing `AuthService` (auth_service.py); existing `CredentialService.revoke_all_for_user()` (credential_service.py line 90); existing `audit_service.CREDENTIAL_REVOKED`
- Produces: `AuthService.deactivate_user(user_id: int) -> User` — sets `is_active=False`, returns the user object; `POST /admin/users/{user_id}/deactivate` endpoint

**Context:** `revoke_all_for_user` exists but is never called (TD-027 description). The natural hook is user deactivation. `AuthService.deactivate_user` only sets `is_active=False` (user-layer concern). The router then calls `CredentialService.revoke_all_for_user` separately — no cross-import between services. Admin template gets a "Деактивировать" form button per row (skip for the current logged-in user and for already-inactive users).

**Check for test file:** Run `ls backend/tests/test_admin.py` — if it doesn't exist, create it. If it does, append the new class.

- [ ] **Step 1: Write failing tests**

Create (or append to) `backend/tests/test_admin.py`:

```python
"""Admin route tests — user management."""
import pytest
from fastapi.testclient import TestClient

from app.services.auth_service import ROLE_ADMIN, AuthService
from app.services.credential_service import CredentialService


def _admin_client(anon):
    resp = anon.post("/login", data={"username": "t_admin", "password": "pw"},
                     follow_redirects=False)
    from fastapi.testclient import TestClient
    from app.main import app as _app
    c = TestClient(_app, cookies=dict(anon.cookies))
    return c


class TestDeactivateUser:
    def test_deactivate_sets_inactive(self, anon, override_db, seed_users, db_session):
        from app.models import User
        issuer = db_session.query(User).filter_by(username="t_issuer").one()
        issuer_id = issuer.id

        # Log in as admin and post deactivation
        resp = anon.post("/login", data={"username": "t_admin", "password": "pw"},
                         follow_redirects=False)
        assert resp.status_code in (302, 303)

        # GET csrf token from admin page
        page_resp = anon.get("/admin/users")
        import re
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
        # Issue a credential for the issuer
        svc = CredentialService(db_session)
        cred, raw = svc.issue(issuer, label="to-be-revoked")
        assert cred.revoked_at is None

        # Deactivate via admin session
        resp = anon.post("/login", data={"username": "t_admin", "password": "pw"},
                         follow_redirects=False)
        page_resp = anon.get("/admin/users")
        import re
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page_resp.text).group(1)
        anon.post(
            f"/admin/users/{issuer.id}/deactivate",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        db_session.refresh(cred)
        assert cred.revoked_at is not None

    def test_deactivate_requires_admin(self, anon, override_db, seed_users, db_session):
        from app.models import User
        admin = db_session.query(User).filter_by(username="t_admin").one()
        # Log in as issuer, try to deactivate admin
        resp = anon.post("/login", data={"username": "t_issuer", "password": "pw"},
                         follow_redirects=False)
        page_resp = anon.get("/admin/users")  # will 403 for issuer
        # Issuer can't reach admin pages at all → 403
        assert page_resp.status_code == 403
```

- [ ] **Step 2: Run to confirm failure**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_admin.py -v
```

Expected: FAIL — endpoint does not exist.

- [ ] **Step 3: Add `deactivate_user` to `AuthService`**

In `backend/app/services/auth_service.py`, add the method after `create_user` (after the existing `ensure_dev_admin`):

```python
    def deactivate_user(self, user_id: int) -> "User":
        """Set user inactive. Raises ValueError when not found or already inactive."""
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found.")
        if not user.is_active:
            raise ValueError(f"User {user_id} is already inactive.")
        user.is_active = False
        self.db.flush()
        return user
```

Check `UserRepository` for `get_by_id` — if it doesn't exist, add it to `backend/app/repositories/user_repository.py`:

```python
    def get_by_id(self, user_id: int) -> Optional["User"]:
        return self.db.query(User).filter_by(id=user_id).first()
```

(Check the file first to avoid duplication.)

- [ ] **Step 4: Add `POST /admin/users/{user_id}/deactivate` to `admin.py`**

In `backend/app/routers/admin.py`, add the import at the top alongside `AuthService`:
```python
from app.services.credential_service import CredentialService
from app.services import audit_service
```

Then add the route (after `admin_create_user`):

```python
@router.post("/admin/users/{user_id}/deactivate", response_class=HTMLResponse)
def admin_deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    require_admin(current_user)
    service = AuthService(db)
    try:
        target = service.deactivate_user(user_id)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/users?error={exc}", status_code=303
        )
    revoked = CredentialService(db).revoke_all_for_user(target)
    audit_service.record(
        db, audit_service.CREDENTIAL_REVOKED, user=current_user,
        meta={"deactivated_user_id": user_id, "credentials_revoked": revoked},
    )
    return RedirectResponse(url="/admin/users", status_code=303)
```

- [ ] **Step 5: Add deactivate button to `admin_users.html`**

In `backend/app/templates/admin_users.html`, change the `<thead>` row to add an "Действия" column:

```html
<thead><tr><th>ID</th><th>Имя</th><th>Роли</th><th>Админ</th><th>Активен</th><th></th></tr></thead>
```

And in the `<tbody>` loop, add a table cell with the deactivate form after the "Активен" cell:

```html
<td>
  {% if u.active and not u.is_admin %}
  <form method="post" action="/admin/users/{{ u.id }}/deactivate"
        onsubmit="return confirm('Деактивировать пользователя {{ u.username }}?')"
        style="display:inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <button type="submit"
            style="padding:4px 10px;font-size:12px;background:#dc2626;">
      Деакт.
    </button>
  </form>
  {% elif not u.active %}
  <span style="color:#9ca3af;font-size:12px;">неактивен</span>
  {% endif %}
</td>
```

(Admin users `u.is_admin=True` are excluded from the button — you cannot deactivate yourself or other admins via this UI.)

- [ ] **Step 6: Run all tests**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/test_admin.py tests/test_credentials.py -v
```

Expected: all pass.

- [ ] **Step 7: Full suite**

```
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
python -m pytest tests/ -q
```

Expected: all previous tests pass + new ones.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/auth_service.py \
        backend/app/repositories/user_repository.py \
        backend/app/routers/admin.py \
        backend/app/templates/admin_users.html \
        backend/tests/test_admin.py
git commit -m "feat(admin): deactivate user revokes all credentials; wire revoke_all_for_user (TD-027)"
```

---

## Post-sprint

After all 4 tasks are committed:

1. Run full test suite: `cd backend && python -m pytest tests/ -q`
2. Update `TECHNICAL_DEBT.md`: mark TD-023 and TD-027 as `✅ RESOLVED`
3. Update `PROJECT_STATE.md` and `CHANGELOG.md` with v1.2.2
4. Update `ROADMAP.md`
5. Commit docs: `git commit -m "docs: update state, roadmap, changelog for v1.2.2"`
