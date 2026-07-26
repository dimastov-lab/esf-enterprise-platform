# STEP 0 — Project Discovery & Architecture Review

> No code. Analysis only. Companion to [`UI_REFERENCE.md`](UI_REFERENCE.md).
> Sources of truth: Technical Specification (CLAUDE.md + roadmap docs), `Копия 6.pdf`,
> existing repository under `backend/`.

---

## ⚠️ Headline finding (read first)

**The implementation targets the wrong document.**

The PDF is the **Kyrgyz Republic electronic VAT invoice** (Счёт-фактура / ЭСФ — supplier &
buyer requisites, line items with ТН ВЭД codes, НДС/НсП taxes, currency & exchange rate,
totals, signatory). The current code models a generic *"Electronic Submission Form"* with four
fields: `title`, `applicant_name`, `applicant_id`, `description`.

These are **incompatible domains**. The existing `Document` table, templates, and PDF
generator cannot represent a single line item, a tax, a supplier/buyer pair, or a currency.
Roughly the entire data layer, template layer, and PDF generator must be **redesigned**, not
extended. This single fact dominates every score below.

The documentation also disagrees with the code (see §4.1): `PROJECT_STATE.md` claims "Sprint 2
complete," but the repo already contains partial Sprints 3–11 (models, repos, services,
routers, auth, templates, PDF/QR). The project was built ahead of its own roadmap and the
trackers were never updated.

---

## 🔒 Locked decisions (owner-approved)

Confirmed by the project owner during Step 0; these constrain all later sprints:

- **D1 — Single document type.** Build exactly one form: the goods invoice
  **«СЧЁТ-ФАКТУРА в виде электронного документа на товары»** per `Копия 6.pdf`. Services
  («…на работы и услуги») and other ESF types are **out of scope** for now. The schema/UI
  target goods only.
- **D2 — Normalized-first storage.** The ESF is stored primarily in **normalized tables**:
  `parties / document header (invoice) / items / totals / snapshots`. A `json_data` column may
  additionally hold the full raw payload, **but the normalized fields and items are the source
  of truth** for rendering the form — not the JSON. (The immutable `snapshots.payload` JSON is
  separate: it is the frozen legal copy taken at publish, see Phase 6.)

---

## Phase 1 — Business Understanding

**What the system is.** A platform for issuing, storing, and publicly verifying **Kyrgyz
electronic VAT invoices (ЭСФ)**. Each invoice is created as a draft, validated, frozen into an
immutable snapshot, rendered to PDF with a QR code, and exposed on a public verification page
that anyone can reach by scanning the QR.

**Who uses it.**
- **Issuer / accountant (supplier side)** — authenticated user who creates and edits invoice
  drafts, validates, and publishes them.
- **Administrator** — manages users, roles, and oversight; sees the audit log.
- **Public verifier (buyer, customs officer, counterparty, auditor)** — unauthenticated; scans
  the QR or opens the public link to confirm an invoice is authentic and view its details.
- **(Future) Tax authority / external systems** — consume the structured invoice via the field
  codes (101…450) for integration.

**Complete user journey.**
1. User logs in.
2. Dashboard lists their invoices with status (Draft / Validated / Snapshot / Published).
3. User opens the editor (the HTML reproduction of the PDF) and fills supplier, buyer,
   sale info, and line items; totals compute automatically.
4. User saves a **draft** (editable).
5. User runs **validation** (INN format, required fields, totals consistency, currency).
6. On success the system creates an **immutable snapshot** — the legal source of truth.
7. The system generates a **PDF from the snapshot** and a **QR** pointing at the public URL,
   and marks the invoice **Published**.
8. A counterparty scans the QR → opens the **public verification page** → sees the invoice is
   authentic plus its key details.
9. Every critical action (create, validate, publish, view) is written to the **audit log**.

**Expected result for the user.** A legally-shaped, tamper-evident electronic VAT invoice that
looks exactly like the official form, can be downloaded as PDF, and can be independently
verified by anyone via QR — without giving them edit access.

