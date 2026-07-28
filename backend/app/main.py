"""FastAPI application.

Sprint 9R adds session-based authentication + RBAC. Protected routes depend on
`get_current_user`; unauthenticated requests raise `NotAuthenticated` and are
redirected to /login. Public verification (`/esf/check-esf`, `/qr/*.png`) stays open.
Schema is managed by Alembic migrations, not by create_all at startup.
"""
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.core import observability
from app.core.config import settings
from app.core.security import NotAuthenticated
from app.db.session import get_db

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Interactive API docs are useful in dev but are attack surface / info disclosure
# in production — disable them there.
_prod = settings.is_production
app = FastAPI(
    title=settings.PROJECT_NAME, version=settings.VERSION,
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)

# structured logging + request id + clean 500 handler
observability.install(app)

# Content-Security-Policy + hardening headers on every response (defence-in-depth
# for XSS/clickjacking). 'unsafe-inline' is required because the templates use
# inline <script>/style; the value still blocks external script/object sources,
# framing, and base-uri hijacking. Served in all environments; HSTS only in prod.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", _CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if _prod:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


# Signed session cookie (login state). Secret comes from config/env.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=_prod,
)

# CWD-safe absolute path (avoids the relative-mount bug from the legacy code).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=303)


@app.get("/")
def health():
    """Shallow liveness probe — process is up (no dependency checks)."""
    return {
        "status": "running",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness probe — verifies DB connectivity so a DB-down container is
    reported unhealthy (503) instead of passing a shallow liveness check."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable", "db": "error"}, status_code=503)
    return {"status": "ready"}


# Routers
from app.routers.admin import router as admin_router
from app.routers.api import router as api_router
from app.routers.auth import router as auth_router
from app.routers.esf import router as esf_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_router)
app.include_router(esf_router)

# Development-only preview. Never mounted in production.
if not settings.is_production:
    from app.routers.dev_preview import router as dev_preview_router

    app.include_router(dev_preview_router)


@app.on_event("startup")
def _dev_seed_admin():
    """Dev only: ensure roles + an initial admin (admin/admin123) so login works."""
    if settings.is_production:
        return
    from app.db.session import SessionLocal
    from app.services.auth_service import AuthService

    db = SessionLocal()
    try:
        AuthService(db).ensure_dev_admin()
    finally:
        db.close()
