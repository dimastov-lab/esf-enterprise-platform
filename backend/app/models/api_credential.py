"""Long-lived API credentials stored in PostgreSQL.

Short-lived JWTs from /auth/token are stateless (60 min, no DB check).
ApiCredential is for programmatic long-term access: each token is an
opaque bearer string stored here as a SHA-256 hash (never the plaintext).
Credentials can carry an explicit expiry and can be revoked at any time.

Token format: ``esf_<base64url(32 random bytes)>``
The ``esf_`` prefix makes leaked credentials detectable by secret scanners.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApiCredential(Base):
    __tablename__ = "api_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 hex of the raw token — the plaintext is returned exactly once
    # at creation and never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # NULL expires_at means the credential never expires.
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="api_credentials")  # noqa: F821

    __table_args__ = (
        Index("ix_api_credentials_token_hash", "token_hash"),
    )

    @property
    def is_active(self) -> bool:
        """False when revoked or past the expiry timestamp."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and datetime.utcnow() >= self.expires_at.replace(tzinfo=None):
            return False
        return True