---

## Phase 2 — Functional Analysis (complete checklist)

Grouped by subsystem. ☐ = not yet / inadequate, ◐ = partial, ☑ = present.

### Authentication
- ◐ Username/password login (session cookie) — present, but secret key hardcoded, single seeded admin.
- ☐ Logout invalidation / session expiry / CSRF tokens.
- ☐ Password policy, lockout, rate limiting.

### Dashboard
- ◐ List invoices with status & created date — present, but lists **all** documents (no ownership scoping).
- ☐ Filter/search, pagination, per-user scoping.

### ESF Editor
- ☐ Supplier requisites (201–208) — **missing from model**.
- ☐ Buyer requisites (301–308) — **missing**.
- ☐ Sale info (401–407) — **missing**.
- ☐ Currency code + exchange rate, traceable-goods flag — **missing**.
- ☐ Line-item grid (commodity code, unit, price, qty, НДС, НсП, totals) — **missing**.
- ☐ Auto-computed subtotals / invoice totals / foreign-currency total — **missing**.
- ☐ HTML reproduction of the PDF layout — **missing** (templates show a generic form).
- ☐ Field codes (101…450) rendered — **missing**.

### Generation
- ◐ "Generate" action — present, but flips Draft→Published directly; no Validated / Snapshot states.
- ☐ Validation gate before generation.
- ☐ Snapshot creation (see Snapshot below).

### PDF
- ◐ PDF produced — present (ReportLab), but renders the generic form, **not** the ESF layout, in A4 portrait. Must be rebuilt from the HTML template in **A4 landscape**.

### QR
- ☑ QR generated and saved — present; encodes `/public/{document_number}`.
- ☐ QR should encode an **unguessable** token, not the sequential number (see Security).

### Public Verification
- ◐ Public read-only page — present, but generic; keyed by **sequential** `ESF-00001` (enumerable).
- ☐ Page must reproduce the ESF layout and read from the **snapshot**, not the live row.

### Administration
- ☐ User management (create/disable users).
- ☐ Role management (RBAC) — only a default `is_admin=True` flag exists.
- ☐ Audit-log viewer.

### Database
- ◐ SQLAlchemy models exist — but wrong domain, and split across two `Base` classes / two engines (see §4.1).
- ◐ Alembic configured — but the one migration is stale/auto-generated and disagrees with the models.
- ☐ ESF schema (supplier, buyer, invoice, line items, taxes, snapshot, user, role, audit).

### Security
- ☐ Ownership enforcement.
- ☐ UUID / opaque public identifiers.
- ☐ CSRF protection.
- ◐ Password hashing (bcrypt via passlib) — present.
- ☐ Immutability enforcement after publish.
- ☐ Secret/config management (no hardcoded secrets).

### Future Features
- ☐ Tax-authority integration (submit ESF via field codes).
- ☐ Invoice correction workflow (codes 406/407).
- ☐ Multi-sheet invoices (per-sheet subtotals).
- ☐ Localization (RU/KG/EN), multi-currency.
- ☐ Digital signature / cryptographic seal of the snapshot.

---

## Phase 4 — Architecture Review (contradictions, ambiguities, gaps)

### 4.1 Code-vs-code contradictions (concrete bugs / inconsistencies in the repo)

