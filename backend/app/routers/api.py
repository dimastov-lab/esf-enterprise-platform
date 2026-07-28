"""Authenticated JSON API for the editor (counterparty lookup).

Search requires a logged-in user; there is no public access to the directory.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.counterparty_service import CounterpartyService
from app.services.good_service import GoodService

router = APIRouter()


@router.get("/api/counterparties/search")
def counterparties_search(q: str = "", db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """Search the counterparty directory by INN or name (max 10).

    Auth required (get_current_user). Returns JSON list ordered: exact-INN match,
    most recently used, then name. Scoped to the caller's own directory.
    """
    return JSONResponse({"results": CounterpartyService(db).search(user.id, q)})


@router.get("/api/counterparties/recent")
def counterparties_recent(db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """Most-recently-used counterparties for the editor's right panel.

    Auth required; there is no public access to the directory. Scoped to the caller.
    """
    return JSONResponse({"results": CounterpartyService(db).recent(user.id)})


@router.get("/api/goods/search")
def goods_search(q: str = "", db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Search the goods catalog by name or ТН ВЭД code (max 10).

    Auth required. Ordered: favorites, most-used, recent, name. Scoped to the caller.
    """
    return JSONResponse({"results": GoodService(db).search(user.id, q)})


@router.get("/api/goods/recent")
def goods_recent(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Most-relevant goods (favorites + recently used) for the editor panel. Scoped to the caller."""
    return JSONResponse({"results": GoodService(db).recent(user.id)})


@router.get("/api/esf")
def esf_list(page: int = 1, page_size: int = 25, q: str = "", status: str = "",
             currency: str = "", supplier: str = "", buyer: str = "",
             date_from: str = "", date_to: str = "", sort: str = "updated", dir: str = "desc",
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Server-side paginated/searched/sorted/filtered document list (v6.1).

    Returns {items, page, page_size, total, total_pages}. Auth required; scoped to
    the user's own documents (admins see all)."""
    from datetime import datetime

    from app.services.esf_service import ESFService

    def _d(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date() if s else None
        except ValueError:
            return None

    r = ESFService(db).page(
        user, page=page, page_size=page_size, q=q, status=status, currency=currency,
        supplier=supplier, buyer=buyer, date_from=_d(date_from), date_to=_d(date_to),
        sort=sort, direction=dir,
    )
    return JSONResponse({"items": r["rows"], "page": r["page"], "page_size": r["page_size"],
                         "total": r["total"], "total_pages": r["total_pages"]})
