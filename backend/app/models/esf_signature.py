"""ESFSignature — section «450» signatory block (1:1 with a document)."""
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ESFSignature(Base):
    __tablename__ = "esf_signatures"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("esf_documents.id", ondelete="CASCADE"), primary_key=True
    )
    director_name: Mapped[Optional[str]] = mapped_column(String(255))
    signature_date: Mapped[Optional[date]] = mapped_column(Date)

    document: Mapped["ESFDocument"] = relationship(back_populates="signature")  # noqa: F821
