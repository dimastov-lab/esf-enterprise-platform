"""ESFParty — supplier (201-208) and buyer (301-308) requisites."""
from typing import Optional

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PartyType


class ESFParty(Base):
    __tablename__ = "esf_parties"
    __table_args__ = (
        UniqueConstraint("document_id", "party_type", name="uq_party_document_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    party_type: Mapped[PartyType] = mapped_column(Enum(PartyType, name="party_type"), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(20))
    name: Mapped[Optional[str]] = mapped_column(String(500))
    branch_inn: Mapped[Optional[str]] = mapped_column(String(20))      # 203/303
    branch: Mapped[Optional[str]] = mapped_column(String(500))         # 204/304 (name)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    tax_office_code: Mapped[Optional[str]] = mapped_column(String(20))  # 206/306 code boxes
    tax_office: Mapped[Optional[str]] = mapped_column(String(255))      # 206/306 name
    bank: Mapped[Optional[str]] = mapped_column(String(255))
    bik: Mapped[Optional[str]] = mapped_column(String(20))
    account: Mapped[Optional[str]] = mapped_column(String(50))

    document: Mapped["ESFDocument"] = relationship(back_populates="parties")  # noqa: F821
