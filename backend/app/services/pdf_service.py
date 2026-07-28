"""Render the ESF PDF from the SAME HTML template (no separate PDF layout).

Renderer: WeasyPrint. It reproduces the STI-007 `templates/esf/form.html` layout
(flexbox rows, boxed digits, the goods table, totals, footer) accurately and emits
true vector/selectable text in A4 landscape via the stylesheet's `@page` rule, so the
PDF stays identical to the HTML and there is no duplicate layout to maintain.

The template's `<link href="/static/css/esf_form.css">` is resolved by a small
url_fetcher that serves the bundled stylesheet, so rendering needs no running web
server and no network.
"""
import os
import sys
from pathlib import Path

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_CSS_PATH = _STATIC_DIR / "css" / "esf_form.css"
_QR_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "qr"


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