| # | Issue | Why it's a problem | Recommended fix |
|---|---|---|---|
| C1 | **Two `Base` classes** — `app/database.py:Base` (used by `Snapshot`) and `app/db/base.py:Base` (used by `Document`, `User`). | They produce **separate metadata registries**. `init_db()` calls `create_all()` on the `db/base` Base only → the `snapshots` table is never created at runtime. | One canonical `Base`. Delete the duplicate; all models import the same one. |
| C2 | **Two database engines** — `app/database.py` → PostgreSQL; `app/db/session.py` → **SQLite** (`esf.db`). App routers + `init_db` use the SQLite session; Alembic + `Snapshot` use Postgres. | The app actually runs on SQLite while Docker/Alembic/Compose target Postgres. FK `ondelete=RESTRICT` is silently unenforced on SQLite. Dev ≠ prod. | Single engine from `DATABASE_URL`. Use Postgres everywhere; drop the SQLite session. |
| C3 | **Lifecycle mismatch.** CLAUDE.md defines `DRAFT → VALIDATED → SNAPSHOT_CREATED → PUBLISHED`. `DocumentStatus` enum has only `DRAFT, PUBLISHED`. The migration enum has all four. | The required validation/snapshot states don't exist in code; "generate" shortcuts straight to PUBLISHED. | Implement the full 4-state lifecycle as the spec mandates. |
| C4 | **Snapshot never created.** A `Snapshot` model exists, but no service writes one. `generate()` mutates the live `Document` and builds the PDF from it. | Violates the core immutability requirement ("Snapshot becomes source of truth", "PDF must be generated from Snapshot"). | Snapshot on publish; render PDF/QR/public page from the snapshot payload. |
| C5 | **Stale migration.** The Alembic revision creates `documents(title, content, status…)` — but the model has no `content` and many other columns. | `alembic upgrade` produces a schema that doesn't match the ORM. | Regenerate migrations from the redesigned models. |
| C6 | **CWD-relative mounts.** `main.py` mounts `static/` and `storage/qr` by relative path; `StaticFiles(directory="static")` requires the dir to exist and the process to run from `backend/`. | Crashes or 500s depending on launch directory. `static/css` is empty. | Resolve paths from a settings/base-dir; create dirs at startup. |
| C7 | **Hardcoded secret** in `add_middleware(SessionMiddleware, secret_key="esf-secret-key-change-in-production")`. | Session forgery; secret in VCS. | Load from env/secret store; fail closed if unset in prod. |
| C8 | **Seeded admin/admin123** in `init_db`. | Default credentials in production. | Seed only in dev; force password change / env-provided bootstrap. |
| C9 | `User.is_admin` defaults to **True**. | Every new user is an admin. | Default False; explicit role assignment. |
| C10 | **Docs out of sync.** `PROJECT_STATE.md` = "Sprint 2 complete," but Sprints 3–11 are partially built. | The roadmap can't be trusted as ground truth. | Reset trackers to reflect reality after this review. |

### 4.2 Specification-level issues

| Issue | Type | Explanation | Proposed solution |
|---|---|---|---|
| "ESF" is undefined in the spec | Ambiguity | CLAUDE.md says "ESF document" generically; the PDF reveals it's a **Kyrgyz VAT invoice** with a fixed legal structure. The generic interpretation produced the wrong app. | Adopt the PDF as the canonical ESF definition. Model supplier/buyer/invoice/line-items/taxes. |
| Validation rules unspecified | Gap | Spec says "Validation Engine" but lists no rules. | Derive rules from the form: INN length/checksum, required requisites, ≥1 line item, totals = Σ(lines), currency+rate present for foreign sales, VAT/sales-tax math. |
| Immutability mechanism unspecified | Gap | "Snapshot becomes source of truth" — but not *how* it's frozen or proven. | JSON snapshot + content hash stored on the snapshot; optional signature. Public page shows hash. |
| Public link format unspecified | Ambiguity | Spec says "QR must point to public check URL" but not the identifier. Code uses the sequential number. | Opaque UUID/token per published invoice (see Security). |
| Roles unspecified | Gap | "users and roles" but no role list. | Define roles: `ADMIN`, `ISSUER`, (public is anonymous). Extend later. |
| Multi-sheet & corrections | Hidden requirement | PDF implies pagination ("НОМЕР ТЕКУЩЕГО ЛИСТА") and a correction workflow (406/407). | Defer to future sprints but design the schema to allow them (line-item count not capped; nullable correction refs). |
| Scalability of PDF rendering | Maintainability | ReportLab hand-layout cannot realistically reproduce this dense form and duplicates the HTML. | Render PDF from the **same** HTML template via WeasyPrint / headless Chromium — one source of layout. |
| Localization | Hidden assumption | Labels are fixed Russian; data may be RU/KG/foreign. | Keep official labels as fixed Russian strings; treat data as UTF-8; plan i18n for app chrome only. |

