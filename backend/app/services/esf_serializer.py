"""Presentation mapping for ESF documents.

Turns the normalized ORM graph (document + parties + supply info + items + totals
+ signature) into the flat, template-ready dict that the STI-007 form, the PDF
render and the immutable snapshot all consume — plus the compact row dict the
dashboard/list uses.

Pure and DB-free: the exact same payload is rendered on screen, printed to PDF and
frozen into the snapshot. Split out of ESFService (audit A-1) so this mapping is a
single, independently testable responsibility with no lifecycle or query concerns.
"""
from app.models import (
    DocumentStatus,
    ESFDocument,
    ESFParty,
    ESFSignature,
    ESFSupplyInfo,
    ESFTotals,
    PartyType,
)

STATUS_LABELS = {
    DocumentStatus.DRAFT: "Черновик (DRAFT)",
    DocumentStatus.VALIDATED: "Проверен (VALIDATED)",
    DocumentStatus.SNAPSHOT_CREATED: "Снапшот (SNAPSHOT_CREATED)",
    DocumentStatus.PUBLISHED: "Опубликован (PUBLISHED)",
    DocumentStatus.CANCELLED: "Отменён (CANCELLED)",
}


def _date_box(d) -> str:
    return d.strftime("%d%m%Y") if d else ""


def _date_disp(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def _money(d) -> str:
    return f"{d:.2f}" if d is not None else ""


def _qty5(d) -> str:
    """Price / quantity exactly as the GNS form prints them — 5 decimal places
    (e.g. 116.49850, 21000.00000), regardless of how they were entered."""
    return f"{d:.5f}" if d is not None else ""


def _rate(d) -> str:
    """Rates (currency rate, VAT rate) without trailing-zero noise: 1.226300 -> 1.2263, 0.00 -> 0."""
    if d is None:
        return ""
    return format(d.normalize(), "f")


class ESFSerializer:
    """Maps an ESFDocument to its template-ready dicts. Stateless."""

    def serialize_row(self, doc: ESFDocument) -> dict:
        """Compact row for the dashboard/list view."""
        parties = {p.party_type: p for p in doc.parties}
        sup = parties.get(PartyType.SUPPLIER)
        buy = parties.get(PartyType.BUYER)
        return {
            "uuid": str(doc.uuid),
            "number": doc.esf_number or "—",
            "date": _date_disp(doc.created_at.date() if doc.created_at else None),
            "supplier": (sup.name if sup and sup.name else "—"),
            "buyer": (buy.name if buy and buy.name else "—"),
            "status": STATUS_LABELS.get(doc.status, doc.status.value),
            "status_code": doc.status.value,
            "published": doc.status == DocumentStatus.PUBLISHED,
            "created_sort": doc.created_at.strftime("%Y%m%d%H%M%S") if doc.created_at else "",
            "updated": doc.updated_at.strftime("%Y-%m-%d %H:%M") if doc.updated_at else "",
        }

    def serialize(self, doc: ESFDocument) -> dict:
        """Full template payload for the STI-007 form / PDF / snapshot."""
        parties = {p.party_type: p for p in doc.parties}
        sup = parties.get(PartyType.SUPPLIER) or ESFParty()
        buy = parties.get(PartyType.BUYER) or ESFParty()
        si = doc.supply_info or ESFSupplyInfo()
        tot = doc.totals or ESFTotals()
        sig = doc.signature or ESFSignature()
        items = sorted(doc.items, key=lambda it: (it.row_number or 0))
        issue = doc.issue_date or (doc.created_at.date() if doc.created_at else None)
        # 101 shows the ESF fiscal status (matches the official form), not the internal lifecycle
        status_101 = "первоначальный (Принят)" if doc.status == DocumentStatus.PUBLISHED else "проект"

        def party_dict(p):
            return {
                "inn": p.inn or "",
                "name": p.name or "",
                "branch_inn": p.branch_inn or "",
                "branch_name": p.branch or "",
                "address": p.address or "",
                "tax_office_code": p.tax_office_code or "",
                "tax_office_name": p.tax_office or "",
                "bank": p.bank or "",
                "account": p.account or "",
            }

        return {
            "uuid": str(doc.uuid),
            "appendix": "Приложение 3",
            "sheet_no": 1,
            "status": status_101,
            "published": doc.status == DocumentStatus.PUBLISHED,
            "qr_url": f"/qr/{doc.uuid}.png",
            "number": doc.esf_number or "",
            "issue_date": _date_box(issue),       # 103 boxes
            "issue_date_disp": _date_disp(issue),  # 103 editable input
            "supplier": party_dict(sup),
            "buyer": party_dict(buy),
            "supply": {
                "date": _date_box(si.supply_date),
                "date_disp": _date_disp(si.supply_date),
                "type": si.supply_type or "",
                "payment": si.payment_type or "",
                "note": si.note or "",
                "contract_no": si.contract_number or "",
                "contract_date": _date_box(si.contract_date),
                "contract_date_disp": _date_disp(si.contract_date),
                "correction_no": si.correction_number or "",
                "correction_date": _date_box(si.correction_date),
                "correction_date_disp": _date_disp(si.correction_date),
                "correction_reason": si.correction_reason or "",
            },
            "currency_code": si.currency_code or "",
            "currency_rate": _rate(si.currency_rate),
            "items": [{
                "row": it.row_number,
                "code": it.tnved_code or "",
                "name": it.product_name or "",
                "unit": it.unit or "",
                "price": _qty5(it.price),
                "qty": _qty5(it.quantity),
                "amount": _money(it.amount),
                "vat_rate": _rate(it.vat_rate),
                "vat_amount": _money(it.vat_amount),
                "nsp_rate": "0",                 # no column (view-only)
                "nsp_amount": _money(it.nsp),
                "total": _money(it.total),
                "customs": it.customs_refs or "",
            } for it in items],
            "totals": {
                "sheet_net": _money(tot.subtotal), "sheet_vat": _money(tot.vat_total),
                "sheet_nsp": _money(tot.nsp_total), "sheet_total": _money(tot.grand_total),
                "inv_net": _money(tot.subtotal), "inv_vat": _money(tot.vat_total),
                "inv_nsp": _money(tot.nsp_total), "inv_total": _money(tot.grand_total),
                "currency_net": _money(tot.currency_total), "currency_total": _money(tot.currency_total),
            },
            "signature": {"name": sig.director_name or ""},
            "timestamp": (doc.published_at or doc.updated_at).strftime("%d/%m/%Y %H.%M.%S")
                         if (doc.published_at or doc.updated_at) else "",
        }
