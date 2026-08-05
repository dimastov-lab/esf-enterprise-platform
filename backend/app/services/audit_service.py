"""Audit logging — records critical actions (CLAUDE.md requirement).

Append-only writes to `audit_logs`. Call `record(...)` after the action succeeds.
Failures to write an audit row must never break the user action, so writes are
best-effort (rolled back on error without propagating).
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.observability import client_ip
from app.models import AuditLog

_log = logging.getLogger("esf.audit")

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
CREDENTIAL_ISSUED = "CREDENTIAL_ISSUED"
CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"


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
        # An audit-write failure must never break the user action, but a silent
        # drop is a compliance blind spot (this is the audit trail). Log why it
        # failed — append-only trigger, DB unavailable, etc. — before swallowing.
        db.rollback()
        _log.warning(
            "audit write failed; action %s not recorded", action,
            extra={
                "audit_user_id": getattr(user, "id", None),
                "audit_document_id": getattr(document, "id", None),
            },
            exc_info=True,
        )
