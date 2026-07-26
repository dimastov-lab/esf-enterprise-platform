"""DEV-ONLY mock data for the STI-007 ESF visual preview (Sprint 4R).

Values are transcribed from «Копия 6.pdf» so the rendered template can be
compared visually against the official document. This is NOT database data
and is NOT a model — keys loosely mirror the Sprint 3R schema for guidance.
Dates are encoded as ddmmyyyy strings for the boxed-digit renderer.
"""

SAMPLE_ESF = {
    "uuid": "1e2ed777-5b32-11f1-8358-704d7b3139c4",  # exact UUID from the reference QR
    "published": True,
    "qr_url": "/static/img/sample_qr.png",  # encodes the exact reference verification URL
    "appendix": "Приложение 3",
    "sheet_no": 1,
    "status": "первоначальный (Принят)",
    "number": "0002026-004-00962265",
    "issue_date": "29052026",  # 29.05.2026
    "issue_date_disp": "29.05.2026",

    "supplier": {
        "inn": "01610201710254",
        "name": 'Общество с ограниченной ответственностью "Ава Тур"',
        "branch_inn": "",
        "branch_name": "",
        "address": "г. Бишкек, Первомайский рн. ул. Раззакова, 4, 20",
        "tax_office_code": "004",
        "tax_office_name": "УГНС по Первомайскому району",
        "bank": 'Филиал "Центральный" ОАО "Бакай Банк" (124030)',
        "account": "1240020001699526",
    },
    "buyer": {
        "inn": "6686063027",
        "name": 'ООО "ПКФ "Промснабметалл"',
        "branch_inn": "",
        "branch_name": "",
        "address": "620137, РФ, г.Екатеринбург, ул.Аппаратная, д.4, офис 61",
        "tax_office_name": "643 - Российская Федерация",
        "bank": 'ФИЛИАЛ "ЧЕЛЯБИНСКИЙ" АО "ОТП БАНК" (047501830)',
        "account": "40702810408170002241",
    },

    "supply": {
        "date": "24052026",          # 24.05.2026
        "date_disp": "24.05.2026",
        "type": "экспорт",
        "payment": "Безналичная",
        "note": "0000-000560",
        "contract_no": "23/04-26",
        "contract_date": "23042026",  # 23.04.2026
        "contract_date_disp": "23.04.2026",
        "correction_no": "",
        "correction_date": "",
        "correction_reason": "",
    },

    "currency_code": "643",
    "currency_rate": "1.2263",

    "items": [
        {
            "row": 1,
            "code": "7308400009",
            "name": "Строительные леса из черных металлов",
            "unit": "Килограмм",
            "price": "116.49850",
            "qty": "21000.00000",
            "amount": "2446468.50",
            "vat_rate": "0",
            "vat_amount": "0.00",
            "nsp_rate": "0",
            "nsp_amount": "0.00",
            "total": "2446468.50",
            "customs": "",
        },
    ],

    "totals": {
        "sheet_net": "2446468.50", "sheet_vat": "0.00", "sheet_nsp": "0.00", "sheet_total": "2446468.50",
        "inv_net": "2446468.50", "inv_vat": "0.00", "inv_nsp": "0.00", "inv_total": "2446468.50",
        "currency_net": "1995000.00", "currency_total": "1995000.00",
    },

    "signature": {
        "name": "Дуйшекеев Бакыт Карыпбекович",
    },

    "timestamp": "29/05/2026 13.46.33",
}
