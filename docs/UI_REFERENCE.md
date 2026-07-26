# UI_REFERENCE.md — Visual Source of Truth

> Reverse-engineered from `Копия 6.pdf`.
> This document, together with the PDF, is the **authoritative layout specification**.
> The HTML interface (editor / view / public / PDF) MUST reproduce this layout.
> The PDF must **not** be used as a background image or rasterized — it is rebuilt in HTML + CSS.

---

## 0. What the document actually is

This is **not** a generic "submission form". It is the official Kyrgyz Republic
**electronic VAT invoice**:

- Header marking: **BLANK STI - 007**
- Country: **Кыргызская Республика** (Kyrgyz Republic)
- Title: **СЧЕТ-ФАКТУРА в виде электронного документа на товары**
  (Invoice in the form of an electronic document for goods)
- Form classification: **Приложение 3** (Appendix 3)
- Language: **Russian** (field labels are fixed Russian text; data may be RU/KG)

Every field carries a **numeric code** (101, 102, 201…450). These codes are part of the
official form and MUST be rendered exactly — they are how the tax authority and integrations
reference fields.

---

## 1. Page geometry

| Property | Value |
|---|---|
| Orientation | **Landscape** |
| Paper | **A4 landscape** (297 mm × 210 mm) |
| Aspect ratio | ≈ 1.41 : 1 (wider than tall) |
| Margins | Narrow (~8–10 mm); the table grid nearly reaches page edges |
| Color | **Monochrome** — black text/borders on white |
| Borders | Thin hairline rules (~0.5–1 px), full grid (every field is boxed) |
| Multi-page | Header says **«НОМЕР ТЕКУЩЕГО ЛИСТА: 1»** (current sheet number) → form is paginated; "Итого по листу" = per-sheet subtotal |

**Layout model:** a dense, fully-ruled government form. Almost every label and value sits
inside its own bordered cell. Use CSS table / grid with `border-collapse: collapse` and
hairline borders. Fixed widths, not fluid.

---

## 2. Typography

| Element | Style |
|---|---|
| Base font | Narrow sans-serif (Arial Narrow / condensed sans). Use `Arial, "Liberation Sans", sans-serif` with condensed letter-spacing |
| Field-code numbers (101, 201…) | ~6–7 pt, top-left inside each cell, in a tiny bordered box |
| Field labels | ~6–7 pt, regular |
| Field values | ~7–9 pt, regular/medium |
| Section titles («Раздел 1…») | ~9–10 pt, centered, slightly bold |
| Document title (СЧЕТ-ФАКТУРА) | ~11–12 pt, centered, bold |
| Boxed digits (INN, dates) | Monospace-style, one digit per cell |

Everything is small and tight. Whitespace is minimal; information density is high.

---

## 3. Top header band

Three zones across the top:

```
┌────────────────────────────┬─────────────────────────────────┬──────────────────────────┐
│ BLANK STI - 007            │          СЧЕТ-ФАКТУРА           │           Приложение 3   │
│ Кыргызская Республика      │ в виде электронного документа   │ НОМЕР ТЕКУЩЕГО ЛИСТА: 1   │
│                            │           на товары             │                          │
└────────────────────────────┴─────────────────────────────────┴──────────────────────────┘
```

Below it, a row of boxed status fields:

| Code | Label | Example value | Render |
|---|---|---|---|
| **101** | СТАТУС | `первоначальный (Принят)` | text in box |
| **102** | НОМЕР | `0002026-004-00962265` | text in box |
| **103** | Дата оформления | `29 05 2026` | **boxed digits**: `день / месяц / год` |

The 103 date (and all dates) render as **separate single-digit cells** grouped under
`день` / `месяц` / `год` captions.

---

## 4. Раздел 1 — «Реквизиты поставщика и покупателя» (Supplier & Buyer requisites)

Two equal columns. **Left = Поставщик (Supplier, codes 201–208)**, **Right = Покупатель (Buyer, codes 301–308)**. Same row structure on both sides.

### Left column — Supplier (example data from PDF)

| Code | Label | Value |
|---|---|---|
| 201 | Поставщик ИНН | `01610201710254` (14 boxed digits) |
| 202 | Ф.И.О. ИП / Наименование организации | Общество с ограниченной ответственностью "Ава Тур" |
| 203 | Филиал поставщика ИНН | *(empty)* |
| 204 | Наименование филиала | *(empty)* |
| 205 | Адрес (юридич. и/или фактич.) | г. Бишкек, Первомайский рн. ул. Раззакова, 4, 20 |
| 206 | Код и наименование налогового органа | `004` УГНС по Первомайскому району |
| 207 | Наименование банка и код (БИК) | Филиал "Центральный" ОАО "Бакай Банк" (124030) |
| 208 | Счет в банке | 1240020001699526 |

### Right column — Buyer (example data from PDF)

