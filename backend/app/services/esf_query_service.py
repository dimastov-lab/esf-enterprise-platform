"""Read side of the ESF domain (audit A-1): document lookup + owner/admin access,
server-side pagination/search/sort/filter, dashboard aggregates, and rendering a
published document from its immutable snapshot.

No mutation happens here — all lifecycle/write operations live in ESFService. This
service owns queries only and delegates presentation to ESFSerializer.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException

from app.core.security import require_owner_or_admin
from app.models import DocumentStatus, ESFDocument, User
from app.repositories.esf_document_repository import ESFDocumentRepository
from app.services import snapshot_service
from app.services.esf_serializer import ESFSerializer

_log = logging.getLogger("esf.error")


class ESFQueryService:
    def __init__(self, db):
        self.repo = ESFDocumentRepository(db)
        self.serializer = ESFSerializer()

    # ---- lookup + access ----------------------------------------------
    def get_for_user(self, doc_uuid: str, user: User) -> Optional[ESFDocument]:
        doc = self.repo.get_by_uuid(doc_uuid)
        if doc is None:
            return None
        require_owner_or_admin(doc, user)
        return doc

    def get_public(self, doc_uuid: str) -> Optional[ESFDocument]:
        """Public lookup (no owner guard). Used by the open verification page / QR."""
        return self.repo.get_by_uuid(doc_uuid)

    # ---- lists / pagination / stats -----------------------------------
    def list_rows(self, user: User) -> List[dict]:
        # kept for compatibility; the dashboard now uses page() (server-side)
        return [self.serializer.serialize_row(doc) for doc in self.repo.list_for_user(user)]

    def page(self, user: User, *, page: int = 1, page_size: int = 25, q: str = "",
             status: str = "", currency: str = "", supplier: str = "", buyer: str = "",
             date_from=None, date_to=None, sort: str = "updated", direction: str = "desc") -> dict:
        """One server-side page: pagination + search + sort + filters. Returns the
        page rows plus {page, page_size, total, total_pages} for the UI / JSON API."""
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 25)))
        sort = sort if sort in {"created", "updated", "number", "status", "date", "supplier", "buyer"} else "updated"
        direction = "asc" if str(direction).lower() == "asc" else "desc"
        status_enum = None
        if status:
            try:
                status_enum = DocumentStatus(status)
            except ValueError:
                status_enum = None
        items, total = self.repo.paginate_for_user(
            user, page=page, page_size=page_size, sort=sort, direction=direction,
            search=(q or "").strip() or None, status=status_enum,
            currency=(currency or "").strip() or None,
            supplier=(supplier or "").strip() or None, buyer=(buyer or "").strip() or None,
            date_from=date_from, date_to=date_to,
        )
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "rows": [self.serializer.serialize_row(d) for d in items],
            "page": page, "page_size": page_size, "total": total, "total_pages": total_pages,
            "sort": sort, "dir": direction,
        }

    def dashboard_stats(self, user: User) -> dict:
        """Aggregate counts + a 7-day activity series — two GROUP BY queries, no
        row loading (scales to any dataset size)."""
        counts = self.repo.status_counts(user)
        today = datetime.now(timezone.utc).date()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]  # oldest -> newest
        created = self.repo.created_counts_since(user, days[0])
        week = [{"day": d.strftime("%d.%m"), "count": created.get(d, 0)} for d in days]
        return {
            "total": sum(counts.values()),
            "drafts": counts.get(DocumentStatus.DRAFT.value, 0),
            "validated": counts.get(DocumentStatus.VALIDATED.value, 0),
            "published": counts.get(DocumentStatus.PUBLISHED.value, 0),
            "cancelled": counts.get(DocumentStatus.CANCELLED.value, 0),
            "today": created.get(today, 0),
            "week": week,
            "week_max": max([w["count"] for w in week] + [1]),
        }

    # ---- published rendering (from the immutable snapshot) ------------
    def serialize_published(self, doc: ESFDocument) -> dict:
        """Render data for a published doc from its immutable snapshot.

        The stored sha256 is re-verified against the payload on every read, so any
        DB-level tampering with `payload_json` (which the append-only triggers make
        hard, but this is defence-in-depth) is caught and fails closed instead of
        serving a corrupted legal record.
        """
        snap = self.repo.latest_snapshot(doc)
        if snap is None:
            return self.serializer.serialize(doc)
        if snapshot_service.content_hash(snap.payload_json) != snap.sha256:
            _log.error(
                "snapshot integrity check failed",
                extra={"document_uuid": str(doc.uuid), "snapshot_id": snap.id},
            )
            raise HTTPException(
                status_code=500,
                detail="Снимок документа повреждён (нарушена целостность). "
                       "Обратитесь к администратору.",
            )
        return snap.payload_json
