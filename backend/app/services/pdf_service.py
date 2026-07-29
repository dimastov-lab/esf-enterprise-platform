"""Render the ESF PDF from the SAME HTML template (no separate PDF layout).

Renderer: WeasyPrint. It reproduces the STI-007 `templates/esf/form.html` layout
(flexbox rows, boxed digits, the goods table, totals, footer) accurately and emits
true vector/selectable text in A4 landscape via the stylesheet's `@page` rule, so the
PDF stays identical to the HTML and there is no duplicate layout to maintain.

The template's `<link href="/static/css/esf_form.css">` is resolved by a small
url_fetcher that serves the bundled stylesheet, so rendering needs no running web
server and no network.
"""
import io
import os
import sys
import zipfile
from pathlib import Path
from typing import List, Tuple

from app.core.config import settings

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_CSS_PATH = _STATIC_DIR / "css" / "esf_form.css"
_QR_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "qr"
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# The ESF document template (mode='pdf') is the single source of layout, shared
# with the on-screen form. Built once and cached; the DEMO-watermark visibility is
# a deployment-wide setting, exposed as the same Jinja global the routers use.
_env = None


def _template_env():
    global _env
    if _env is None:
        from fastapi.templating import Jinja2Templates
        jt = Jinja2Templates(directory=str(_TEMPLATES_DIR))
        jt.env.globals["show_demo_watermark"] = settings.SHOW_DEMO_WATERMARK
        _env = jt.env
    return _env


def _render_html(esf: dict) -> str:
    """Render the ESF template for `esf` in PDF mode (no request/CSRF context)."""
    return _template_env().get_template("esf/form.html").render(
        esf=esf, mode="pdf", dev=False, edit=False, locked=False, errors=[]
    )


def _ensure_native_libs() -> None:
    """macOS dev: make Homebrew's pango/cairo discoverable before importing WeasyPrint."""
    if sys.platform == "darwin":
        hb = "/opt/homebrew/lib"
        if os.path.isdir(hb):
            current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if hb not in current.split(":"):
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{current}:{hb}" if current else hb


def render_pdf(html: str) -> bytes:
    """Render an HTML string (the ESF template in mode='pdf') to PDF bytes."""
    _ensure_native_libs()
    from weasyprint import HTML  # lazy: app boots even if native libs are absent

    css_text = _CSS_PATH.read_text(encoding="utf-8")

    def fetcher(url: str):
        if url.endswith("esf_form.css"):
            return {"string": css_text, "mime_type": "text/css"}
        if "/static/fonts/" in url and url.endswith(".ttf"):
            ttf = _STATIC_DIR / "fonts" / url.rsplit("/", 1)[1]
            if ttf.exists():
                return {"string": ttf.read_bytes(), "mime_type": "font/ttf"}
        if "/qr/" in url and url.endswith(".png"):
            png = _QR_DIR / url.rsplit("/", 1)[1]
            if png.exists():
                return {"string": png.read_bytes(), "mime_type": "image/png"}
        # Fail closed: the ESF PDF needs only the bundled css/fonts/qr assets. Any
        # other URL (a stray http:// or file://) is refused rather than fetched, so
        # there is no SSRF / local-file disclosure even if a template ever emits an
        # unexpected resource URL.
        return {"string": b"", "mime_type": "application/octet-stream"}

    return HTML(string=html, base_url="http://esf.local/", url_fetcher=fetcher).write_pdf()


def render_esf_pdf(esf: dict) -> bytes:
    """Render one serialized ESF payload (the template-ready dict) to PDF bytes.

    Owns the template render + WeasyPrint step so the router stays a thin controller.
    CPU-bound; FastAPI runs the sync PDF route in a threadpool, so no extra offload
    is needed here (the batch path offloads explicitly via run_in_threadpool)."""
    return render_pdf(_render_html(esf))


def render_esf_zip(named_docs: List[Tuple[str, dict]]) -> bytes:
    """Render several ESF payloads into one ZIP: each `(filename, esf)` becomes a PDF.

    Pure CPU work (template render + WeasyPrint, no DB access) so callers offload it
    to a threadpool. The serialization/DB access happens in the request context before
    this is called."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, esf in named_docs:
            zf.writestr(filename, render_pdf(_render_html(esf)))
    return buf.getvalue()