| Code | Label | Value |
|---|---|---|
| 301 | Покупатель ИНН | `6686063027` (boxed digits) |
| 302 | Ф.И.О. ИП / Наименование организации | ООО "ПКФ "Промснабметалл" |
| 303 | Филиал покупателя ИНН | *(empty)* |
| 304 | Наименование филиала | *(empty)* |
| 305 | Адрес (юридич. и/или фактич.) | 620137, РФ, г.Екатеринбург, ул.Аппаратная, д.4, офис 61 |
| 306 | Код и наименование налогового органа / страны | `643 - Российская Федерация` |
| 307 | Наименование банка и код (БИК) | ФИЛИАЛ "ЧЕЛЯБИНСКИЙ" АО "ОТП БАНК" (047501830) |
| 308 | Счет в банке | 40702810408170002241 |

> Note: a foreign (RF) buyer has a country code (643) instead of a local tax-authority code.
> The buyer's INN box has a different length than the supplier's — the layout tolerates both.

---

## 5. Раздел 2 — «Информация о реализации» (Sale information)

A horizontal band of boxed fields:

| Code | Label | Example value |
|---|---|---|
| 401 | Дата поставки | `24 05 2026` (boxed день/месяц/год) |
| 402 | Вид поставки | экспорт |
| 403 | Форма оплаты | Безналичная |
| 404 | Примечание | 0000-000560 |
| 405 | Договор (контракт) на реализацию (поставку) работ и услуг | №: `23/04-26`, дата `23 04 2026` |
| 406 | Корректировка к счету-фактуре | №: *(empty)*, дата *(empty)* |
| 407 | Причина корректировки | *(empty)* |

Codes 405/406 each contain a sub-`№` and a boxed-digit date.

---

## 6. Раздел 3 — «Информация о товаре» (Goods information)

### 6.1 Currency strip (above the table)

| Field | Value |
|---|---|
| Код валюты | `643` |
| Курс валюты | `1.2263` |
| ☐ Товар, подлежащий прослеживаемости | checkbox (traceable goods) — empty here |

### 6.2 Line-items table

Column order, left → right (note the **grouped header**: НДС and НсП each span two sub-columns):

```
┌────┬──────────┬─────────────────┬──────────┬──────────┬────────────┬──────────────┬───────────────┬───────────────┬──────────────┬────────────────────────┐
│ №  │  Код     │  Наименование   │ Единица  │  Цена за │ Количество │ Стоимость    │      НДС       │      НсП      │   Общая      │  Реквизиты таможенной   │
│п/п │ товара   │     товара      │измерения │ единицу  │  (объем)   │ товара без   ├───────┬───────┼───────┬───────┤  стоимость   │  декларации или ЭСФ     │
│    │          │                 │          │          │            │ НДС и НсП    │Ставка │ Сумма │Ставка │ Сумма │   товара     │                        │
├────┼──────────┼─────────────────┼──────────┼──────────┼────────────┼──────────────┼───────┼───────┼───────┼───────┼──────────────┼────────────────────────┤
│ 1  │7308400009│Строительные леса│Килограмм │116.49850 │21000.00000 │ 2446468.50   │  0    │ 0.00  │  0    │ 0.00  │ 2446468.50   │                        │
│    │          │из черных металлов│         │          │            │              │       │       │       │       │              │                        │
└────┴──────────┴─────────────────┴──────────┴──────────┴────────────┴──────────────┴───────┴───────┴───────┴───────┴──────────────┴────────────────────────┘
```

Column reference:

| # | Header | Notes / alignment |
|---|---|---|
| 1 | № п/п | row number, center |
| 2 | Код товара | ТН ВЭД commodity code (e.g. `7308400009`), center |
| 3 | Наименование товара | goods name, left, wraps |
| 4 | Единица измерения | unit of measure (Килограмм), center |
| 5 | Цена за единицу | unit price, 5 decimals, right |
| 6 | Количество (объем) | quantity, 5 decimals, right |
| 7 | Стоимость товара без НДС и НсП | net amount, 2 decimals, right |
| 8 | НДС → Ставка | VAT rate, center |
| 9 | НДС → Сумма | VAT amount, right |
| 10 | НсП → Ставка | Sales-tax rate, center |
| 11 | НсП → Сумма | Sales-tax amount, right |
| 12 | Общая стоимость товара | line total, right |
| 13 | Реквизиты таможенной декларации или ЭСФ | customs declaration / ESF refs, left |

### 6.3 Totals rows (under the table)

| Row label | Net | НДС.Ставка | НДС.Сумма | НсП.Ставка | НсП.Сумма | Общая | Customs |
|---|---|---|---|---|---|---|---|
| **Итого по листу** (per sheet) | 2446468.50 | X | 0.00 | X | 0.00 | 2446468.50 | X |
| **Итого по счету-фактуре** (whole invoice) | 2446468.50 | X | 0.00 | X | 0.00 | 2446468.50 | X |
| **Итого в иностранной валюте** (in foreign currency) | 1995000.00 | | | | | 1995000.00 | |

- `X` is a literal printed placeholder in rate/customs cells where a sum is not meaningful.
- Foreign-currency total = local total ÷ exchange rate (2446468.50 ÷ 1.2263 ≈ 1995000.00).

