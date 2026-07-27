"""ESF Validation Engine.

Pure rules over a loaded ESFDocument. Returns a list of human-readable error
messages (empty list = valid). No DB writes here.
"""
from decimal import Decimal, InvalidOperation
from typing import List

from app.models import ESFDocument, PartyType

_NATIONAL_CURRENCY = "417"          # KGS (som) — the only currency needing no rate
_CENT = Decimal("0.01")
_VAT_TOLERANCE = Decimal("0.02")    # absorb per-line rounding, still catch real errors


def _filled(value) -> bool:
    return value is not None and str(value).strip() != ""


def _to_decimal(value):
    """Parse a rate/amount that may be a Decimal or a string like '12', '12%'."""
    if value is None:
        return None
    s = str(value).strip().replace(",", ".").rstrip("%").strip()
    if s == "":
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def validate_document(doc: ESFDocument) -> List[str]:
    errors: List[str] = []
    parties = {p.party_type: p for p in doc.parties}
    sup = parties.get(PartyType.SUPPLIER)
    buy = parties.get(PartyType.BUYER)

    # Раздел 1 — requisites
    if not sup or not _filled(sup.inn):
        errors.append("Не указан ИНН поставщика (поле 201).")
    elif not str(sup.inn).isdigit():
        errors.append("ИНН поставщика должен содержать только цифры (поле 201).")
    if not sup or not _filled(sup.name):
        errors.append("Не указано наименование поставщика (поле 202).")
    if not buy or not _filled(buy.inn):
        errors.append("Не указан ИНН покупателя (поле 301).")
    elif not str(buy.inn).isdigit():
        errors.append("ИНН покупателя должен содержать только цифры (поле 301).")
    if not buy or not _filled(buy.name):
        errors.append("Не указано наименование покупателя (поле 302).")

    # Раздел 3 — currency
    si = doc.supply_info
    if not si or not _filled(si.currency_code):
        errors.append("Не указан код валюты (Раздел 3).")
    if si and si.currency_rate is not None and si.currency_rate <= 0:
        errors.append("Курс валюты должен быть больше нуля (Раздел 3).")
    # A non-national currency (anything but KGS/417) must carry an exchange rate.
    if (si and _filled(si.currency_code)
            and str(si.currency_code).strip() != _NATIONAL_CURRENCY
            and not _filled(si.currency_rate)):
        errors.append("Для иностранной валюты необходимо указать курс (Раздел 3).")

    # Items
    items = sorted(list(doc.items), key=lambda x: (x.row_number or 0))
    if not items:
        errors.append("Добавьте хотя бы одну товарную позицию (Раздел 3).")
    for idx, it in enumerate(items, start=1):
        if not _filled(it.product_name):
            errors.append(f"Позиция {idx}: не указано наименование товара.")
        if not _filled(it.unit):
            errors.append(f"Позиция {idx}: не указана единица измерения.")
        if it.price is None or it.price <= 0:
            errors.append(f"Позиция {idx}: цена за единицу должна быть больше нуля.")
        if it.quantity is None or it.quantity <= 0:
            errors.append(f"Позиция {idx}: количество должно быть больше нуля.")
        if it.vat_amount is not None and it.vat_amount < 0:
            errors.append(f"Позиция {idx}: сумма НДС не может быть отрицательной.")
        if it.nsp is not None and it.nsp < 0:
            errors.append(f"Позиция {idx}: сумма НсП не может быть отрицательной.")
        # VAT consistency: the entered VAT must match rate × taxable base (amount),
        # within a small rounding tolerance. Only checked when all three are present.
        rate = _to_decimal(it.vat_rate)
        if rate is not None and it.amount is not None and it.vat_amount is not None:
            expected = (it.amount * rate / Decimal(100)).quantize(_CENT)
            if abs(it.vat_amount - expected) > _VAT_TOLERANCE:
                errors.append(
                    f"Позиция {idx}: сумма НДС ({it.vat_amount}) не соответствует ставке "
                    f"{rate}% от суммы {it.amount} (ожидается ≈ {expected})."
                )

    # Signature
    if not doc.signature or not _filled(doc.signature.director_name):
        errors.append("Не указан Ф.И.О. подписанта (поле 450).")

    return errors
