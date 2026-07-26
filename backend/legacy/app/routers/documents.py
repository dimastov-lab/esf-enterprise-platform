import os

from app.services.document_service import DocumentService
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/documents")
templates = Jinja2Templates(directory="templates")


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("document_form.html", {"request": request, "error": None})


@router.post("/new")
def create_document(
    request: Request,
    title: str = Form(...),
    applicant_name: str = Form(...),
    applicant_id: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    service = DocumentService(db)
    doc = service.create_draft(
        title=title,
        applicant_name=applicant_name,
        applicant_id=applicant_id,
        description=description,
        created_by=request.session["user_id"],
    )
    return RedirectResponse(url=f"/documents/{doc.id}", status_code=303)


@router.get("/{doc_id}", response_class=HTMLResponse)
def view_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    service = DocumentService(db)
    doc = service.get(doc_id)
    if not doc:
        return HTMLResponse("Document not found", status_code=404)
    return templates.TemplateResponse(
        "document_view.html",
        {"request": request, "doc": doc, "username": request.session.get("username")},
    )


@router.post("/{doc_id}/generate")
def generate_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    base_url = str(request.base_url).rstrip("/")
    service = DocumentService(db)
    service.generate(doc_id, base_url)
    return RedirectResponse(url=f"/documents/{doc_id}", status_code=303)


@router.get("/{doc_id}/pdf")
def download_pdf(doc_id: int, request: Request, db: Session = Depends(get_db)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    service = DocumentService(db)
    doc = service.get(doc_id)
    if not doc or not doc.pdf_path or not os.path.exists(doc.pdf_path):
        return HTMLResponse("PDF not found", status_code=404)
    return FileResponse(
        doc.pdf_path,
        media_type="application/pdf",
        filename=f"{doc.document_number}.pdf",
    )