---

## Phase 5 — Database Design (proposed, not implemented)

Design goals: 3NF, UUID public identifiers, clear ownership, enforce the 4-state lifecycle,
immutable snapshots, full audit. Reflects **D1** (goods invoice only) and **D2**
(normalized-first; `json_data` is auxiliary, normalized fields/items are the source of truth).

Normalized core = **`parties` / `invoices` (document header) / `invoice_items` / `invoice_totals` / `snapshots`**.

### Tables

**users**
- `id` UUID PK · `username` unique · `hashed_password` · `is_active` · `created_at`
- (role via `user_roles` or a `role` enum column: `ADMIN` | `ISSUER`)

**roles** *(optional if using enum)* — `id`, `name`. **user_roles** — `(user_id, role_id)`.

**invoices** — *document header* (the editable draft / lifecycle row, codes 101–407)
- `id` UUID PK
- `public_token` UUID unique (used only after publish; null while draft)
- `number` (102), `status` enum(`DRAFT`,`VALIDATED`,`SNAPSHOT_CREATED`,`PUBLISHED`)
- `issue_date` (103), `delivery_date` (401), `delivery_type` (402, default `экспорт`/`domestic`),
  `payment_form` (403), `note` (404), `contract_no`+`contract_date` (405),
  `correction_no`+`correction_date`+`correction_reason` (406/407, nullable — deferred workflow)
- `currency_code`, `exchange_rate`, `traceable_flag`
- `json_data` JSONB **nullable** — optional full raw payload for round-tripping/integration;
  **not** read back to render the form (per D2). Normalized columns + items win on any conflict.
- `owner_id` FK→users · `created_at` · `updated_at`

**parties** — supplier & buyer requisites (201–208 / 301–308)
- `id` UUID · `invoice_id` FK · `role` enum(`SUPPLIER`,`BUYER`)
- `inn`, `org_name`, `branch_inn`, `branch_name`, `address`, `tax_authority_code`,
  `tax_authority_name` / `country_code`, `bank_name`, `bik`, `account`
- Exactly two rows per invoice (one SUPPLIER, one BUYER); enforce with a unique
  `(invoice_id, role)` constraint.

**invoice_items** — Раздел 3 line items
- `id` UUID · `invoice_id` FK · `position` (№ п/п)
- `commodity_code` (ТН ВЭД), `name`, `unit`, `unit_price`(numeric, 5dp), `quantity`(5dp),
  `net_amount`(2dp), `vat_rate`, `vat_amount`(2dp), `sales_tax_rate`, `sales_tax_amount`(2dp),
  `total_amount`(2dp), `customs_refs`
- Unique `(invoice_id, position)`.

**invoice_totals** — Итого rows (1 : 1 with invoice; single-sheet MVP → per-sheet == per-invoice)
- `invoice_id` FK PK · `net_total`(2dp) · `vat_total`(2dp) · `sales_tax_total`(2dp)
- `grand_total`(2dp) · `foreign_currency_total`(2dp)
- Derived = Σ(items) and grand_total ÷ exchange_rate; stored (not just computed) so the snapshot
  and PDF have a stable, audited figure. Recomputed by the service on every draft save.

**snapshots** — immutable frozen copy at publish
- `id` UUID · `invoice_id` FK (RESTRICT) · `payload` JSONB (full frozen invoice incl. header +
  parties + items + totals) · `content_hash` (sha256 of canonical payload) · `pdf_path` ·
  `qr_path` · `created_at`
- One published invoice → exactly one authoritative snapshot (allow versions later for corrections).
- This `payload` is the **legal frozen copy** and is distinct from the header's auxiliary
  `json_data`: snapshots are write-once and serve every public/PDF render.

