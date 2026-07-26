"""ESF Validation Engine.

Pure rules over a loaded ESFDocument. Returns a list of human-readable error
messages (empty list = valid). No DB writes here.
"""
from typing import List

from app.models import ESFDocument, PartyType


def _filled(value) -> bool:
    return value is not None and str(value).strip() != ""


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
    if not buy or not _filled(buy.name):
        errors.append("Не указано наименование покупателя (поле 302).")

    # Раздел 3 — currency
    si = doc.supply_info
    if not si or not _filled(si.currency_code):
        errors.append("Не указан код валюты (Раздел 3).")
    if si and si.currency_rate is not None and si.currency_rate <= 0:
        errors.append("Курс валюты должен быть больше нуля (Раздел 3).")

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

    # Signature
    if not doc.signature or not _filled(doc.signature.director_name):
        errors.append("Не указан Ф.И.О. подписанта (поле 450).")

    return errors
