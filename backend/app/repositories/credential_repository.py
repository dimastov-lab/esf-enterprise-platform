"""Data access for ApiCredential."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_credential import ApiCredential


class CredentialRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_hash(self, token_hash: str) -> Optional[ApiCredential]:
        return (
            self.db.query(ApiCredential)
            .filter(ApiCredential.token_hash == token_hash)
            .one_or_none()
        )

    def list_for_user(self, user_id: int) -> List[ApiCredential]:
        return (
            self.db.query(ApiCredential)
            .filter(ApiCredential.user_id == user_id)
            .order_by(ApiCredential.created_at.desc())
            .all()
        )

    def create(
        self,
        user_id: int,
        token_hash: str,
        label: Optional[str],
        expires_at: Optional[datetime],
    ) -> ApiCredential:
        cred = ApiCredential(
            user_id=user_id,
            token_hash=token_hash,
            label=label,
            expires_at=expires_at,
        )
        self.db.add(cred)
        self.db.commit()
        self.db.refresh(cred)
        return cred

    def revoke(self, credential: ApiCredential) -> None:
        credential.revoked_at = datetime.utcnow()
        self.db.commit()

    def touch(self, credential: ApiCredential) -> None:
        """Update last_used_at without blocking the request on commit."""
        credential.last_used_at = datetime.utcnow()
        self.db.commit()

    def get_for_user(self, credential_id: int, user_id: int) -> Optional[ApiCredential]:
        return (
            self.db.query(ApiCredential)
            .filter(
                ApiCredential.id == credential_id,
                ApiCredential.user_id == user_id,
            )
            .one_or_none()
        )

    def delete_expired(self) -> int:
        """Purge rows that are both revoked and past their expiry. Returns count deleted."""
        now = datetime.utcnow()
        rows = (
            self.db.query(ApiCredential)
            .filter(
                ApiCredential.revoked_at.isnot(None),
                ApiCredential.expires_at.isnot(None),
                ApiCredential.expires_at < func.now(),
            )
            .all()
        )
        for row in rows:
            self.db.delete(row)
        if rows:
            self.db.commit()
        return len(rows)