**audit_log**
- `id` UUID · `actor_id` (nullable for anonymous public views) · `action`
  (`CREATE`,`UPDATE`,`VALIDATE`,`PUBLISH`,`VIEW_PUBLIC`,`DOWNLOAD_PDF`,`LOGIN`)
- `entity_type` · `entity_id` · `metadata` JSONB · `ip` · `created_at`

### Relationships & rules
- users 1—N invoices (ownership).
- invoices 1—2 parties, 1—N invoice_items, 1—1 invoice_totals, 1—N snapshots.
- After `PUBLISHED`: invoice + its parties/items/totals become read-only (enforced in service
  layer; reject mutations with 409). Public/PDF read only from `snapshots`.
- Indexes: `invoices(owner_id, status)`, `invoices(number)` unique, `invoices(public_token)`
  unique, `parties(invoice_id, role)` unique, `invoice_items(invoice_id, position)` unique,
  `snapshots(invoice_id)`, `snapshots(content_hash)`, `audit_log(entity_type, entity_id)`,
  `users(username)` unique.
- UUIDs for all externally-referenced IDs; sequential ints never exposed in URLs.

---

## Phase 6 — API Design (proposed)

Convention: server-rendered HTML (current stack) + a thin JSON layer for future integration.
Listed as logical endpoints; permissions noted.

### Public (no auth)
| Method | URL | Request | Response | Permissions |
|---|---|---|---|---|
| GET | `/public/{public_token}` | token in path | HTML verification page (from snapshot) | anyone |
| GET | `/public/{public_token}/pdf` | token | PDF (from snapshot) | anyone |
| GET | `/public/{public_token}/verify` | token | JSON `{authentic, number, hash, issued_at}` | anyone (future API) |

### Authenticated (ISSUER)
| Method | URL | Request | Response | Permissions |
|---|---|---|---|---|
| GET | `/login`, POST `/login`, GET `/logout` | credentials | session | anyone / self |
| GET | `/dashboard` | — | HTML list of **own** invoices | owner |
| GET | `/invoices/new` | — | editor (empty ESF form) | issuer |
| POST | `/invoices` | full ESF payload | redirect to draft | issuer |
| GET | `/invoices/{id}` | — | editor/view of own draft | owner |
| PUT/POST | `/invoices/{id}` | edited payload | updated draft (only if DRAFT) | owner |
| POST | `/invoices/{id}/validate` | — | validation result; status→VALIDATED | owner |
| POST | `/invoices/{id}/publish` | — | snapshot+PDF+QR; status→PUBLISHED | owner |
| GET | `/invoices/{id}/pdf` | — | PDF (own) | owner |

### Administrator
| Method | URL | Request | Response | Permissions |
|---|---|---|---|---|
| GET | `/admin/users` | — | user list | admin |
| POST | `/admin/users` | username, role | created user | admin |
| POST | `/admin/users/{id}/disable` | — | disabled | admin |
| GET | `/admin/audit` | filters | audit-log view | admin |

Rules: no business logic in routers (Controller→Service→Repository); ownership checked in the
service; mutating routes require CSRF token; published invoices reject edits with 409.

---

## Phase 7 — Security Review

