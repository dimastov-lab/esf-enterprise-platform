from app.services.document_service import DocumentService
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def require_login(request: Request):
    if "user_id" not in request.session:
        return None
    return request.session["user_id"]


@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    service = DocumentService(db)
    documents = service.list_all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "documents": documents, "username": request.session.get("username")},
    )
