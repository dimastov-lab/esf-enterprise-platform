"""Unit tests for ESFSerializer — pure, DB-free presentation mapping."""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.models import DocumentStatus, PartyType
from app.services.esf_serializer import (
    ESFSerializer,
    _date_box,
    _date_disp,
    _money,
    _qty5,
    _rate,
)


# ---- private formatting helpers ----------------------------------------

def test_date_box_formats_ddmmyyyy():
    assert _date_box(date(2026, 5, 24)) == "24052026"

def test_date_box_none_returns_empty():
    assert _date_box(None) == ""

def test_date_disp_formats_dots():
    assert _date_disp(date(2026, 5, 24)) == "24.05.2026"

def test_date_disp_none_returns_empty():
    assert _date_disp(None) == ""

def test_money_two_decimal_places():
    assert _money(Decimal("2446470.00")) == "2446470.00"

def test_money_rounds_to_two():
    assert _money(Decimal("1.005")) == "1.00"  # banker's rounding (Decimal)

def test_money_none_returns_empty():
    assert _money(None) == ""

def test_qty5_five_decimal_places():
    assert _qty5(Decimal("116.49850")) == "116.49850"
    assert _qty5(Decimal("21000")) == "21000.00000"

def test_qty5_none_returns_empty():
    assert _qty5(None) == ""

def test_rate_strips_trailing_zeros():
    assert _rate(Decimal("1.226300")) == "1.2263"
    assert _rate(Decimal("0.00")) == "0"

def test_rate_none_returns_empty():
    assert _rate(None) == ""


# ---- helpers -----------------------------------------------------------

def _party(party_type, name="Компания", inn="123"):
    p = MagicMock()
    p.party_type = party_type
    p.name = name
    p.inn = inn
    p.branch_inn = None
    p.branch = None
    p.address = "г. Бишкек"
    p.tax_office_code = "001"
    p.tax_office = "УГНС"
    p.bank = "Бакай"
    p.account = "1234567890"
    return p


def _make_doc(status=DocumentStatus.DRAFT, number="2026-001"):
    doc = MagicMock()
    doc.uuid = "aaaabbbb-1234-5678-abcd-111122223333"
    doc.esf_number = number
    doc.status = status
    dt = datetime(2026, 5, 24, 10, 0, 0, tzinfo=timezone.utc)
    doc.created_at = dt
    doc.updated_at = dt
    doc.published_at = dt if status == DocumentStatus.PUBLISHED else None
    doc.issue_date = date(2026, 5, 24)
    doc.parties = [
        _party(PartyType.SUPPLIER, name="ООО Поставщик", inn="01610201710254"),
        _party(PartyType.BUYER,    name="ООО Покупатель", inn="6686063027"),
    ]

    si = MagicMock()
    si.supply_date = date(2026, 5, 24)
    si.supply_type = "экспорт"
    si.payment_type = "Безналичная"
    si.note = ""
    si.contract_number = "23/04-26"
    si.contract_date = date(2026, 4, 23)
    si.correction_number = None
    si.correction_date = None
    si.correction_reason = None
    si.currency_code = "643"
    si.currency_rate = Decimal("1.2263")
    doc.supply_info = si

    tot = MagicMock()
    tot.subtotal      = Decimal("2446470.00")
    tot.vat_total     = Decimal("0.00")
    tot.nsp_total     = Decimal("0.00")
    tot.grand_total   = Decimal("2446470.00")
    tot.currency_total = Decimal("1994500.00")
    doc.totals = tot

    sig = MagicMock()
    sig.director_name = "Дуйшекеев Б.К."
    doc.signature = sig

    item = MagicMock()
    item.row_number   = 1
    item.tnved_code   = "7308400009"
    item.product_name = "Строительные леса"
    item.unit         = "Килограмм"
    item.price        = Decimal("116.49850")
    item.quantity     = Decimal("21000.00000")
    item.amount       = Decimal("2446470.00")
    item.vat_rate     = Decimal("0")
    item.vat_amount   = Decimal("0.00")
    item.nsp          = Decimal("0.00")
    item.total        = Decimal("2446470.00")
    item.customs_refs = ""
    doc.items = [item]

    return doc