| Area | Weakness (current) | Recommendation |
|---|---|---|
| Authentication | Hardcoded session secret; seeded `admin/admin123`; no expiry/lockout/rate-limit | Env-provided secret; no default creds in prod; session TTL; login throttling |
| Authorization | Dashboard & generate operate on **all** documents; `is_admin` defaults True | Enforce ownership in service; roles `ADMIN`/`ISSUER`; default non-admin |
| Ownership | Not enforced — any logged-in user can view/generate any document by id | Every read/write checks `owner_id == current_user` (admins exempt) |
| UUID exposure | Public page keyed by **sequential** `ESF-00001` → trivially enumerable | Opaque `public_token` (UUIDv4); never expose sequential ids/numbers in URLs |
| CSRF | No CSRF tokens on POST forms (login, create, generate) | CSRF token per session on all state-changing forms |
| Password storage | bcrypt via passlib — OK | Keep; tune cost factor; consider argon2 |
| Public links | Number-based, guessable; leak whether an id exists | Token-based; return uniform 404 for missing/unpublished |
| Edit permissions | "generate" is the only gate; no validation; drafts editable by any user | Ownership + lifecycle guard; only owner edits own DRAFT |
| Document immutability | PDF/public read the **live, mutable** row; no snapshot | Freeze to snapshot + content hash on publish; serve everything public from snapshot; reject post-publish edits (409) |
| Transport / headers | Not configured | HTTPS, secure+httponly+samesite cookies, security headers, behind nginx (infra/ exists, unused) |
| Secrets/config | `.env.example` exists but app ignores it (hardcoded values) | Centralized settings (pydantic-settings); fail closed when secrets missing |

---

## Phase 8 — Visual Implementation Strategy

**Principle:** rebuild the PDF as **native HTML + CSS**, never as a background image or raster.
See [`UI_REFERENCE.md`](UI_REFERENCE.md) for the exact layout.

**Single-template, four-mode approach.** One Jinja template renders the ESF document body. A
mode flag controls behavior:

| Mode | Inputs | Chrome | Source data |
|---|---|---|---|
| **edit** | `<input>`/`<select>` cells, JS auto-totals | app nav + Save/Validate/Publish | live draft |
| **view** | static cells | app nav + actions | live draft |
| **public** | static cells | minimal header, "VERIFIED" badge, no actions | **snapshot** |
| **pdf** | static cells | none | **snapshot** |

**How the PDF is recreated.**
1. Build a fully-ruled HTML table/grid matching the form: header band (101/102/103), Раздел 1
   two-column requisites, Раздел 2 sale band, Раздел 3 currency strip + line-item table with
   grouped НДС/НсП headers + totals rows, footer with QR + signatory (450).
2. Reusable components: **digit-box** (INN/dates), **section header**, **field cell** (code +
   label + value), **money/number** formatter.
3. Print CSS: `@page { size: A4 landscape; margin: 8mm }`, hairline borders, condensed font,
   monochrome.
4. PDF engine: render the **same HTML** with **WeasyPrint** (pure-Python, honors `@page`) or a
   headless-Chromium printer — *replacing* the current ReportLab hand-layout. This guarantees
   screen and PDF are pixel-identical and eliminates duplicated layout logic.
5. QR generated server-side (existing `qrcode` lib is fine), embedded bottom-left, encoding the
   `public_token` URL.

**Why not ReportLab:** it requires re-expressing the entire dense grid in Python, will drift
from the HTML, and is far costlier to match this form precisely. HTML→PDF reuses one layout.

---

## Phase 9 — Sprint Planning (revised)

The existing roadmap's Sprint order is sound, but Sprints 3–11 must be **redone** against the
real ESF domain. Proposed plan:

