# FINAL_VISUAL_REPORT.md

**Sprint:** Final Visual Parity — ESF public viewer vs. official esf.salyk.kg
**Date:** 2026-06-27
**Scope:** viewer only (`view` + `public`). STI-007 document, edit mode, PDF,
snapshot, publication, QR — unchanged. **Regression: 41/41 green.**

---

## Honest note on the reference

This environment cannot reach `https://esf.salyk.kg`, so a live pixel-diff /
overlay against the official server was **not possible**. The comparison below is
against the **official screenshot you provided** plus the explicit spec in the
sprint. Where I could not measure, I say so rather than estimate.

To enable a true pixel overlay, drop the official capture at
`docs/screenshots/official_reference_public.png` and I will diff it against
`docs/screenshots/final_public_after.png`.

---

## Before → After

| | file |
|---|---|
| Before (dark app viewer, page filled width) | `docs/screenshots/public_view_before.png` |
| After (light viewer, centered paper, big margins) | `docs/screenshots/final_public_after.png` |
| After — wide / ultra | `docs/screenshots/final_public_wide.png` |
| Toolbar close-up | `docs/screenshots/final_viewer_toolbar.png` |

---

## Difference table (official screenshot → our viewer)

| Aspect | Official | Before | After (now) |
|--------|----------|--------|-------------|
| Background / canvas | light, near-white | dark gray (#52565a) | **light #f4f5f7** ✔ |
| Toolbar | none / minimal | dark, dominant | **light, minimal, compact** ✔ |
| Document size (roomy screen) | small, centered | filled width | **natural size, capped at 100%** ✔ |
| Margins | large | small | **large (centered both axes)** ✔ |
| Paper effect | sheet + soft shadow | hard shadow on dark | **soft shadow on white** ✔ |
| Centering | yes | yes | **yes (flex + margin:auto)** ✔ |
| Whitespace / spacing | generous | cramped | **generous** ✔ |
| Footer | QR · 450 · name · vertical date | same | **same (unchanged)** ✔ |
| QR alignment | bottom-left in document | same | **same (in grid cell)** ✔ |
| Signature | name in cell, vertical divider | same | **same** ✔ |
| Typography | DejaVu Sans (document) | same | **same (document untouched)** ✔ |
| Default zoom | reads as ~100% w/ margins | maximized | **Fit Page capped at 100%** ✔ |

---

## Viewer behavior (as specified)

- **Default: Fit Page** — whole page visible, **never upscaled past 100%**, so on
  roomy screens it shows the natural-size sheet centered with large margins (the
  official look); shrinks to fit on smaller screens.
- **Presets:** Fit Width · 100% · 125% · 150% · zoom ± (and Ctrl/Cmd +/−/0).
- **Remembers zoom** across visits (`localStorage` `esf_viewer_zoom`).
- Active mode/preset is highlighted; current % is shown.
- Uniform `transform: scale` only → **STI-007 proportions never distorted**.

## Toolbar (as specified)

- **Minimal, light, compact**, ~44px, white with a hairline border.
- **Public:** title + zoom controls only — no internal/owner actions
  (verified: no `/esf/new`, no `/pdf/…`, no “← Назад”).
- **Owner view:** same light bar + light actions (Назад · Печать · PDF · QR ·
  Ссылка · + Новый).

## Canvas (as specified)

- White/near-white canvas, document centered as a paper sheet, **soft shadow**,
  **large margins** on every side, fixed toolbar, independent smooth scroll.

---

## Remaining differences (cosmetic / out of scope)

1. **Live pixel overlay not run** — no network access to the official server
   (see note above). Visual match assessed against your screenshot.
2. **Document NUMBER** of the demo doc shows the old format
   (`2026-004-00000010`) because it was published before the format change and
   its snapshot is immutable; new documents use `000{YYYY}-004-{8}`.
3. **Exact canvas gray and shadow radius** are matched by eye, not sampled from
   the official pixels — trivially tunable once a reference PNG is provided.
4. **Toolbar control labels** are localized (“По странице/По ширине”); the
   official may use icons — easy to swap if desired.

## Definition of Done

- [x] Public viewer reads as the official ESF viewer for a normal user
      (light canvas, centered paper, soft shadow, large margins, minimal light
      toolbar, Fit Page default + presets, remembered zoom).
- [x] STI-007 document, edit mode, PDF, snapshot, publication, QR unchanged.
- [x] Regression tests green (**41/41**); public-page test updated to assert the
      light viewer is present and no editor/owner chrome leaks.
- [x] Screenshots captured (before/after/wide/toolbar).
- [ ] Live pixel overlay vs official — blocked on network access to esf.salyk.kg.
