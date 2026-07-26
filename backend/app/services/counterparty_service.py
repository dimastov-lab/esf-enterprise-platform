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

    def search(self, q: str) -> List[dict]:
        return [_to_dict(cp) for cp in self.repo.search(q)]

    def recent(self, limit: int = 8) -> List[dict]:
        return [_to_dict(cp) for cp in self.repo.recent(limit)]

    def upsert_party(self, party: ESFParty) -> None:
        """Upsert a supplier/buyer party into the directory (keyed by INN)."""
        if not party or not party.inn:
            return
        self.repo.upsert({
            "inn": party.inn,
            "name": party.name,
            "branch": party.branch,
            "address": party.address,
            "tax_office": party.tax_office,
            "bank": party.bank,
            "bik": party.bik,
            "account": party.account,
        })
