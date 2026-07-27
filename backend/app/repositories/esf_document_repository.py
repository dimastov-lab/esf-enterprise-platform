"""Data access for ESF documents (no business logic here)."""
import uuid as uuid_pkg
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import asc, desc, exists, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ESFDocument,
    ESFParty,
    ESFSnapshot,
    ESFSupplyInfo,
    PartyType,
    User,
)

# server-side sortable columns (indexed ones are cheap; supplier/buyer use a
# correlated subquery and are slower on huge datasets — see SCALABILITY_REPORT.md)
_SORT_KEYS = {"created", "updated", "number", "status", "date", "supplier", "buyer"}


class ESFDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def last_supplier_for(self, user: User) -> Optional[ESFParty]:
        """The supplier party from this user's most recent document (the supplier
        is almost always the same organisation, so new drafts can prefill it)."""
        return (
            self.db.query(ESFParty)
            .join(ESFDocument, ESFParty.document_id == ESFDocument.id)
            .filter(
                ESFDocument.owner_id == user.id,
                ESFParty.party_type == PartyType.SUPPLIER,
                ESFParty.name.isnot(None),
            )
            .order_by(ESFDocument.updated_at.desc())
            .first()
        )

    def list_for_user(self, user: User) -> List[ESFDocument]:
        q = self.db.query(ESFDocument).options(selectinload(ESFDocument.parties))
        if not user.is_admin:
            q = q.filter(ESFDocument.owner_id == user.id)
        return q.order_by(ESFDocument.updated_at.desc()).all()

    # ---- server-side pagination / search / sort / filter (v6.1) --------
    def _party_name_subq(self, ptype: PartyType):
        return (
            select(ESFParty.name)
            .where((ESFParty.document_id == ESFDocument.id) & (ESFParty.party_type == ptype))
            .order_by(ESFParty.id).limit(1)
            .correlate(ESFDocument).scalar_subquery()
        )

    def _filtered(self, user, *, search=None, status=None, currency=None,
                  supplier=None, buyer=None, date_from=None, date_to=None):
        q = self.db.query(ESFDocument)
        if not user.is_admin:
            q = q.filter(ESFDocument.owner_id == user.id)
        if status is not None:
            q = q.filter(ESFDocument.status == status)
        if date_from is not None:
            q = q.filter(ESFDocument.created_at >= date_from)
        if date_to is not None:
            q = q.filter(ESFDocument.created_at < date_to + timedelta(days=1))  # inclusive day
        if currency:
            q = q.filter(exists().where(
                (ESFSupplyInfo.document_id == ESFDocument.id) & (ESFSupplyInfo.currency_code == currency)))
        if supplier:
            like = f"%{supplier}%"
            q = q.filter(exists().where(
                (ESFParty.document_id == ESFDocument.id) & (ESFParty.party_type == PartyType.SUPPLIER) & ESFParty.name.ilike(like)))
        if buyer:
            like = f"%{buyer}%"
            q = q.filter(exists().where(
                (ESFParty.document_id == ESFDocument.id) & (ESFParty.party_type == PartyType.BUYER) & ESFParty.name.ilike(like)))
        if search:
            like = f"%{search}%"
            party_hit = exists().where(
                (ESFParty.document_id == ESFDocument.id) & (ESFParty.name.ilike(like) | ESFParty.inn.ilike(like)))
            note_hit = exists().where(
                (ESFSupplyInfo.document_id == ESFDocument.id) &
                (ESFSupplyInfo.note.ilike(like) | ESFSupplyInfo.currency_code.ilike(like)))
            q = q.filter(or_(ESFDocument.esf_number.ilike(like), party_hit, note_hit))
        return q

    def _order_expr(self, sort: str, direction: str):
        d = asc if direction == "asc" else desc
        if sort == "number":
            col = ESFDocument.esf_number
        elif sort == "status":
            col = ESFDocument.status
        elif sort in ("created", "date"):
            col = ESFDocument.created_at
        elif sort == "supplier":
            col = self._party_name_subq(PartyType.SUPPLIER)
        elif sort == "buyer":
            col = self._party_name_subq(PartyType.BUYER)
        else:  # "updated" (default)
            col = ESFDocument.updated_at
        return d(col)

    def paginate_for_user(self, user, *, page=1, page_size=25, sort="updated",
                          direction="desc", **filters) -> Tuple[List[ESFDocument], int]:
        """One page of documents + total count. 3 queries total regardless of
        dataset size: COUNT, the page (LIMIT/OFFSET), and a selectinload for the
        page's parties (no N+1, no `.all()` over the whole table)."""
        q = self._filtered(user, **filters)
        total = q.with_entities(func.count(ESFDocument.id)).order_by(None).scalar() or 0
        items = (
            q.options(selectinload(ESFDocument.parties))
            .order_by(self._order_expr(sort, direction), ESFDocument.id.desc())  # stable tiebreaker
            .offset((page - 1) * page_size).limit(page_size).all()
        )
        return items, total

    def status_counts(self, user) -> Dict[str, int]:
        """One GROUP BY query — counts per status (no row loading)."""
        q = self.db.query(ESFDocument.status, func.count(ESFDocument.id))
        if not user.is_admin:
            q = q.filter(ESFDocument.owner_id == user.id)
        return {s.value: c for s, c in q.group_by(ESFDocument.status).all()}

    def created_counts_since(self, user, since: date) -> Dict[date, int]:
        """One GROUP BY query — documents created per day since `since`.

        Buckets by the UTC calendar date so it lines up with `dashboard_stats`,
        which derives "today" from `datetime.now(timezone.utc)`. Grouping in the
        DB session's local timezone previously skewed the "today" count near the
        UTC day boundary.
        """
        day = func.date(func.timezone("UTC", ESFDocument.created_at))
        q = self.db.query(day, func.count(ESFDocument.id)).filter(ESFDocument.created_at >= since)
        if not user.is_admin:
            q = q.filter(ESFDocument.owner_id == user.id)
        out: Dict[date, int] = {}
        for d, c in q.group_by(day).all():
            out[d if isinstance(d, date) else date.fromisoformat(str(d))] = c
        return out

    def get_by_uuid(self, doc_uuid: str) -> Optional[ESFDocument]:
        try:
            key = uuid_pkg.UUID(str(doc_uuid))
        except (ValueError, AttributeError, TypeError):
            return None
        return (
            self.db.query(ESFDocument)
            .filter(ESFDocument.uuid == key)
            .one_or_none()
        )

    def lock(self, doc: ESFDocument) -> None:
        """Take a row lock on `doc` and refresh it to the committed state.

        Used at the start of every mutating service method so concurrent
        publish/save/validate/cancel/delete requests serialize on the document
        row and re-check the *fresh* status under the lock (SELECT ... FOR UPDATE),
        instead of acting on a stale in-memory copy. The lock is held until the
        transaction commits.
        """
        self.db.refresh(doc, with_for_update=True)

    def add(self, doc: ESFDocument) -> ESFDocument:
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def commit(self) -> None:
        self.db.commit()

    def delete(self, doc: ESFDocument) -> None:
        self.db.delete(doc)
        self.db.commit()

    def number_exists(self, number: str) -> bool:
        return (
            self.db.query(ESFDocument.id)
            .filter(ESFDocument.esf_number == number)
            .first()
            is not None
        )

    def next_number_seq(self) -> int:
        """Atomically allocate the next ESF number counter from the DB sequence.

        `nextval` is concurrency-safe (never hands the same value to two callers),
        which removes the count()+1 race. Values are non-transactional (a rolled
        back publish leaves a gap) — gaps in the counter are acceptable.
        """
        return int(self.db.execute(text("SELECT nextval('esf_number_seq')")).scalar())

    def latest_snapshot(self, doc: ESFDocument) -> Optional[ESFSnapshot]:
        return (
            self.db.query(ESFSnapshot)
            .filter(ESFSnapshot.document_id == doc.id)
            .order_by(ESFSnapshot.created_at.desc(), ESFSnapshot.id.desc())
            .first()
        )
