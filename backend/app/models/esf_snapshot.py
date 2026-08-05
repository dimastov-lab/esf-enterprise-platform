"""ESFSnapshot — immutable, write-once frozen copy taken at publish time.

`payload_json` is the legal source of truth for public/PDF rendering; `sha256`
is the content hash of the canonical payload. Rows are never updated.
"""
import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, event, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ESFSnapshot(Base):
    __tablename__ = "esf_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False, default=uuid_pkg.uuid4
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    immutable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    aios_memory_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    document: Mapped["ESFDocument"] = relationship(back_populates="snapshots")  # noqa: F821


class SnapshotImmutableError(Exception):
    """Raised when code attempts to modify or delete a frozen snapshot."""


@event.listens_for(ESFSnapshot, "before_update")
def _block_snapshot_update(mapper, connection, target):  # noqa: ANN001
    raise SnapshotImmutableError("ESFSnapshot is immutable and cannot be updated.")


@event.listens_for(ESFSnapshot, "before_delete")
def _block_snapshot_delete(mapper, connection, target):  # noqa: ANN001
    raise SnapshotImmutableError("ESFSnapshot is immutable and cannot be deleted.")
