"""ESFItem — section 3 «Информация о товаре» line items.

Monetary precision: prices/quantities 5 dp, money 2 dp (matches the form).
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ESFItem(Base):
    __tablename__ = "esf_items"
    __table_args__ = (
        UniqueConstraint("document_id", "row_number", name="uq_item_document_row"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[Optional[str]] = mapped_column(String(100))
    tnved_code: Mapped[Optional[str]] = mapped_column(String(50))
    product_name: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 5))
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 5))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    vat_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    nsp: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    customs_refs: Mapped[Optional[str]] = mapped_column(String(255))  # Реквизиты таможенной декларации/ЭСФ

    document: Mapped["ESFDocument"] = relationship(back_populates="items")  # noqa: F821
