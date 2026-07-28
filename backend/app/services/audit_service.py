"""Audit logging — records critical actions (CLAUDE.md requirement).

Append-only writes to `audit_logs`. Call `record(...)` after the action succeeds.
Failures to write an audit row must never break the user action, so writes are
best-effort (rolled back on error without propagating).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.observability import client_ip
from app.models import AuditLog

# Action vocabulary
LOGIN = "LOGIN"
LOGIN_FAILED = "LOGIN_FAILED"
LOGOUT = "LOGOUT"
CREATE = "CREATE"
VALIDATE = "VALIDATE"
PUBLISH = "PUBLISH"
DELETE = "DELETE"
VIEW_PUBLIC = "VIEW_PUBLIC"
DOWNLOAD_PDF = "DOWNLOAD_PDF"


def record(db: Session, action: str, *, user=None, document=None, request=None,
           meta: Optional[dict] = None) -> None:
    ip = None
    ua = None
    if request is not None:
        ip = client_ip(request)
        ua = request.headers.get("user-agent")
    entry = AuditLog(
        user_id=getattr(user, "id", None),
        document_id=getattr(document, "id", None),
        action=action,
        ip_address=ip,
        user_agent=ua,
        meta_json=meta,
    )
    try:
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
