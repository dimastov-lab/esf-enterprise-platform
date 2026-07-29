"""Good — a reusable goods-catalog entry (SMART GOODS, Module 34).

Populated automatically on ESF save (upsert by name) and used by the editor's
item autocomplete and the "recent goods" panel. Not part of the STI-007
document or any snapshot.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Good(Base):
    __tablename__ = "goods"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Owner scoping (H1): the catalog is per-user, not a shared global directory.
    # NOT NULL — legacy pre-scoping rows (owner_id NULL) were purged in migration
    # b1c2d3e4f5a6 (A-7); every code path that inserts a row sets owner_id.
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[Optional[str]] = mapped_column(String(50), index=True)   # ТН ВЭД
    name: Mapped[Optional[str]] = mapped_column(String(500), index=True)  # dedup key (case-insensitive)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 5))
    vat_rate: Mapped[Optional[str]] = mapped_column(String(20))
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
