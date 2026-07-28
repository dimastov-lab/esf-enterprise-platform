"""Development-only preview route for the STI-007 ESF visual template.

Sprint 4R: renders `templates/esf/form.html` with sample mock data so the
layout can be compared against «Копия 6.pdf». No database access, no CRUD,
no PDF/QR/workflow. This router is mounted only when ENVIRONMENT != production.
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dev_sample import SAMPLE_ESF

# app/ directory -> app/templates
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
# The dev preview is inherently a non-official demo — always mark it.
templates.env.globals["show_demo_watermark"] = True

router = APIRouter()

_ALLOWED_MODES = {"edit", "view", "public"}


@router.get("/dev/esf-preview", response_class=HTMLResponse)
def esf_preview(request: Request, mode: str = "view"):
    if mode not in _ALLOWED_MODES:
        mode = "view"
    return templates.TemplateResponse(
        request,
        "esf/form.html",
        {"request": request, "esf": SAMPLE_ESF, "mode": mode, "dev": True},
    )
