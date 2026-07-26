"""Admin-only user management (RBAC)."""
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.security import (
    get_csrf_token,
    get_current_user,
    require_admin,
    require_csrf,
)
from app.db.session import get_db
from app.models import User
from app.repositories.audit_repository import AuditRepository
from app.services.auth_service import ROLES, AuthService

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


def _rows(service: AuthService):
    rows = []
    for u in service.list_users():
        rows.append({
            "id": u.id,
            "username": u.username,
            "roles": ", ".join(r.name for r in u.roles) or ("ADMIN" if u.is_admin else "—"),
            "is_admin": u.is_admin,
            "active": u.is_active,
        })
    return rows


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user), error: str = None, ok: str = None):
    require_admin(user)
    service = AuthService(db)
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {"request": request, "rows": _rows(service), "roles": list(ROLES.keys()),
         "username": user.username, "error": error, "ok": ok,
         "csrf_token": get_csrf_token(request)},
    )


@router.post("/admin/users", response_class=HTMLResponse)
def admin_create_user(request: Request, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user),
                      new_username: str = Form(...), new_password: str = Form(...),
                      role: str = Form(...), _csrf: None = Depends(require_csrf)):
    require_admin(user)
    service = AuthService(db)
    try:
        service.create_user(new_username, new_password, role)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin_users.html",
            {"request": request, "rows": _rows(service), "roles": list(ROLES.keys()),
             "username": user.username, "error": str(exc), "ok": None,
             "csrf_token": get_csrf_token(request)},
            status_code=400,
        )
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/admin/audit", response_class=HTMLResponse)
def admin_audit(request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    require_admin(user)
    rows = [{
        "time": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
        "user": uname or "—",
        "action": a.action,
        "doc": a.document_id if a.document_id is not None else "—",
        "ip": a.ip_address or "—",
        "meta": a.meta_json or {},
    } for a, uname in AuditRepository(db).list_recent()]
    return templates.TemplateResponse(
        request,
        "admin_audit.html",
        {"request": request, "rows": rows, "username": user.username},
    )
