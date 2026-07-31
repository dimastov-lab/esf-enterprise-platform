"""ESF routes: dashboard, create, edit, save, validate, publish, delete,
PDF, QR, public verification, result page.

URLs use the document UUID only (never the sequential id). Authenticated routes
run through `get_current_user` and the service enforces owner/admin access.
The public verification page is open and read-only, served from the snapshot.
Controllers stay thin: all business logic lives in the services.
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import ratelimit
from app.core.config import settings
from app.core.observability import client_ip, error_response
from app.core.security import get_csrf_token, get_current_user, require_csrf
from app.db.session import get_db
from app.models import DocumentStatus, User
from app.services import audit_service
from app.services.esf_service import ESFService
from app.services.pdf_service import render_esf_pdf, render_esf_zip

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
# DEMO watermark visibility is a deployment-wide setting; expose it to every
# form.html render (edit / view / public / pdf / batch) via one Jinja global.
templates.env.globals["show_demo_watermark"] = settings.SHOW_DEMO_WATERMARK

router = APIRouter()


def _qdate(s: str):
    """Parse an HTML <input type=date> value (YYYY-MM-DD); None if blank/invalid."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _render_form(request: Request, service: ESFService, doc, user=None, errors=None, ok_msg=None):
    """Render the document for its owner: editable form (DRAFT/VALIDATED) or a
    read-only, snapshot-backed view (PUBLISHED/CANCELLED)."""
    from app.services.esf_serializer import STATUS_LABELS
    csrf = get_csrf_token(request)
    workspace = {
        "username": user.username if user else "",
        "is_admin": bool(user and user.is_admin),
        "status_code": doc.status.value,
        "status_label": STATUS_LABELS.get(doc.status, doc.status.value),
    }
    if ESFService.is_editable(doc):
        ctx = {
            "request": request, "esf": service.serialize(doc), "mode": "edit",
            "dev": False, "edit": True, "locked": False,
            "errors": errors or [], "ok_msg": ok_msg, "csrf_token": csrf,
            **workspace,
        }
    else:
        ctx = {
            "request": request, "esf": service.serialize_published(doc), "mode": "view",
            "dev": False, "edit": False, "locked": True,
            "errors": errors or [], "ok_msg": ok_msg, "csrf_token": csrf,
            "is_published": doc.status == DocumentStatus.PUBLISHED,
            "is_cancelled": doc.status == DocumentStatus.CANCELLED,
            **workspace,
        }
    return templates.TemplateResponse(request, "esf/form.html", ctx)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user),
              page: int = 1, page_size: int = 25, q: str = "", status: str = "",
              currency: str = "", supplier: str = "", buyer: str = "",
              date_from: str = "", date_to: str = "", sort: str = "updated", dir: str = "desc"):
    service = ESFService(db)
    result = service.page(
        user, page=page, page_size=page_size, q=q, status=status, currency=currency,
        supplier=supplier, buyer=buyer, date_from=_qdate(date_from), date_to=_qdate(date_to),
        sort=sort, direction=dir,
    )
    stats = service.dashboard_stats(user)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "stats": stats, "username": user.username,
         "is_admin": user.is_admin, "csrf_token": get_csrf_token(request),
         "rows": result["rows"], "page": result["page"], "page_size": result["page_size"],
         "total": result["total"], "total_pages": result["total_pages"],
         "sort": result["sort"], "dir": result["dir"],
         "filters": {"q": q, "status": status, "currency": currency, "supplier": supplier,
                     "buyer": buyer, "date_from": date_from, "date_to": date_to}},
    )


@router.get("/esf/new")
def esf_new(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = ESFService(db).create_draft(user)
    audit_service.record(db, audit_service.CREATE, user=user, document=doc, request=request)
    return RedirectResponse(url=f"/esf/{doc.uuid}", status_code=303)


@router.post("/esf/{doc_uuid}/duplicate")
def esf_duplicate(doc_uuid: str, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user),
                  _csrf: None = Depends(require_csrf)):
    """Create a new editable draft copied from an existing document (any status).
    Opens the copy in the editor. The source is never modified."""
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    new = service.duplicate(doc, user)
    audit_service.record(db, audit_service.CREATE, user=user, document=new,
                         request=request, meta={"duplicated_from": str(doc.uuid)})
    return RedirectResponse(url=f"/esf/{new.uuid}", status_code=303)


@router.post("/esf/{doc_uuid}/correct")
def esf_correct(doc_uuid: str, request: Request,
                db: Session = Depends(get_db), user: User = Depends(get_current_user),
                _csrf: None = Depends(require_csrf)):
    """Create a correction draft for a PUBLISHED document and open it in the editor."""
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    new = service.create_correction(doc, user)
    audit_service.record(db, audit_service.CREATE, user=user, document=new,
                         request=request, meta={"corrects": str(doc.uuid)})
    return RedirectResponse(url=f"/esf/{new.uuid}", status_code=303)


