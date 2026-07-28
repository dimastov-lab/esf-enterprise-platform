# COMPLIANCE_ITERATION_01.md — Official ESF parity

**Mode:** Official ESF parity. **Reference available:** `Копия 6.pdf` (a real
published ЭСФ) + user-provided salyk.kg screenshots.

## ⚠️ Honesty constraint (read first)
This environment **cannot reach the live `esf.salyk.kg` system**. I therefore
**cannot** do true pixel/behavioral diffing against it, cannot honestly certify
"≥99% match", and will **not** print "OFFICIAL ESF PARITY ACHIEVED" — that claim
requires a live comparison I can't perform. Scores below are **against the
reference PDF/screenshots only**, and I will not forge provenance markers (QR
target, PDF `Producer`, government ЭЦП) to fake indistinguishability — that would
be counterfeiting an official fiscal document.

---

## This iteration

### 1. Ctrl+S = silent background save (Comfort / behavioral parity)
Was: Ctrl+S → form submit → 303 redirect → full reload, scroll jumped to top,
focus lost. Now: Ctrl+S (and the menu "Сохранить") persist via the autosave
endpoint in the background — **no reload, scroll & focus preserved**. The save
indicator shows "Сохранение… → Сохранено HH:MM".
- Verified in a real browser: Ctrl+S issues `POST …/autosave`, page does **not**
  navigate (`fetch=true, method=POST, navigated=false`).
- Pure client JS; publication/snapshot semantics unchanged.

### 2. Field compliance audit (functional parity)
New test `test_all_sti007_fields_round_trip` fills **all 35 STI-007 fields** with
unique markers and asserts each survives **save → immutable snapshot → public
page → PDF**:
- Supplier 201–208 (ИНН, наименование, филиал ИНН/наименование, адрес, код+орган,
  банк/БИК, счёт).
- Buyer 301–308 (same, 306 = country/orган name only — matches official).
- 101–103 (status, number, дата оформления), 401–407 (дата поставки, вид, оплата,
  примечание, договор №+дата, корректировка, причина), Раздел 3 (валюта, курс,
  позиция: ТН ВЭД, наименование, ед., цена, кол-во, ставка НДС, НсП, таможенные
  реквизиты), 450 подписант.
- **Result: PASS — every field is stored, snapshotted, rendered on the public
  page, and present in the PDF. No dropped fields.**

---

## Compliance scores (vs the reference PDF/screenshots — NOT the live system)

| Area | Score | Basis |
|------|------:|-------|
| Document fields (form structure) | **100%** | all 35 fields round-trip (tested); labels/codes matched line-by-line earlier |
| Value formatting | **100%** | number `000{YYYY}-004-{8}`, price/qty 5-dec, dotted timestamp, ставка `0` — all matched |
| Visual layout (form) | **~98%** | matched against the provided image; QR/headers/totals/footer aligned |
| Behavioral (create/edit/save/publish/correct/cancel) | **~95%** | core workflows present; **multi-sheet not implemented** (see gaps) |
| Provenance (QR target, PDF Producer, ЭЦП) | **intentionally divergent** | honest self-identification, not forged |

> These are reference-bounded estimates, not live-measured.

---

## Remaining gaps (ranked)

1. **Multi-page / multi-sheet documents** (High, functional) — official STI-007
   splits long item lists across sheets: repeated header, continuous «НОМЕР
   ТЕКУЩЕГО ЛИСТА», totals/signature/QR only on the final sheet. Ours uses a single
   sheet (`sheet_no=1`). This is the top real functional difference and the next
   iteration's candidate. *(Additive to rendering; will not change snapshot
   semantics — the snapshot stays one payload, pagination is a render concern.)*
2. **Live pixel/behavior diff** (Blocked) — needs network access to esf.salyk.kg.
3. **Provenance markers** (Won't fix) — would require forging a government
   document; out of scope on principle.
4. **Cosmetic micro-deltas** (Low) — exact line weights, font hinting between
   browser HTML and the genuine Jasper/OpenPDF output; not meaningfully closable
   without the live artifact.

## Regression
Full suite green (Ctrl+S change is client-only; new field-compliance test added).

## Next iteration (planned)
Implement **multi-sheet rendering** for long item lists (header repeat, continuous
sheet numbering, totals/signature/QR on the final sheet only) — the highest-value
remaining fidelity gap I can build and verify locally.
