"""ESF business logic: map between the STI-007 form and the normalized schema,
recompute totals, and own the draft create/edit/delete operations.

Controller (router) -> this service -> repository -> DB.
"""
import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.security import require_owner_or_admin
from app.models import (
    DocumentStatus,
    ESFDocument,
    ESFItem,
    ESFParty,
    ESFSignature,
    ESFSupplyInfo,
    ESFTotals,
    PartyType,
    User,
)
from app.repositories.esf_document_repository import ESFDocumentRepository
from app.services import snapshot_service
from app.services.esf_query_service import ESFQueryService
from app.services.esf_serializer import ESFSerializer
from app.services.validation_service import validate_document

_log = logging.getLogger("esf.error")

TWO = Decimal("0.01")

# Reject absurd magnitudes before money arithmetic so a huge input can't overflow
# the Decimal context (→ InvalidOperation) or the Numeric(20,2) columns (→ DataError)
# and surface as an opaque 500. 10^16 is far above any real invoice value.
_MAX_MONEY = Decimal(10) ** 16
_MAX_RATE = Decimal("9999.99")   # Numeric(6,2) capacity for item vat_rate


def _bounded(value: Optional[Decimal], label: str = "") -> Optional[Decimal]:
    """Raise a clean 400 if a monetary value is outside the sane range."""
    if value is not None and abs(value) > _MAX_MONEY:
        detail = f"Недопустимо большое числовое значение{(' (' + label + ')') if label else ''}."
        raise HTTPException(status_code=400, detail=detail)
    return value


# ESF numbers are digits + hyphens only (official format 000{YYYY}-004-{8 digits}).
# Enforced on save so a user-supplied number can never carry markup into a
# template (defence-in-depth against the inline-handler XSS class).
_ESF_NUMBER_RE = re.compile(r"^[0-9-]{1,40}$")

EDITABLE_STATUSES = {DocumentStatus.DRAFT, DocumentStatus.VALIDATED}


