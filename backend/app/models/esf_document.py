"""ESFDocument — the editable header / lifecycle row of an STI-007 ESF.

Public access uses `uuid` (v4), never the sequential `id`.
"""
import uuid as uuid_pkg
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DocumentStatus


class ESFDocument(Base):
    __tablename__ = "esf_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False, default=uuid_pkg.uuid4
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.DRAFT,
        server_default=DocumentStatus.DRAFT.value,
        index=True,
    )
    esf_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # 103 Дата оформления
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # self-reference: set when this draft is a correction of an already-published ESF
    corrects_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="SET NULL"), nullable=True
    )
    # Auxiliary raw payload (integration/round-trip). NOT the form's source of truth.
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="documents")  # noqa: F821
    organization: Mapped[Optional["Organization"]] = relationship(  # noqa: F821
        back_populates="documents"
    )
    parties: Mapped[List["ESFParty"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
    items: Mapped[List["ESFItem"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
    supply_info: Mapped[Optional["ESFSupplyInfo"]] = relationship(  # noqa: F821
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    totals: Mapped[Optional["ESFTotals"]] = relationship(  # noqa: F821
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    signature: Mapped[Optional["ESFSignature"]] = relationship(  # noqa: F821
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    snapshots: Mapped[List["ESFSnapshot"]] = relationship(  # noqa: F821
        back_populates="document"
    )