@router.post("/esf/{doc_uuid}/cancel")
def esf_cancel(doc_uuid: str, request: Request,
               db: Session = Depends(get_db), user: User = Depends(get_current_user),
               _csrf: None = Depends(require_csrf)):
    """Annul a PUBLISHED document (status -> CANCELLED); snapshot is preserved."""
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    service.cancel(doc, user)
    audit_service.record(db, audit_service.DELETE, user=user, document=doc,
                         request=request, meta={"action": "cancel", "number": doc.esf_number})
    return RedirectResponse(url=f"/esf/{doc_uuid}", status_code=303)


# ---- batch operations (v6.0 #3) — multi-select on the dashboard ----------
@router.post("/esf/batch/delete")
async def esf_batch_delete(request: Request, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)):
    uuids = (await request.form()).getlist("uuid")[:500]
    res = ESFService(db).batch_delete(uuids, user)
    audit_service.record(db, audit_service.DELETE, user=user,
                         request=request, meta={"action": "batch_delete", **res})
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/esf/batch/publish")
async def esf_batch_publish(request: Request, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)):
    uuids = (await request.form()).getlist("uuid")[:500]
    res = ESFService(db).batch_publish(uuids, user)
    audit_service.record(db, audit_service.PUBLISH, user=user,
                         request=request, meta={"action": "batch_publish", **res})
    return RedirectResponse(url="/dashboard", status_code=303)


# Batch PDF is capped low: WeasyPrint is ~2-3s/doc, so keep the whole request
# comfortably under the reverse-proxy read timeout (nginx 60s).
_BATCH_PDF_CAP = 20


@router.post("/esf/batch/pdf")
async def esf_batch_pdf(request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)):
    """Render the selected documents and return them as a single ZIP download."""
    uuids = (await request.form()).getlist("uuid")[:_BATCH_PDF_CAP]
    service = ESFService(db)
    # Serialize in the request context (fast DB access); non-editable docs render
    # from the immutable snapshot, matching the single-PDF route. The blocking
    # template + WeasyPrint render is then offloaded off the event loop.
    named = []
    for u in uuids:
        doc = service.get_if_owner(u, user)
        if doc is None:
            continue
        esf = service.serialize(doc) if service.is_editable(doc) else service.serialize_published(doc)
        name = (doc.esf_number or str(doc.uuid)).replace("/", "-")
        named.append((f"esf-{name}.pdf", esf))
    zip_bytes = await run_in_threadpool(render_esf_zip, named)
    audit_service.record(db, audit_service.DOWNLOAD_PDF, user=user,
                         request=request, meta={"action": "batch_pdf", "count": len(named)})
    return Response(content=zip_bytes, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="esf-batch.zip"'})


@router.get("/esf/check-esf", response_class=HTMLResponse)
def esf_public_check(documentUUID: str, request: Request, db: Session = Depends(get_db)):
    """PUBLIC verification page — no login, read-only, served from the snapshot.

    Only PUBLISHED documents are publicly verifiable. Declared before
    `/esf/{doc_uuid}` so the literal path wins over the catch-all.
    Throttled per IP BEFORE any DB work: the route is unauthenticated, and every
    allowed view also writes an audit row — the limiter caps both UUID
    enumeration and that write amplification (TD-013).
    """
    if ratelimit.throttle_public(client_ip(request)):
        return error_response(
            request, 429, "Слишком много запросов. Повторите позже.",
            headers={"Retry-After": str(ratelimit.PUBLIC_WINDOW_SECONDS)},
        )
    service = ESFService(db)
    doc = service.get_public(documentUUID)
    if doc is None or doc.status != DocumentStatus.PUBLISHED:
        return HTMLResponse(
            "Документ не найден или не опубликован.", status_code=404
        )
    esf = service.serialize_published(doc)
    audit_service.record(db, audit_service.VIEW_PUBLIC, document=doc, request=request)
    return templates.TemplateResponse(
        request,
        "esf/form.html",
        {"request": request, "esf": esf, "mode": "public", "dev": False,
         "edit": False, "locked": False, "errors": []},
    )


@router.get("/esf/{doc_uuid}", response_class=HTMLResponse)
def esf_edit(doc_uuid: str, request: Request,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    return _render_form(request, service, doc, user=user)


@router.post("/esf/{doc_uuid}/save")
async def esf_save(doc_uuid: str, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user),
                   _csrf: None = Depends(require_csrf)):
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    service.save(doc, user, await request.form())
    return RedirectResponse(url=f"/esf/{doc_uuid}", status_code=303)


@router.post("/esf/{doc_uuid}/autosave")
async def esf_autosave(doc_uuid: str, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user),
                       _csrf: None = Depends(require_csrf)):
    """Background autosave (fetch). Persists the draft without navigation; returns JSON."""
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    try:
        service.save(doc, user, await request.form())
    except HTTPException as exc:
        return JSONResponse({"ok": False, "error": str(exc.detail)}, status_code=exc.status_code)
    return JSONResponse({"ok": True, "saved_at": datetime.now().strftime("%H:%M:%S")})


