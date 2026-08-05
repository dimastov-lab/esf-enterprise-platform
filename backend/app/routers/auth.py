"""Authentication routes: login / logout (session) + /auth/token (JWT REST API)."""
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.observability import client_ip
from app.core.security import get_optional_user
from app.db.session import get_db
from app.services import audit_service
from app.services.auth_service import AuthService

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
