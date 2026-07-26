"""QR generation for ESF verification.

The QR encodes the public check URL. By default (dev) that is the bare path
`/esf/check-esf?documentUUID={uuid}`; if PUBLIC_BASE_URL is configured the QR
encodes the absolute URL so a phone scanner can open it.
"""
import io
from pathlib import Path

import qrcode

from app.core.config import settings

# backend/storage/qr  (app/services/qr_service.py -> app -> backend)
STORAGE_QR_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "qr"


def public_check_path(doc_uuid: str) -> str:
    return f"/esf/check-esf?documentUUID={doc_uuid}"


def qr_target(doc_uuid: str) -> str:
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    path = public_check_path(doc_uuid)
    return f"{base}{path}" if base else path


def qr_png_bytes(data: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def write_qr_file(doc_uuid: str) -> str:
    """Generate and persist storage/qr/{uuid}.png; return its path."""
    STORAGE_QR_DIR.mkdir(parents=True, exist_ok=True)
    path = STORAGE_QR_DIR / f"{doc_uuid}.png"
    path.write_bytes(qr_png_bytes(qr_target(doc_uuid)))
    return str(path)
