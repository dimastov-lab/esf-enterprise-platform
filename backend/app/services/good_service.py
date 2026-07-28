"""Goods catalog: autocomplete for the editor item table, recent/favorites,
and upsert on ESF save."""
from typing import List

from sqlalchemy.orm import Session

from app.models import ESFItem, Good
from app.repositories.good_repository import GoodRepository


def _to_dict(g: Good) -> dict:
    return {
        "id": g.id,
        "code": g.code or "",
        "name": g.name or "",
        "unit": g.unit or "",
        "price": ("" if g.price is None else format(g.price.normalize(), "f")),
        "vat_rate": g.vat_rate or "",
        "use_count": g.use_count or 0,
        "is_favorite": bool(g.is_favorite),
    }


class GoodService:
    def __init__(self, db: Session):
        self.repo = GoodRepository(db)

    def search(self, owner_id: int, q: str) -> List[dict]:
        return [_to_dict(g) for g in self.repo.search(owner_id, q)]

    def recent(self, owner_id: int, limit: int = 8) -> List[dict]:
        return [_to_dict(g) for g in self.repo.recent(owner_id, limit)]

    def set_favorite(self, good_id: int, value: bool) -> bool:
        return self.repo.set_favorite(good_id, value) is not None

    def upsert_item(self, item: ESFItem, owner_id: int) -> None:
        """Remember a saved line item in the owner's catalog (keyed by product name)."""
        if not item or not item.product_name:
            return
        self.repo.upsert(owner_id, {
            "name": item.product_name,
            "code": item.tnved_code,
            "unit": item.unit,
            "price": item.price,
            "vat_rate": (None if item.vat_rate is None else format(item.vat_rate.normalize(), "f")),
        })