def _dec(s) -> Optional[Decimal]:
    s = (s or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_date(s) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d%m%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class ESFService:
    """Document lifecycle + coordinator.

    Owns every mutating operation (create / save / validate / publish / delete /
    duplicate / correct / cancel / batch) plus QR persistence, and stays the single
    entry point the routers use. Read/query and presentation were split out (audit
    A-1) into ESFQueryService and ESFSerializer; the thin pass-throughs below keep
    the public API stable while that logic lives in its own focused services.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ESFDocumentRepository(db)
        self.serializer = ESFSerializer()
        self.query = ESFQueryService(db)

    # ---- read side (delegated) ----------------------------------------
    def serialize(self, doc: ESFDocument) -> dict:
        return self.serializer.serialize(doc)

    def serialize_published(self, doc: ESFDocument) -> dict:
        return self.query.serialize_published(doc)

    def list_rows(self, user: User) -> List[dict]:
        return self.query.list_rows(user)

    def page(self, user: User, **kwargs) -> dict:
        return self.query.page(user, **kwargs)

    def dashboard_stats(self, user: User) -> dict:
        return self.query.dashboard_stats(user)

    def get_for_user(self, doc_uuid: str, user: User) -> Optional[ESFDocument]:
        return self.query.get_for_user(doc_uuid, user)

    def get_public(self, doc_uuid: str) -> Optional[ESFDocument]:
        return self.query.get_public(doc_uuid)

    def ensure_qr(self, doc: ESFDocument, commit: bool = True) -> bytes:
        """Generate + persist the QR PNG, record qr_path, and return the bytes.

        `commit=False` lets a caller fold the qr_path write into a larger
        transaction (used by the atomic publish so QR is not committed early)."""
        from app.services.qr_service import qr_png_bytes, qr_target, write_qr_file
        path = write_qr_file(str(doc.uuid))
        if doc.qr_path != path:
            doc.qr_path = path
            if commit:
                self.repo.commit()
        return qr_png_bytes(qr_target(str(doc.uuid)))

    # ---- create --------------------------------------------------------
    def create_draft(self, user: User) -> ESFDocument:
        doc = ESFDocument(owner_id=user.id, status=DocumentStatus.DRAFT)
        supplier = ESFParty(party_type=PartyType.SUPPLIER)
        # Carry the supplier over from the user's most recent document — it's
        # almost always the same organisation, so this removes re-entering it on
        # every new ESF. Buyer stays blank. (Only prefills a fresh draft; never
        # touches published docs/snapshots.)
        prev = self.repo.last_supplier_for(user)
        if prev is not None:
            for f in ("inn", "name", "branch_inn", "branch", "address",
                      "tax_office_code", "tax_office", "bank", "bik", "account"):
                setattr(supplier, f, getattr(prev, f))
        doc.parties = [
            supplier,
            ESFParty(party_type=PartyType.BUYER),
        ]
        doc.supply_info = ESFSupplyInfo(currency_code="643")
        doc.totals = ESFTotals()
        doc.signature = ESFSignature()
        doc.items = [ESFItem(row_number=1)]
        return self.repo.add(doc)

    _PARTY_FIELDS = ("inn", "name", "branch_inn", "branch", "address",
                     "tax_office_code", "tax_office", "bank", "bik", "account")

    def duplicate(self, doc: ESFDocument, user: User) -> ESFDocument:
        """Create a new editable DRAFT copied from `doc` (parties, supply info,
        goods, signatory). A fresh invoice: no number, no status/snapshot, blank
        issue date and correction refs. Never touches the source document."""
        require_owner_or_admin(doc, user)
        parties = {p.party_type: p for p in doc.parties}
        new = ESFDocument(owner_id=user.id, status=DocumentStatus.DRAFT)

        new_parties = []
        for ptype in (PartyType.SUPPLIER, PartyType.BUYER):
            src = parties.get(ptype)
            np = ESFParty(party_type=ptype)
            if src is not None:
                for f in self._PARTY_FIELDS:
                    setattr(np, f, getattr(src, f))
            new_parties.append(np)
        new.parties = new_parties

        si = doc.supply_info
        nsi = ESFSupplyInfo()
        nsi.currency_code = (si.currency_code if si else None) or "643"
        if si is not None:
            for f in ("supply_date", "supply_type", "payment_type", "note",
                      "contract_number", "contract_date", "currency_rate"):
                setattr(nsi, f, getattr(si, f))
        new.supply_info = nsi

        new.signature = ESFSignature(director_name=(doc.signature.director_name if doc.signature else None))
        new.items = [
            ESFItem(
                row_number=it.row_number, product_code=it.product_code,
                tnved_code=it.tnved_code, product_name=it.product_name, unit=it.unit,
                price=it.price, quantity=it.quantity, amount=it.amount,
                vat_rate=it.vat_rate, vat_amount=it.vat_amount, nsp=it.nsp,
                total=it.total, customs_refs=it.customs_refs,
            )
            for it in sorted(doc.items, key=lambda x: (x.row_number or 0))
        ]
        new.totals = ESFTotals()
        self._recompute_totals(new)
        return self.repo.add(new)

    # ---- corrections & cancellation (v6.0) ----------------------------
    def cancel(self, doc: ESFDocument, user: User) -> ESFDocument:
        """Annul a PUBLISHED ESF. The immutable snapshot is preserved (history);
        only the document's lifecycle status changes to CANCELLED."""
        require_owner_or_admin(doc, user)
        self._lock(doc)                  # serialize + re-read status under a row lock
        if doc.status != DocumentStatus.PUBLISHED:
            raise HTTPException(status_code=409,
                                detail="Аннулировать можно только опубликованный документ.")
        doc.status = DocumentStatus.CANCELLED
        doc.cancelled_at = datetime.now(timezone.utc)
        self.repo.commit()
        self.repo.refresh(doc)
        return doc

    def create_correction(self, doc: ESFDocument, user: User) -> ESFDocument:
        """Create a new editable DRAFT that corrects a PUBLISHED ESF: a full copy
        linked to the original (`corrects_id`) with field 406 prefilled to the
        original number/date. The original is never modified."""
        require_owner_or_admin(doc, user)
        if doc.status != DocumentStatus.PUBLISHED:
            raise HTTPException(status_code=409,
                                detail="Корректировку можно создать только к опубликованному документу.")
        new = self.duplicate(doc, user)
        new.corrects_id = doc.id
        si = new.supply_info
        si.correction_flag = True
        si.correction_number = doc.esf_number
        si.correction_date = doc.issue_date or (doc.created_at.date() if doc.created_at else None)
        self.repo.commit()
        self.repo.refresh(new)
        return new

    # ---- batch operations (v6.0 #3) -----------------------------------
    def get_if_owner(self, doc_uuid: str, user: User) -> Optional[ESFDocument]:
        """Return the doc if the user may access it, else None (no raise) — for
        batch loops that should silently skip foreign/missing documents."""
        doc = self.repo.get_by_uuid(doc_uuid)
        if doc is None or (doc.owner_id != user.id and not user.is_admin):
            return None
        return doc

    def batch_delete(self, uuids, user: User) -> dict:
        """Delete each selected draft (skips published/cancelled and foreign docs)."""
        deleted = skipped = 0
        for u in uuids:
            doc = self.get_if_owner(u, user)
            if doc is None or not self.is_editable(doc):
                skipped += 1
                continue
            self.repo.delete(doc)
            deleted += 1
        return {"deleted": deleted, "skipped": skipped}

    def batch_publish(self, uuids, user: User) -> dict:
        """Publish each selected editable doc (atomic per document; invalid ones
        are reported as failed and stay DRAFT)."""
        published = skipped = failed = 0
        for u in uuids:
            doc = self.get_if_owner(u, user)
            if doc is None or not self.is_editable(doc):
                skipped += 1
                continue
            try:
                errors = self.publish(doc, user)
                published += 1 if not errors else 0
                failed += 1 if errors else 0
            except Exception:
                # One document failing (lock contention, a race that flips its
                # status, a DB error) must not abort the whole batch — but a
                # silently swallowed error is invisible. Log it with the document
                # uuid and reset the session so the next iteration starts clean.
                self.repo.rollback()
                _log.exception("batch publish failed for document %s",
                               getattr(doc, "uuid", "?"))
                failed += 1
        return {"published": published, "skipped": skipped, "failed": failed}

    # ---- lifecycle helpers --------------------------------------------
    @staticmethod
    def is_editable(doc: ESFDocument) -> bool:
        return doc.status in EDITABLE_STATUSES

    def _require_editable(self, doc: ESFDocument) -> None:
        if not self.is_editable(doc):
            raise HTTPException(
                status_code=409,
                detail="Документ опубликован и не может быть изменён.",
            )

    def _lock(self, doc: ESFDocument) -> None:
        """Row-lock the document (re-reading its status under the lock). A contended
        lock fails fast via lock_timeout as a clean 409 instead of hanging for
        statement_timeout and surfacing an opaque 500."""
        try:
            self.repo.lock(doc)
        except OperationalError:
            self.repo.rollback()
            raise HTTPException(
                status_code=409,
                detail="Документ сейчас изменяется другим процессом. Повторите попытку.",
            )

    # ---- delete --------------------------------------------------------
    def delete(self, doc: ESFDocument, user: User) -> None:
        require_owner_or_admin(doc, user)
        self._lock(doc)                  # serialize + re-read status under a row lock
        # Only editable drafts can be deleted. A PUBLISHED or CANCELLED document
        # has an immutable snapshot (FK RESTRICT); deleting it previously raised
        # an unhandled 500 — reject it cleanly with a 409 instead.
        if not self.is_editable(doc):
            raise HTTPException(
                status_code=409,
                detail="Документ с этим статусом нельзя удалить: "
                       "у опубликованного/аннулированного есть неизменяемый снапшот.",
            )
        self.repo.delete(doc)

    # ---- save ----------------------------------------------------------
    def save(self, doc: ESFDocument, user: User, form) -> ESFDocument:
        require_owner_or_admin(doc, user)
        self._lock(doc)                  # serialize + re-read status under a row lock
        self._require_editable(doc)

        def g(key):
            return (form.get(key) or "").strip()

        # Reject markup early (defence-in-depth for the inline-handler XSS class):
        # ESF numbers are digits + hyphens only. Checked before any mutation so a
        # bad value never leaves partial state behind.
        if g("esf_number") and not _ESF_NUMBER_RE.match(g("esf_number")):
            raise HTTPException(
                status_code=400,
                detail="Недопустимый номер ЭСФ (допустимы только цифры и дефис).",
            )

        parties = {p.party_type: p for p in doc.parties}
        sup = parties.get(PartyType.SUPPLIER) or ESFParty(party_type=PartyType.SUPPLIER)
        buy = parties.get(PartyType.BUYER) or ESFParty(party_type=PartyType.BUYER)
        if sup not in doc.parties:
            doc.parties.append(sup)
        if buy not in doc.parties:
            doc.parties.append(buy)

        for party, pfx in ((sup, "supplier"), (buy, "buyer")):
            party.inn = g(f"{pfx}_inn") or None
            party.name = g(f"{pfx}_name") or None
            party.branch_inn = g(f"{pfx}_branch_inn") or None
            party.branch = g(f"{pfx}_branch") or None
            party.address = g(f"{pfx}_address") or None
            party.tax_office_code = g(f"{pfx}_tax_office_code") or None
            party.tax_office = g(f"{pfx}_tax_office") or None
            party.bank = g(f"{pfx}_bank") or None
            party.account = g(f"{pfx}_account") or None

        si = doc.supply_info or ESFSupplyInfo()
        if doc.supply_info is None:
            doc.supply_info = si
        si.supply_date = _parse_date(g("supply_date"))
        si.supply_type = g("supply_type") or None
        si.payment_type = g("payment_type") or None
        si.note = g("note") or None
        si.contract_number = g("contract_number") or None
        si.contract_date = _parse_date(g("contract_date"))
        si.correction_number = g("correction_number") or None
        si.correction_date = _parse_date(g("correction_date"))
        si.correction_reason = g("correction_reason") or None
        si.currency_code = g("currency_code") or None
        si.currency_rate = _dec(g("currency_rate"))

        sig = doc.signature or ESFSignature()
        if doc.signature is None:
            doc.signature = sig
        sig.director_name = g("director_name") or None

        self._rebuild_items(doc, form)
        self._recompute_totals(doc)

        # Upsert supplier/buyer into the OWNER's counterparty directory (by INN).
        from app.services.counterparty_service import CounterpartyService
        cp_service = CounterpartyService(self.db)
        cp_service.upsert_party(sup, doc.owner_id)
        # Skip the buyer upsert when both sides share an INN: a second pending
        # Counterparty(owner, inn) would collide on uq_counterparties_owner_inn at
        # commit and be misreported as an "ESF number" conflict.
        _sup_inn = (sup.inn or "").strip()
        if not (_sup_inn and (buy.inn or "").strip() == _sup_inn):
            cp_service.upsert_party(buy, doc.owner_id)

        # Remember line items in the owner's goods catalog (by name) — SMART GOODS.
        from app.services.good_service import GoodService
        good_service = GoodService(self.db)
        for it in doc.items:
            good_service.upsert_item(it, doc.owner_id)

        # editing a VALIDATED draft invalidates the prior validation
        if doc.status == DocumentStatus.VALIDATED:
            doc.status = DocumentStatus.DRAFT

        # Header set last (after the item-rebuild flush) so a duplicate esf_number
        # surfaces only at commit and is turned into a clean 409, not a mid-flush 500.
        # (Format was validated at the top of save(), before any mutation.)
        doc.esf_number = g("esf_number") or None
        doc.issue_date = _parse_date(g("issue_date"))

        try:
            self.repo.commit()
        except IntegrityError:
            self.repo.rollback()
            raise HTTPException(
                status_code=409,
                detail="Номер ЭСФ уже используется другим документом.",
            )
        self.repo.refresh(doc)
        return doc

    # ---- validate / publish (lifecycle) -------------------------------
    def validate(self, doc: ESFDocument, user: User) -> List[str]:
        """Run the Validation Engine. On success: status DRAFT -> VALIDATED."""
        require_owner_or_admin(doc, user)
        self._lock(doc)                  # serialize + re-read status under a row lock
        self._require_editable(doc)
        errors = validate_document(doc)
        doc.status = DocumentStatus.DRAFT if errors else DocumentStatus.VALIDATED
        self.repo.commit()
        self.repo.refresh(doc)
        return errors

    def next_esf_number(self) -> str:
        # Official salyk.kg format: 000{YYYY}-004-{8 digits}, e.g. 0002026-004-00000010.
        # The counter is allocated from a DB sequence (atomic + collision-free under
        # concurrency, unlike the old count()+1). The number_exists guard only covers
        # the rare case of a hand-entered number a later sequence value could reach.
        year = datetime.now(timezone.utc).year
        for _ in range(1000):
            n = self.repo.next_number_seq()
            candidate = f"000{year}-004-{n:08d}"
            if not self.repo.number_exists(candidate):
                return candidate
        raise HTTPException(status_code=500, detail="Не удалось выделить номер ЭСФ.")

    def publish(self, doc: ESFDocument, user: User) -> List[str]:
        """DRAFT/VALIDATED -> PUBLISHED via validate -> snapshot.

        Returns validation errors (non-empty = not published).
        """
        require_owner_or_admin(doc, user)
        self._lock(doc)                  # serialize: re-check status under a row lock
        self._require_editable(doc)
        errors = validate_document(doc)
        if errors:
            doc.status = DocumentStatus.DRAFT
            self.repo.commit()
            return errors

        # ----- ATOMIC PUBLICATION ------------------------------------------
        # Number, QR, snapshot, status and published_at are all staged in a
        # SINGLE transaction and committed once. If anything fails we roll the
        # whole thing back, so the document stays DRAFT/VALIDATED and a PUBLISHED
        # document can never exist without its immutable snapshot.
        #
        # Note: status/published_at are set BEFORE building the snapshot because
        # the payload must freeze the *published* document (status "первоначальный
        # (Принят)", published flag, timestamp). The snapshot payload format is
        # therefore unchanged; only the commit boundary moved.
        try:
            if not doc.esf_number:                          # 2. assign ESF number
                doc.esf_number = self.next_esf_number()
            doc.status = DocumentStatus.PUBLISHED           # 5. status (in memory)
            doc.published_at = datetime.now(timezone.utc)   # 6. published_at (in memory)
            self.ensure_qr(doc, commit=False)               # 3. generate QR (no early commit)
            payload = self.serialize(doc)                   # 4. immutable snapshot...
            self.repo.add_pending(snapshot_service.make_snapshot(doc, payload))
            self.repo.commit()                              # 7. commit once
        except IntegrityError:
            # e.g. an esf_number collision that slipped past the guard — surface a
            # clean 409 (retryable) instead of an opaque 500.
            self.repo.rollback()
            raise HTTPException(
                status_code=409,
                detail="Публикация не удалась из-за конфликта номера ЭСФ. Повторите попытку.",
            )
        except Exception:
            self.repo.rollback()                              # no partial publication
            raise
        self.repo.refresh(doc)
        return []

    def _rebuild_items(self, doc: ESFDocument, form) -> None:
        codes = form.getlist("item_tnved")
        names = form.getlist("item_name")
        units = form.getlist("item_unit")
        prices = form.getlist("item_price")
        qtys = form.getlist("item_qty")
        vat_rates = form.getlist("item_vat_rate")
        vat_amounts = form.getlist("item_vat_amount")
        nsps = form.getlist("item_nsp")
        customs = form.getlist("item_customs")
        n = max(len(codes), len(names), len(units), len(prices), len(qtys),
                len(vat_rates), len(vat_amounts), len(nsps), len(customs), 0)

        def at(lst, i):
            return lst[i] if i < len(lst) else ""

        new_items: List[ESFItem] = []
        pos = 0
        for i in range(n):
            code = at(codes, i).strip()
            name = at(names, i).strip()
            price = _bounded(_dec(at(prices, i)), "цена")
            qty = _bounded(_dec(at(qtys, i)), "количество")
            vat_amount = _bounded(_dec(at(vat_amounts, i)), "НДС")
            nsp = _bounded(_dec(at(nsps, i)), "НсП")
            # skip fully-empty rows
            if not any([code, name, price, qty, vat_amount, nsp]):
                continue
            vat_rate = _dec(at(vat_rates, i))
            if vat_rate is not None and abs(vat_rate) > _MAX_RATE:
                raise HTTPException(status_code=400, detail=f"Недопустимая ставка НДС в позиции {pos + 1}.")
            # Guard against a magnitude/precision overflow surfacing as a 500.
            try:
                amount = (price * qty).quantize(TWO) if (price is not None and qty is not None) else None
                total = sum((x for x in (amount, vat_amount, nsp) if x is not None), Decimal("0"))
                total = total.quantize(TWO) if any(x is not None for x in (amount, vat_amount, nsp)) else None
            except InvalidOperation:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недопустимо большое числовое значение в позиции {pos + 1}.",
                )
            amount = _bounded(amount)
            total = _bounded(total)
            pos += 1
            new_items.append(ESFItem(
                row_number=pos,
                tnved_code=code or None,
                product_name=name or None,
                unit=at(units, i).strip() or None,
                price=price,
                quantity=qty,
                amount=amount,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                nsp=nsp,
                total=total,
                customs_refs=at(customs, i).strip() or None,
            ))
        # Remove old rows and flush the DELETEs before inserting the rebuilt rows,
        # otherwise reusing row_number values trips the (document_id, row_number)
        # unique constraint mid-flush.
        doc.items.clear()
        self.repo.flush()
        for it in new_items:
            doc.items.append(it)

    def _recompute_totals(self, doc: ESFDocument) -> None:
        subtotal = sum((it.amount for it in doc.items if it.amount is not None), Decimal("0"))
        vat_total = sum((it.vat_amount for it in doc.items if it.vat_amount is not None), Decimal("0"))
        nsp_total = sum((it.nsp for it in doc.items if it.nsp is not None), Decimal("0"))
        rate = doc.supply_info.currency_rate if doc.supply_info else None
        try:
            grand = (subtotal + vat_total + nsp_total).quantize(TWO)
            currency_total = (grand / rate).quantize(TWO) if rate else None
        except InvalidOperation:
            raise HTTPException(status_code=400, detail="Итоговая сумма недопустимо велика.")

        tot = doc.totals or ESFTotals()
        if doc.totals is None:
            doc.totals = tot
        tot.subtotal = _bounded(subtotal.quantize(TWO))
        tot.vat_total = _bounded(vat_total.quantize(TWO))
        tot.nsp_total = _bounded(nsp_total.quantize(TWO))
        tot.grand_total = _bounded(grand)
        tot.currency_total = _bounded(currency_total)