---

## 7. Footer / signature block

Bottom band, three zones left → right:

```
┌──────────┬───────────────────────────────────────────────────────┬──────────────────┐
│  ▓▓ QR ▓▓ │ 450  Ф.И.О. руководителя организации или индивид-      │  Дуйшекеев Бакыт │
│  ▓▓▓▓▓▓▓ │      уального предпринимателя или бухгалтера или       │  Карыпбекович    │
│  ▓▓▓▓▓▓▓ │      налогового представителя                          │                  │
└──────────┴───────────────────────────────────────────────────────┴──────────────────┘
                                                          (rotated, far right): 29/05/2026 13:46:33
```

| Element | Position | Notes |
|---|---|---|
| **QR code** | **bottom-left corner** | ~2 cm square; encodes the public verification URL |
| **450** signatory label | center | fixed Russian text (руководитель / бухгалтер / налоговый представитель) |
| Signatory name | right of label | Дуйшекеев Бакыт Карыпбекович |
| Print timestamp | far right, **rotated 90°** | `29/05/2026 13:46:33` — generation datetime |

---

## 8. Implementation notes for the HTML template

1. **One template, four uses.** The same markup renders for *edit*, *internal view*,
   *public verification*, and *PDF*. Only interactivity changes (inputs vs. static text)
   and the chrome (nav/actions hidden on public + PDF).
2. **Field codes are content, not decoration.** Render the tiny numbered boxes (101, 201…)
   exactly; downstream tax integration relies on them.
3. **Boxed digits.** INN and dates render as one-character cells. A reusable
   "digit-box" component (N cells) handles 201/301/103/401/405.
4. **Grouped table headers.** НДС and НсП are colspan-2 headers over Ставка/Сумма — use
   a two-row `<thead>`.
5. **Numeric formatting.** Prices/quantities show 5 decimals; money 2 decimals; literal `X`
   in non-applicable rate/customs cells.
6. **Print CSS.** `@page { size: A4 landscape; margin: 8mm; }`, hairline borders via
   `border: 0.5px solid #000`, condensed font. Target an HTML→PDF engine that honors page
   CSS (WeasyPrint or a headless-Chromium renderer) rather than ReportLab hand-layout, so
   the same template produces both screen and PDF.
7. **Monochrome.** No colors, gradients, rounded corners, or shadows on the document itself.
   (App chrome around it may be styled; the *document* stays black-on-white.)
8. **Pagination.** Support multiple sheets with "Итого по листу" per sheet and a final
   "Итого по счету-фактуре" — header shows current sheet number (НОМЕР ТЕКУЩЕГО ЛИСТА).

---

## 9. Field dictionary (codes seen in this sample)

| Code | Meaning |
|---|---|
| 101 | Status |
| 102 | Invoice number |
| 103 | Issue date |
| 201–208 | Supplier: INN, name, branch INN, branch name, address, tax-authority code+name, bank+BIK, account |
| 301–308 | Buyer: same structure (306 = tax authority **or country code** for foreign buyers) |
| 401 | Delivery date |
| 402 | Delivery type (export/domestic) |
| 403 | Payment form |
| 404 | Note |
| 405 | Sales contract № + date |
| 406 | Correction reference № + date |
| 407 | Correction reason |
| (strip) | Currency code, exchange rate, traceable-goods flag |
| (table) | Line items: №, commodity code, name, unit, price, qty, net, VAT rate/sum, sales-tax rate/sum, total, customs refs |
| Итого | Subtotals: per sheet, per invoice, in foreign currency |
| 450 | Signatory (head / accountant / tax representative) name |

---

## 10. Implementation status (Sprint 4R)

The layout above is implemented as a single reusable template rendered in original HTML/CSS
(no rasterized PDF, no background image):

- Template: `backend/app/templates/esf/form.html` (modes `edit` / `view` / `public`)
- Stylesheet: `backend/app/static/css/esf_form.css`
- Dev preview: `GET /dev/esf-preview?mode=view` (dev-only; not mounted in production)
- Reference screenshots: `docs/screenshots/esf_preview.png` (early pass),
  `docs/screenshots/esf_preview_v2.png` (current — hairline borders, free header above grid)

**Conventions adopted to match the form:**
- Field-code chips (101, 201, …) are small boxes anchored to each cell's top-left corner.
- Boxed digits use fixed-count cells: 14 for INN (filled left, remainder blank), 2/2/4 for
  dates — empty fields still show their cells.
- The goods table uses `table-layout: fixed` + a `colgroup` so column proportions stay pinned.
- Borders are a 0.5px hairline; the bordered region starts at the 101/102/103 row and the
  title header floats above it (no full-page outer box), as in the official form.

**Known residual deltas (cosmetic, tracked as TD-005):** condensed-font substitution (Arial
Narrow vs the form's exact face); 0.5px hairlines render crisply at 2× / print but may vary on
1× displays; QR is a labeled placeholder until Sprint 7.
