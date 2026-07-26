from datetime import datetime

from app.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", backref="snapshots")  # noqa: F821
