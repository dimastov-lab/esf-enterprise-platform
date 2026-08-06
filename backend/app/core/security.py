"""Access control — session-based authentication + RBAC (Sprint 9R).

The authenticated user id lives in the signed session cookie. Protected routes
depend on `get_current_user`, which raises `NotAuthenticated` when there is no
valid session; an exception handler (main.py) redirects those to /login.
Public routes use no auth dependency.
"""
import logging
import secrets
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request

_log = logging.getLogger(__name__)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)


class NotAuthenticated(Exception):
    """Raised when a protected route is hit without a valid session."""


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return (
        db.query(User)
        .filter(User.id == user_id, User.is_active.is_(True))
        .one_or_none()
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise NotAuthenticated()
    return user


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора.")


async def get_current_api_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Dependency for API routes protected by Bearer tokens.

    Accepts two token formats:
    - ``esf_…`` — long-lived PG-backed credential (validated via api_credentials table)
    - anything else — treated as a short-lived JWT (60 min, stateless)

    Web UI routes continue to use get_current_user (session-cookie based).
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required",
                            headers={"WWW-Authenticate": "Bearer"})
    raw = credentials.credentials

    if raw.startswith("esf_"):
        from app.services.credential_service import CredentialService
        cred = CredentialService(db).validate(raw)
        if cred is None:
            raise HTTPException(status_code=401, detail="Invalid, expired or revoked credential",
                                headers={"WWW-Authenticate": "Bearer"})
        user = (
            db.query(User)
            .filter(User.id == cred.user_id, User.is_active.is_(True))
            .one_or_none()
        )
        if user is None:
            raise HTTPException(status_code=401, detail="User not found or inactive",
                                headers={"WWW-Authenticate": "Bearer"})
        return user

    # Layer 2 — AIOS Identity: when AIOS_ENABLED=true, validate the token
    # against AIOS first. If AIOS confirms it (returns claims), resolve the
    # local user by preferred_username/sub. If AIOS is unreachable or rejects
    # the token (returns None), fall through to ESF's own JWT validation so
    # locally-issued tokens continue to work even when AIOS is down.
    from app.core.config import settings as _settings
    if _settings.AIOS_ENABLED:
        from app.core.aios_bridge import get_bridge
        try:
            claims = await get_bridge().async_identity_verify(raw)
        except Exception as exc:  # bridge is already fire-and-forget; guard the call site too
            _log.warning("AIOS async_identity_verify raised: %s", exc)
            claims = None
        if claims is not None:
            if not isinstance(claims, dict):
                raise HTTPException(status_code=401, detail="AIOS returned unexpected identity format",
                                    headers={"WWW-Authenticate": "Bearer"})
            expected_tenant = _settings.AIOS_EXPECTED_TENANT_ID
            if expected_tenant and claims.get("tenant_id") != expected_tenant:
                raise HTTPException(
                    status_code=401,
                    detail="AIOS identity does not belong to the expected tenant",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            aios_username = claims.get("preferred_username") or claims.get("sub")
            if aios_username:
                user = (
                    db.query(User)
                    .filter(User.username == aios_username, User.is_active.is_(True))
                    .one_or_none()
                )
                if user is not None:
                    return user
            raise HTTPException(
                status_code=401,
                detail="AIOS identity verified but no matching ESF user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # claims is None: AIOS unavailable or token not recognized by AIOS.
        # Fall through to ESF JWT so local tokens keep working.

    from app.core.jwt import decode_access_token
    try:
        user_id = decode_access_token(raw)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    user = (
        db.query(User)
        .filter(User.id == user_id, User.is_active.is_(True))
        .one_or_none()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_owner_or_admin(doc, user: User) -> None:
    """Raise 403 unless the user owns the document or is an admin."""
    if doc.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")


# ---- CSRF (session-bound double-submit token) -------------------------
def get_csrf_token(request: Request) -> str:
    """Return the session CSRF token, creating it on first use."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


async def require_csrf(request: Request) -> None:
    """Dependency for state-changing POSTs: token from `X-CSRF-Token` header or
    `csrf_token` form field must match the session token."""
    session_token = request.session.get("csrf_token")
    token = request.headers.get("X-CSRF-Token")
    if not token:
        form = await request.form()  # Starlette caches this for the handler
        token = form.get("csrf_token")
    if not session_token or not token or not secrets.compare_digest(str(token), str(session_token)):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
