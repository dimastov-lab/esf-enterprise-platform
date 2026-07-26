"""Data access for the goods catalog (SMART GOODS)."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Good

_FIELDS = ("code", "unit", "price", "vat_rate")


class GoodRepository:
    def __init__(self, db: Session):
        self.db = db

    def search(self, q: str, limit: int = 10) -> List[Good]:
        q = (q or "").strip()
        if not q:
            return []
        return (
            self.db.query(Good)
            .filter(or_(Good.name.ilike(f"%{q}%"), Good.code.ilike(f"{q}%")))
            .order_by(
                Good.is_favorite.desc(),
                Good.use_count.desc(),
                Good.last_used_at.desc().nullslast(),
                Good.name.asc(),
            )
            .limit(limit)
            .all()
        )

    def recent(self, limit: int = 8) -> List[Good]:
        return (
            self.db.query(Good)
            .order_by(
                Good.is_favorite.desc(),
                Good.last_used_at.desc().nullslast(),
                Good.use_count.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_by_name(self, name: str) -> Optional[Good]:
        name = (name or "").strip()
        if not name:
            return None
        return (
            self.db.query(Good)
            .filter(func.lower(Good.name) == name.lower())
            .first()
        )

    def upsert(self, data: dict) -> Optional[Good]:
        """Insert/update a catalog good keyed by name (case-insensitive).
        Increments the usage counter on every save."""
        name = (data.get("name") or "").strip()
        if not name:
            return None
        good = self.get_by_name(name)
        if good is None:
            good = Good(name=name)
            self.db.add(good)
        for f in _FIELDS:
            value = data.get(f)
            if value not in (None, ""):
                setattr(good, f, value)
        good.use_count = (good.use_count or 0) + 1
        good.last_used_at = datetime.now(timezone.utc)
        return good

    def set_favorite(self, good_id: int, value: bool) -> Optional[Good]:
        good = self.db.get(Good, good_id)
        if good is not None:
            good.is_favorite = bool(value)
        return good
