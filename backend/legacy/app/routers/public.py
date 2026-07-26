from app.services.document_service import DocumentService
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/public")
templates = Jinja2Templates(directory="templates")


@router.get("/{document_number}", response_class=HTMLResponse)
def public_view(document_number: str, request: Request, db: Session = Depends(get_db)):
    service = DocumentService(db)
    doc = service.get_by_number(document_number)
    if not doc:
        return HTMLResponse("Document not found", status_code=404)
    return templates.TemplateResponse(
        "public_view.html", {"request": request, "doc": doc}
    )
