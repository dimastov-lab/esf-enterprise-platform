"""Authentication routes: login / logout (session) + /auth/token (JWT REST API)
+ /auth/credentials (long-lived PG-backed API credentials).
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.observability import client_ip
from app.core.security import get_current_api_user, get_optional_user
from app.db.session import get_db
from app.models.user import User
from app.services import audit_service
from app.services.auth_service import AuthService
from app.services.credential_service import CredentialService

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_optional_user(request, db) is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    # Key the limiter by (IP, username) so a successful login to one account cannot
    # reset the failure counter of a *different* account being brute-forced from the
    # same IP.
    key = f"{client_ip(request)}\x00{(username or '').strip().lower()}"
    if ratelimit.is_locked(key):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Слишком много попыток входа. Повторите позже."},
            status_code=429,
        )
    user = AuthService(db).authenticate(username, password)
    if user is None:
        ratelimit.record_failure(key)
        audit_service.record(db, audit_service.LOGIN_FAILED, request=request,
                             meta={"username": username})
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Неверное имя пользователя или пароль."},
            status_code=401,
        )
    ratelimit.reset(key)                      # only this (ip, username) bucket
    request.session["user_id"] = user.id
    request.session.pop("csrf_token", None)   # rotate the CSRF token on privilege change
    audit_service.record(db, audit_service.LOGIN, user=user, request=request)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/auth/token")
def api_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Issue a short-lived Bearer JWT for programmatic API access.

    Clients send ``Authorization: Bearer <token>`` on subsequent API requests.
    bcrypt runs once here; all downstream verification is a cheap signature check.
    Rate-limited by (IP, username) — same policy as the session login.
    """
    key = f"{client_ip(request)}\x00{(form_data.username or '').strip().lower()}"
    if ratelimit.is_locked(key):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    user = AuthService(db).authenticate(form_data.username, form_data.password)
    if user is None:
        ratelimit.record_failure(key)
        audit_service.record(db, audit_service.LOGIN_FAILED, request=request,
                             meta={"username": form_data.username})
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})

    ratelimit.reset(key)
    audit_service.record(db, audit_service.LOGIN, user=user, request=request)
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    audit_service.record(db, audit_service.LOGOUT, user=user, request=request)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ── Long-lived API credentials (PG-backed) ──────────────────────────────────

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
    - ``expires_in_days`` — TTL in days; omit for a non-expiring credential.
    """
    cred, raw_token = CredentialService(db).issue(
        user, label=label, expires_in_days=expires_in_days
    )
    audit_service.record(
        db, audit_service.LOGIN, user=user,
        meta={"action": "credential_issued", "credential_id": cred.id, "label": label},
    )
    return {
        "id": cred.id,
        "token": raw_token,
        "label": cred.label,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "created_at": cred.created_at.isoformat(),
        "note": "Store this token securely — it will not be shown again.",
    }


@router.get("/auth/credentials")
def list_credentials(
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    """List API credentials for the authenticated user (no raw tokens)."""
    creds = CredentialService(db).list_for_user(user)
    return [
        {
            "id": c.id,
            "label": c.label,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            "created_at": c.created_at.isoformat(),
            "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
            "active": c.is_active,
        }
        for c in creds
    ]


@router.delete("/auth/credentials/{credential_id}")
def revoke_credential(
    credential_id: int,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    """Revoke an API credential by id. Idempotent — returns 404 when not found."""
    ok = CredentialService(db).revoke(credential_id, user)
    if not ok:
        raise HTTPException(status_code=404, detail="Credential not found or already revoked.")
    audit_service.record(
        db, audit_service.LOGOUT, user=user,
        meta={"action": "credential_revoked", "credential_id": credential_id},
    )
    return {"revoked": True, "id": credential_id}