| Sprint | Goal | Deliverables | Dependencies | Definition of Done | Complexity |
|---|---|---|---|---|---|
| **0** | This review (current) | UI_REFERENCE.md, this doc, reset trackers | PDF, repo | Docs approved; trackers reflect reality | S |
| **3R** | Correct DB schema | Single Base/engine; users, invoices (header), parties, invoice_items, invoice_totals, snapshots, audit_log; Alembic baseline | S0 approved | `alembic upgrade head` on Postgres; ORM == migration | M |
| **4** | Invoice CRUD (draft) | Service/repo/controllers for create/edit/list **own** drafts; ownership enforced | 3R | Create/edit/list a real ESF draft; ownership tested | M |
| **5** | Validation engine | INN, required requisites, ≥1 line, totals math, currency/rate, VAT/НсП | 4 | Invalid drafts blocked with field errors; status→VALIDATED | M |
| **6** | Snapshot engine | Freeze JSON payload + content hash on publish; immutability guard | 5 | Publish creates snapshot; post-publish edits rejected (409) | M |
| **7** | HTML ESF template + PDF + QR | One template (edit/view/public/pdf); WeasyPrint PDF; QR token | 6, UI_REFERENCE | PDF visually matches PDF reference; QR resolves | L |
| **8** | Public verification | `/public/{token}` from snapshot; verify endpoint | 6, 7 | Anonymous view by token; sequential ids not exposed | S |
| **9** | Auth + RBAC | Env secret, no default creds, ADMIN/ISSUER, CSRF, sessions | 4 | Roles enforced; CSRF on all POST; no hardcoded secret | M |
| **10** | Audit log | Record + admin viewer for all critical actions | 9 | Critical actions logged; admin can view/filter | S |
| **11** | UI polish | Dashboard, editor UX, public page styling | 7–10 | End-to-end flow usable | M |
| **12** | Production hardening | nginx (infra/), HTTPS, security headers, logging, env config, tests | all | Compose up clean; tests pass; headers present | M |

(Sprints 1–2 — FastAPI skeleton + Postgres compose — are genuinely done and reusable.)

---

## Phase 10 — Final Assessment

| Dimension | Score (0–10) | Rationale |
|---|---|---|
| **Architecture** | **4** | Layering intent is good (Controller→Service→Repository) and partly followed, but undermined by dual Base/engine, no snapshot, wrong domain model, CWD-relative mounts. |
| **Requirement completeness** | **2** | Implements a generic form, not the Kyrgyz ESF. Most real requirements (requisites, line items, taxes, validation, snapshot, audit, RBAC) absent. |
| **Security** | **3** | bcrypt is the one bright spot. Hardcoded secret, default admin, no ownership, enumerable public links, no CSRF, mutable "published" docs. |
| **Scalability** | **5** | Postgres + layered services scale fine; ReportLab hand-layout and missing pagination/correction design are the limiters. |
| **Buildability** | **6** | Stack is simple and runs; Sprints 1–2 solid. But the app currently runs on SQLite while infra targets Postgres, and the snapshot table isn't created — so "it builds" hides real breakage. |
| **Visual replication feasibility** | **8** | The form is monochrome, grid-based, fully specifiable in HTML/CSS. Very reproducible via WeasyPrint/headless Chromium. Current ReportLab path is the wrong tool but the goal is clearly achievable. |

### Critical risks
1. **Wrong domain model** — building further on the generic `Document` compounds rework. *(highest)*
2. **No immutability** — "published" docs are live mutable rows; legally and architecturally unacceptable for an invoice system.
3. **Dual Base/engine split** — silent data-layer breakage (snapshots table never created; SQLite vs Postgres divergence).
4. **Enumerable public links + no ownership** — anyone can enumerate/guess and read documents.
5. **Doc/reality drift** — trackers say Sprint 2 while Sprints 3–11 are half-built; planning can't trust them.

### Recommended improvements
1. Adopt the PDF as the canonical ESF definition; redesign the schema (Phase 5).
2. Unify on one `Base` + one Postgres engine driven by `DATABASE_URL`.
3. Implement the full 4-state lifecycle with a real snapshot + content hash.
4. Switch PDF generation to HTML→PDF (WeasyPrint) sharing one template.
5. Opaque `public_token`, ownership checks, CSRF, env-based secrets, non-admin default.
6. Reset `PROJECT_STATE.md` / `ROADMAP.md` / `MASTER_PROGRESS.md` to reflect reality and the revised plan.

### Final recommendation
**Do not extend the current `Document` model.** Treat Sprints 1–2 (FastAPI + Postgres compose)
as the foundation, **discard or quarantine the generic Sprint 3–11 code**, and restart from
**Sprint 3R** with the ESF schema above. The visual goal is highly feasible; the blocker is the
data model and the missing immutability — both addressable early. With the redesign, this is a
buildable, coherent platform.

**Awaiting approval before any code (Sprint 1 / 3R).**
