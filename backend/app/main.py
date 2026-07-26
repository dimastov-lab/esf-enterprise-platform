"""FastAPI application.

Sprint 9R adds session-based authentication + RBAC. Protected routes depend on
`get_current_user`; unauthenticated requests raise `NotAuthenticated` and are
redirected to /login. Public verification (`/esf/check-esf`, `/qr/*.png`) stays open.
Schema is managed by Alembic migrations, not by create_all at startup.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core import observability
from app.core.config import settings
from app.core.security import NotAuthenticated

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Interactive API docs are useful in dev but are attack surface / info disclosure
# in production — disable them there.
_prod = settings.ENVIRONMENT == "production"
app = FastAPI(
    title=settings.PROJECT_NAME, version=settings.VERSION,
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)

# structured logging + request id + clean 500 handler
observability.install(app)

# Signed session cookie (login state). Secret comes from config/env.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=(settings.ENVIRONMENT == "production"),
)

# CWD-safe absolute path (avoids the relative-mount bug from the legacy code).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=303)


@app.get("/")
def health():
    return {
        "status": "running",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


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
if settings.ENVIRONMENT != "production":
    from app.routers.dev_preview import router as dev_preview_router

    app.include_router(dev_preview_router)


@app.on_event("startup")
def _dev_seed_admin():
    """Dev only: ensure roles + an initial admin (admin/admin123) so login works."""
    if settings.ENVIRONMENT == "production":
        return
    from app.db.session import SessionLocal
    from app.services.auth_service import AuthService

    db = SessionLocal()
    try:
        AuthService(db).ensure_dev_admin()
    finally:
        db.close()