# ---- ESFSerializer.serialize_row ----------------------------------------

def test_serialize_row_returns_uuid_and_number():
    row = ESFSerializer().serialize_row(_make_doc())
    assert row["uuid"] == "aaaabbbb-1234-5678-abcd-111122223333"
    assert row["number"] == "2026-001"

def test_serialize_row_supplier_and_buyer_names():
    row = ESFSerializer().serialize_row(_make_doc())
    assert row["supplier"] == "ООО Поставщик"
    assert row["buyer"] == "ООО Покупатель"

def test_serialize_row_published_false_for_draft():
    row = ESFSerializer().serialize_row(_make_doc(status=DocumentStatus.DRAFT))
    assert row["published"] is False

def test_serialize_row_published_true_for_published():
    row = ESFSerializer().serialize_row(_make_doc(status=DocumentStatus.PUBLISHED))
    assert row["published"] is True

def test_serialize_row_no_number_shows_dash():
    row = ESFSerializer().serialize_row(_make_doc(number=None))
    assert row["number"] == "—"

def test_serialize_row_no_parties_shows_dashes():
    doc = _make_doc()
    doc.parties = []
    row = ESFSerializer().serialize_row(doc)
    assert row["supplier"] == "—"
    assert row["buyer"] == "—"

def test_serialize_row_status_code_matches_enum_value():
    for status in (DocumentStatus.DRAFT, DocumentStatus.PUBLISHED, DocumentStatus.CANCELLED):
        row = ESFSerializer().serialize_row(_make_doc(status=status))
        assert row["status_code"] == status.value


# ---- ESFSerializer.serialize (full payload) -----------------------------

def test_serialize_has_required_keys():
    payload = ESFSerializer().serialize(_make_doc())
    for key in ("uuid", "number", "supplier", "buyer", "supply", "items", "totals", "signature"):
        assert key in payload

def test_serialize_status_101_published():
    payload = ESFSerializer().serialize(_make_doc(status=DocumentStatus.PUBLISHED))
    assert payload["status"] == "первоначальный (Принят)"

def test_serialize_status_101_draft():
    payload = ESFSerializer().serialize(_make_doc(status=DocumentStatus.DRAFT))
    assert payload["status"] == "проект"

def test_serialize_item_qty_formatted_five_decimals():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["items"][0]["qty"] == "21000.00000"
    assert payload["items"][0]["price"] == "116.49850"

def test_serialize_item_total_formatted():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["items"][0]["total"] == "2446470.00"

def test_serialize_totals_grand_total():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["totals"]["sheet_total"] == "2446470.00"
    assert payload["totals"]["inv_total"] == "2446470.00"

def test_serialize_issue_date_boxed():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["issue_date"] == "24052026"

def test_serialize_issue_date_display():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["issue_date_disp"] == "24.05.2026"

def test_serialize_currency_rate_stripped():
    payload = ESFSerializer().serialize(_make_doc())
    assert payload["currency_rate"] == "1.2263"

def test_serialize_items_sorted_by_row_number():
    doc = _make_doc()
    item2 = MagicMock()
    item2.row_number   = 2
    item2.tnved_code   = "0"
    item2.product_name = "Второй"
    item2.unit         = "шт"
    item2.price        = Decimal("1.00000")
    item2.quantity     = Decimal("1.00000")
    item2.amount       = Decimal("1.00")
    item2.vat_rate     = Decimal("0")
    item2.vat_amount   = Decimal("0.00")
    item2.nsp          = Decimal("0.00")
    item2.total        = Decimal("1.00")
    item2.customs_refs = ""
    # Insert in reverse order to test sorting
    doc.items = [item2, doc.items[0]]
    payload = ESFSerializer().serialize(doc)
    assert payload["items"][0]["row"] == 1
    assert payload["items"][1]["row"] == 2

def test_serialize_no_supply_info_returns_empty_strings():
    doc = _make_doc()
    doc.supply_info = None
    payload = ESFSerializer().serialize(doc)
    assert payload["supply"]["type"] == ""
    assert payload["supply"]["payment"] == ""
