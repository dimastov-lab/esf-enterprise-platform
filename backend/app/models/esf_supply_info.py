"""ESFSupplyInfo — section 2 «Информация о реализации» (1:1 with a document)."""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ESFSupplyInfo(Base):
    __tablename__ = "esf_supply_info"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="CASCADE"), primary_key=True
    )
    supply_date: Mapped[Optional[date]] = mapped_column(Date)
    supply_type: Mapped[Optional[str]] = mapped_column(String(100))
    payment_type: Mapped[Optional[str]] = mapped_column(String(100))
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_date: Mapped[Optional[date]] = mapped_column(Date)
    correction_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    correction_number: Mapped[Optional[str]] = mapped_column(String(100))   # 406 № исходной ЭСФ
    correction_date: Mapped[Optional[date]] = mapped_column(Date)            # 406 дата исходной ЭСФ
    correction_reason: Mapped[Optional[str]] = mapped_column(Text)
    currency_code: Mapped[Optional[str]] = mapped_column(String(10))
    currency_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    note: Mapped[Optional[str]] = mapped_column(Text)

    document: Mapped["ESFDocument"] = relationship(back_populates="supply_info")  # noqa: F821