@router.post("/esf/{doc_uuid}/validate", response_class=HTMLResponse)
async def esf_validate(doc_uuid: str, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user),
                       _csrf: None = Depends(require_csrf)):
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    service.save(doc, user, await request.form())   # persist current edits first
    errors = service.validate(doc, user)
    audit_service.record(db, audit_service.VALIDATE, user=user, document=doc,
                         request=request, meta={"errors": len(errors)})
    ok = None if errors else "Документ прошёл проверку (VALIDATED). Можно формировать."
    return _render_form(request, service, doc, user=user, errors=errors, ok_msg=ok)


@router.post("/esf/{doc_uuid}/publish", response_class=HTMLResponse)
async def esf_publish(doc_uuid: str, request: Request,
                      db: Session = Depends(get_db), user: User = Depends(get_current_user),
                      _csrf: None = Depends(require_csrf)):
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    service.save(doc, user, await request.form())   # persist current edits first
    errors = service.publish(doc, user)
    if errors:
        return _render_form(request, service, doc, user=user, errors=errors)
    audit_service.record(db, audit_service.PUBLISH, user=user, document=doc,
                         request=request, meta={"number": doc.esf_number})
    # Phase 9 (smart publication): open the final official document directly —
    # no intermediate result page. The read-only view carries the review toolbar.
    return RedirectResponse(url=f"/esf/{doc_uuid}", status_code=303)


@router.post("/esf/{doc_uuid}/delete")
def esf_delete(doc_uuid: str, request: Request,
               db: Session = Depends(get_db), user: User = Depends(get_current_user),
               _csrf: None = Depends(require_csrf)):
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    meta = {"number": doc.esf_number, "uuid": str(doc.uuid)}
    service.delete(doc, user)  # raises 409 if the doc is not an editable draft
    # Record the audit only AFTER a successful delete, so a rejected delete (409 on
    # a non-editable doc) never leaves a false "DELETE" entry.
    audit_service.record(db, audit_service.DELETE, user=user, request=request, meta=meta)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/pdf/{doc_uuid}.pdf")
def esf_pdf(doc_uuid: str, request: Request,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """PDF from the SAME template via WeasyPrint. Any non-editable doc (PUBLISHED
    or CANCELLED) renders from the immutable snapshot; editable drafts from live
    data — so a cancelled invoice's PDF matches its on-screen snapshot view."""
    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    esf = service.serialize(doc) if service.is_editable(doc) \
        else service.serialize_published(doc)
    audit_service.record(db, audit_service.DOWNLOAD_PDF, user=user, document=doc, request=request)
    return Response(
        content=render_esf_pdf(esf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="esf-{doc_uuid}.pdf"'},
    )


@router.get("/qr/{doc_uuid}.png")
def esf_qr(doc_uuid: str, request: Request, db: Session = Depends(get_db)):
    """QR PNG (open, read-only). Encodes the public check URL only — no document
    data. Restricted to PUBLISHED documents (matching /esf/check-esf) and generated
    in memory: an unauthenticated GET must never write to disk or the DB. The QR is
    persisted at publish time / on the owner's result page.
    Shares the public per-IP throttle bucket with /esf/check-esf (TD-013)."""
    from app.services.qr_service import qr_png_bytes, qr_target

    if ratelimit.throttle_public(client_ip(request)):
        return error_response(
            request, 429, "Слишком много запросов. Повторите позже.",
            headers={"Retry-After": str(ratelimit.PUBLIC_WINDOW_SECONDS)},
        )
    service = ESFService(db)
    doc = service.get_public(doc_uuid)
    if doc is None or doc.status != DocumentStatus.PUBLISHED:
        return error_response(request, 404, "Документ не найден.")
    png = qr_png_bytes(qr_target(str(doc.uuid)))
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="qr-{doc_uuid}.png"'},
    )


@router.get("/result/{doc_uuid}", response_class=HTMLResponse)
def esf_result(doc_uuid: str, request: Request,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Result/landing page (owner/admin): QR, public link, PDF link, downloads."""
    from app.services.qr_service import public_check_path, qr_target

    service = ESFService(db)
    doc = service.get_for_user(doc_uuid, user)
    if doc is None:
        return error_response(request, 404, "Документ не найден.")
    service.ensure_qr(doc)
    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "request": request,
            "uuid": doc_uuid,
            "number": doc.esf_number or "—",
            "status": doc.status.value,
            "published": doc.status == DocumentStatus.PUBLISHED,
            "public_path": public_check_path(doc_uuid),
            "qr_target": qr_target(doc_uuid),
        },
    )
