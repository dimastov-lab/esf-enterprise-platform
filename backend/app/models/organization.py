"""Organization model — the legal entity that owns ESF documents."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[List["ESFDocument"]] = relationship(  # noqa: F821
        back_populates="organization"
    )
