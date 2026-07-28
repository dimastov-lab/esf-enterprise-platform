# ENTERPRISE_PRODUCTIVITY_REPORT.md

**Project:** ESF Enterprise Platform — Enterprise Productivity Suite
**Target version:** 2.5
**Date:** 2026-06-27
**Baseline:** 1.0.0-rc1 (production-ready)

This program turns a production-ready ESF system into the *fastest and most
comfortable* electronic-invoice editor. Work was done as additive sprints on
top of the existing layered architecture (Controller → Service → Repository →
DB). **No architecture redesign, no STI-007 template duplication, no changes to
Snapshot / Publication / Validation / Security.** The regression suite is green
throughout (**40 passed**, up from 26 at baseline).

Direction confirmed with the product owner before starting:
- Execution: **long autonomous run** (chained sprints, checkpoint at the end).
- AI / OCR: **local-only AI (no external calls); OCR deferred** (keeps the
  project's "no integrations" rule).
- Persistence: **new DB tables + Alembic migrations approved.**

---

## 1. Implemented modules

### Module 31 — Full-width dashboard *(prior sprint)*
Back-office workspace using the entire browser width; sticky top bar; single
professional toolbar (search / status / date range); full-width table with
horizontal overflow. Login / editor / public / PDF untouched.

### Module 32 — Fullscreen editing workspace *(prior sprint)*
Distraction-free editor: sticky toolbar + status bar, collapsible left
navigation and right productivity panel, native fullscreen mode (Esc exits),
document scrolls independently while staying true A4 and centered. `esf_workspace.css`
is loaded **only in edit mode**; view / public / PDF stay byte-identical.

### Module 33 — Editor productivity core *(this program)*
Client-side, no schema, zero regression risk.
- **Live calculations** — per-row `amount = price·qty`, `total = amount+vat+nsp`,
  and the sheet / invoice / currency totals recompute in realtime as you type.
  The backend remains the source of truth (recomputes + persists on save), so the
  numbers never drift from what is stored.
- **Smart item table** — duplicate, copy/paste, insert above / below, delete,
  **Tab in the last cell creates the next row**, automatic numbering, automatic
  totals, **right-click context menu**, multi-select (click the № cell) with
  **mass duplicate / mass delete**, and **drag-and-drop reordering**.
- **Keyboard productivity** — `Ctrl/Cmd+S` save, `Ctrl/Cmd+Enter` publish,
  `Ctrl/Cmd+P` PDF, `Ctrl/Cmd+K` command palette, `Ctrl/Cmd+Z`/`Y` undo/redo,
  Tab / Shift+Tab, Esc, arrow navigation.
- **Command palette (`Ctrl/Cmd+K`)** — fuzzy command list (save, validate,
  publish, PDF, public link, add row, fullscreen, dashboard, new ESF, jump to
  section) plus recent documents.
- **Smart formatting** — INN / account fields digit-only; date fields snap to
  `dd.mm.yyyy`; currency rate normalizes `,`→`.`. All validation-safe.
- **Auto-recovery** — the draft is mirrored to `localStorage`; after a crash the
  editor offers to restore unsaved changes (and scroll position).

### Module 34 — Smart goods catalog + favorites/usage *(this program)*
New `goods` table; `use_count` + `is_favorite` added to `goods` **and**
`counterparties`.
- Line items are remembered on save (upsert by name; usage counter increments).
- **Autocomplete** on the item name field fills code / unit / price / VAT for the
  row; ranked favorites → most-used → recent → name.
- Right-panel **"Recent goods"** list — one click adds a pre-filled item row.
- Counterparty lookup now also ranks by favorites + usage.
- Endpoints (auth-only): `GET /api/goods/search`, `GET /api/goods/recent`
  (alongside the existing `/api/counterparties/{search,recent}`).

### Module 35 — Smart dashboard analytics *(this program)*
Server-computed stats (`ESFService.dashboard_stats`), no schema.
- Stat cards: total / drafts / validated / published / today.
- **Click a stat card to filter** the table by that status.
- Inline **7-day activity bar chart**.
- Dashboard keyboard shortcuts: `n` = new ESF, `/` = focus search, `Esc` = clear.

---

## 2. Performance impact

- **No measured regression.** New per-request work on the dashboard is one extra
  in-memory aggregation over the user's own documents (`dashboard_stats`),
  O(n) over rows already loaded for the list. Editor productivity is 100%
  client-side. Goods/counterparty autocomplete are debounced (300 ms),
  `LIMIT 10`, indexed lookups (`ix_goods_name`, `ix_goods_code`).
- Catalog upserts on save are bounded by the number of line items (small).
- All new CSS/JS ships only in the relevant template; the public page, PDF and
  snapshot path carry **no** extra payload.
- Test-suite wall-clock: ~30 s for 40 tests (was ~27 s for 26).

## 3. Productivity improvements (qualitative)

| Task | Before | After |
|------|--------|-------|
| Add many line items | click "+ строка" each time | **Tab** auto-creates rows; duplicate / mass-duplicate |
| See totals | save → reload | **realtime** as you type |
| Re-enter a known company / good | retype everything | **autocomplete** + recent panels |
| Navigate a long document | scroll hunting | left-nav jump + command palette |
| Recover after a crash | retype | **auto-recovery** prompt |
| Triage the dashboard | read the whole table | stat cards + click-to-filter + chart |
| Common actions | hunt for the button | `Ctrl/Cmd+K` palette + shortcuts |

## 4. Quality / regression status

- **40 / 40 tests pass.** New tests cover: goods search/recent (+auth, +usage
  increment), editor productivity hooks present and **absent in public**,
  live-calc formula parity with backend totals, dashboard stats widgets + counts,
  workspace chrome edit-only.
- Snapshot immutability, publication, validation, RBAC, CSRF, owner isolation —
  unchanged and still covered by their original tests.
- STI-007 document, PDF and public verification remain visually identical
  (the productivity layer is edit-mode-scoped; only inert CSS class names appear
  in shared markup).

## 5. Technical debt introduced / outstanding

- **Undo/redo** is snapshot-based and bails if the row count changed between
  snapshots (safe, but not a true per-edit history). Full version history is a
  future module.
- **Counterparty/goods favorites** are persisted (columns exist) but there is no
  UI toggle yet — ranking already honors them.
- **Drag-and-drop** reorder has no on-screen drop indicator (functional only).
- Live-calc mirrors backend rounding (`round half-up to 2dp`); if backend
  rounding ever changes, the JS must change in lockstep (documented in the
  template).
- `dashboard_stats` loads the user's documents in memory; for very large
  datasets it should become a `GROUP BY` aggregate query.

## 6. Roadmap — remaining suite (proposed sprints to v3.0)

These were scoped but **not yet implemented**; each is a clean, additive sprint:

1. **Validation Center** — progress indicator, errors vs warnings, click-to-navigate
   + highlight, suggestions (build on existing validation engine).
2. **Smart publication** — open the final document directly after publish (skip
   the intermediate result page) with Print / PDF / QR / Copy-link toolbar.
3. **History & versions** — autosave history, version timeline, diff, restore
   (new `document_versions` table; must not violate snapshot immutability).
4. **Attachments** — contracts / invoices / scans with a counter (new
   `attachments` table + file storage decision).
5. **Batch operations** — multi-select on the dashboard → PDF / ZIP / delete /
   export / publish.
6. **Excel import/export** — goods/documents/counterparties via `openpyxl`
   (new dependency) with preview + column mapping + validation.
7. **Split view** — editor left, live preview right, realtime sync.
8. **Global search & timeline** — one box across documents/companies/goods;
   per-document activity timeline (created/edited/validated/published/viewed/QR).
9. **User settings** — autosave interval, theme, language, dashboard layout.
10. **Local AI assistant** — heuristic checks (suspicious totals, missing data,
    anomaly flags, plain-language error explanations); **no external calls**.
11. **OCR import** — deferred pending a provider decision (conflicts with the
    current "no integrations" rule).

## 7. Recommended Version 3.0

Ship v2.5 now (Modules 31–35). For **v3.0**, prioritize the items that compound
the editor's speed: **Validation Center → Smart publication → History/versions →
Batch operations → Excel I/O**, then Split view and Local AI. Treat OCR and any
external AI as a separate, explicitly-approved track because they cross the
project's no-integration boundary.

---

### Files touched this program (Modules 33–35)

- Templates: `app/templates/esf/form.html`, `app/templates/dashboard.html`
- CSS: `app/static/css/esf_workspace.css`
- Models: `app/models/good.py` (new), `app/models/counterparty.py`, `app/models/__init__.py`
- Migration: `alembic/versions/e4b7c1a9f210_add_goods_and_usage_counters.py`
- Repos/services: `good_repository.py`, `good_service.py` (new),
  `counterparty_repository.py`, `services/esf_service.py`
- Routers: `app/routers/api.py`, `app/routers/esf.py`
- Tests: `tests/test_regression.py` (26 → 40)
- Screenshots: `docs/screenshots/{editor_productivity,command_palette,dashboard_analytics,editor_workspace_wide,editor_workspace_laptop}.png`
