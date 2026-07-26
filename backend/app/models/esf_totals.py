"""ESFTotals — invoice totals «Итого» (1:1 with a document)."""
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ESFTotals(Base):
    __tablename__ = "esf_totals"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="CASCADE"), primary_key=True
    )
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    vat_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    nsp_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    grand_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    currency_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))

    document: Mapped["ESFDocument"] = relationship(back_populates="totals")  # noqa: F821
