"""Counterparty directory: search for the editor lookup, and upsert on ESF save."""
from typing import List

from sqlalchemy.orm import Session

from app.models import Counterparty, ESFParty
from app.repositories.counterparty_repository import CounterpartyRepository

_FIELDS = ("inn", "name", "branch", "address", "tax_office", "bank", "bik", "account")


def _to_dict(cp: Counterparty) -> dict:
    return {f: getattr(cp, f) or "" for f in _FIELDS}


class CounterpartyService:
    def __init__(self, db: Session):
        self.repo = CounterpartyRepository(db)

    def search(self, owner_id: int, q: str) -> List[dict]:
        return [_to_dict(cp) for cp in self.repo.search(owner_id, q)]

    def recent(self, owner_id: int, limit: int = 8) -> List[dict]:
        return [_to_dict(cp) for cp in self.repo.recent(owner_id, limit)]

    def upsert_party(self, party: ESFParty, owner_id: int) -> None:
        """Upsert a supplier/buyer party into the owner's directory (keyed by INN)."""
        if not party or not party.inn:
            return
        self.repo.upsert(owner_id, {
            "inn": party.inn,
            "name": party.name,
            "branch": party.branch,
            "address": party.address,
            "tax_office": party.tax_office,
            "bank": party.bank,
            "bik": party.bik,
            "account": party.account,
        })
