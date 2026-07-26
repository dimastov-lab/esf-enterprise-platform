"""Access control — session-based authentication + RBAC (Sprint 9R).

The authenticated user id lives in the signed session cookie. Protected routes
depend on `get_current_user`, which raises `NotAuthenticated` when there is no
valid session; an exception handler (main.py) redirects those to /login.
Public routes use no auth dependency.
"""
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User


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
