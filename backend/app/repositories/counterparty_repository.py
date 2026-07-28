"""Data access for the counterparty directory."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models import Counterparty

_FIELDS = ("name", "branch", "address", "tax_office", "bank", "bik", "account")


class CounterpartyRepository:
    def __init__(self, db: Session):
        self.db = db

    def search(self, owner_id: int, q: str, limit: int = 10) -> List[Counterparty]:
        q = (q or "").strip()
        if not q:
            return []
        exact_first = case((Counterparty.inn == q, 0), else_=1)
        return (
            self.db.query(Counterparty)
            .filter(Counterparty.owner_id == owner_id)
            .filter(or_(Counterparty.inn.ilike(f"{q}%"), Counterparty.name.ilike(f"%{q}%")))
            .order_by(
                exact_first,
                Counterparty.is_favorite.desc(),
                Counterparty.use_count.desc(),
                Counterparty.last_used_at.desc().nullslast(),
                Counterparty.name.asc(),
            )
            .limit(limit)
            .all()
        )

    def recent(self, owner_id: int, limit: int = 8) -> List[Counterparty]:
        """Most-recently-used counterparties (for the editor's right panel)."""
        return (
            self.db.query(Counterparty)
            .filter(Counterparty.owner_id == owner_id)
            .filter(Counterparty.last_used_at.isnot(None))
            .order_by(
                Counterparty.is_favorite.desc(),
                Counterparty.last_used_at.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_by_owner_inn(self, owner_id: int, inn: str) -> Optional[Counterparty]:
        return (
            self.db.query(Counterparty)
            .filter(Counterparty.owner_id == owner_id, Counterparty.inn == inn)
            .one_or_none()
        )

    def upsert(self, owner_id: int, data: dict) -> Optional[Counterparty]:
        """Insert/update a counterparty for `owner_id`, keyed by INN. No-op without an INN."""
        inn = (data.get("inn") or "").strip()
        if not inn:
            return None
        cp = self.get_by_owner_inn(owner_id, inn)
        if cp is None:
            cp = Counterparty(owner_id=owner_id, inn=inn)
            self.db.add(cp)
        for field in _FIELDS:
            value = data.get(field)
            if value:  # only overwrite with real values; never blank an existing entry
                setattr(cp, field, value)
        cp.use_count = (cp.use_count or 0) + 1
        cp.last_used_at = datetime.now(timezone.utc)
        return cp
