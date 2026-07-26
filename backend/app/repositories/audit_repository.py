"""Read access for the audit log."""
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models import AuditLog, User


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_recent(self, limit: int = 200) -> List[Tuple[AuditLog, str]]:
        return (
            self.db.query(AuditLog, User.username)
            .outerjoin(User, AuditLog.user_id == User.id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .all()
        )
