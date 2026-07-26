"""Counterparty — a reusable supplier/buyer directory entry.

Populated automatically on ESF save (upsert by INN) and used by the editor's
search-as-you-type lookup. Not part of the STI-007 document or any snapshot.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Counterparty(Base):
    __tablename__ = "counterparties"

    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    branch: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    tax_office: Mapped[Optional[str]] = mapped_column(String(255))
    bank: Mapped[Optional[str]] = mapped_column(String(255))
    bik: Mapped[Optional[str]] = mapped_column(String(20))
    account: Mapped[Optional[str]] = mapped_column(String(50))
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
