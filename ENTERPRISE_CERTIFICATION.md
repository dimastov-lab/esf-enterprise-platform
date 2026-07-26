# ENTERPRISE_CERTIFICATION.md

**Auditors assumed:** Government, Big Four, Fortune 500 CTO, security auditors,
enterprise architects, chief accountants.
**Method:** scored against the actual code in this repo. Only real, measurable
gaps are listed — no cosmetic perfectionism, no invented work.
**Effort key:** S = <1 day · M = 1–3 days · L = >3 days.
**Value:** High / Med / Low (engineering value, not vanity).

> **Headline:** mature, well-architected product. **Nothing is a true 10/10 yet.**
> The gaps are mostly *engineering-process and ops* (CI, observability, one
> dependency CVE, horizontal-scale state), not product correctness. Overall ≈ **8.2/10**.

---

## 1. Architecture — **9 / 10** (target 10)
**Why not 10:** clean Controller→Service→Repository, atomic publication, immutable
snapshots, additive migrations — genuinely good. But there are no *enforced*
boundaries (no import-linter/arch tests), and a couple of files have grown large
(`routers/esf.py`, `templates/esf/form.html` ~1.6k lines).
**Required:** add an architecture/import test (e.g. import-linter) asserting
"routers never import models directly", split the mega-template into includes.
**Effort:** M · **Value:** Med · **Worth it:** Yes (cheap guardrail).

## 2. Backend — **9 / 10**
**Why not 10:** thin services, DI, fail-closed config. Missing **structured logging,
request IDs, and an error taxonomy** — errors surface as bare 500s with no
correlation id. No application-level metrics.
**Required:** add JSON logging + request-id middleware + a small exception→HTTP
mapping; emit basic metrics.
**Effort:** M · **Value:** High (ops) · **Worth it:** Yes.

## 3. Security — **7 / 10**
**Why not 10:** strong fundamentals (session-bound CSRF, RBAC, owner isolation,
bcrypt, fail-closed `SECRET_KEY`, `same_site=lax` + `Secure` in prod, login rate
limiting). Real gaps:
- **Dependency CVE:** `python-multipart==0.0.9` — CVE-2024-53981 (multipart DoS),
  fixed in **0.0.18**. *(Real, must fix.)*
- **Rate limiter is in-process** → bypassable across multiple workers/replicas.
- **FastAPI `/docs` & `/openapi.json` exposed in production** (no `docs_url=None`).
- No dependency scanning / SBOM / pinned hashes; deps somewhat dated (fastapi 0.111).
**Required:** bump `python-multipart` (+ `pip-audit`/Dependabot in CI); move the rate
limiter to a shared store (Redis) when running >1 worker; disable docs in prod or
gate behind auth.
**Effort:** S–M · **Value:** High · **Worth it:** Yes (CVE + multi-worker bypass are real).

## 4. Performance — **8 / 10**
**Why not 10:** server-side pagination, pg_trgm search indexes, constant query
count, instant client-side calc. Gaps: deep `OFFSET` at ~1M rows (keyset/seek
pagination would be flat), no DB `statement_timeout`, no perf test in CI, no caching
of hot reads.
**Required:** keyset pagination on the default `updated_at` sort; `statement_timeout`;
a small load test in CI.
**Effort:** M · **Value:** Med (only bites at very large scale) · **Worth it:** Partially (do statement_timeout now; keyset when needed).

## 5. Database — **9 / 10**
**Why not 10:** FKs with `ondelete` rules, unique/not-null constraints, indexes,
ORM immutability guard, linear migrations, sha256 snapshot hash. Gaps: no
`statement_timeout`, no documented PITR, no table partitioning plan for the largest
tenants.
**Required:** set `statement_timeout`; document PITR/WAL backup; note a partitioning
strategy for `esf_documents` at extreme scale.
**Effort:** S–M · **Value:** Med · **Worth it:** Yes for statement_timeout + PITR.

## 6. PDF — **8 / 10**
**Why not 10:** single source-of-truth HTML→PDF (WeasyPrint), embedded DejaVu Sans,
true A4, value formatting matched to the official form. Gaps:
- **No multi-sheet pagination** — long item lists don't split into sheets with
  repeated headers / final-sheet totals (official behaviour).
- **Not PDF/A** — government archival often requires PDF/A-2/3.
- `Producer: WeasyPrint`, no digital signature → honestly distinguishable from the
  genuine GNS output (correct, not a forgery — but a gap vs "indistinguishable").
**Required:** multi-sheet rendering (needs a multi-sheet reference); optional PDF/A
export profile.
**Effort:** L · **Value:** Med–High (compliance) · **Worth it:** Yes if long invoices / archival are in scope.

## 7. Public Viewer — **9 / 10**
**Why not 10:** document-first light viewer, Fit Page/Width/zoom, paper shadow,
correct margins, QR in-document, matches the provided salyk.kg screenshots. Gap:
**no live pixel verification** against the running official site (environment can't
reach it); multi-page navigation absent (tied to multi-sheet).
**Required:** live diff once network access exists; page navigation when multi-sheet lands.
**Effort:** M · **Value:** Med · **Worth it:** When a reference/live access is available.

## 8. Editor — **9 / 10**
**Why not 10:** fits one screen (no scroll), numbered wizard with live status,
Excel-grade grid (paste/fill/arrows), autocomplete, auto-VAT, silent Ctrl+S,
auto-recovery, full keyboard. Gaps: no editing of multi-sheet docs; no
field-level inline (as-you-type) server validation (only on «Проверить»/publish,
mitigated by the wizard + AI checks).
**Required:** multi-sheet edit support; (optional) live validation mirror.
**Effort:** M–L · **Value:** Med · **Worth it:** With multi-sheet.

## 9. Dashboard — **9 / 10**
**Why not 10:** full-width, server-side pagination/search/sort/filter, batch
operations, analytics, clickable rows, keyboard. Gaps: search requires Enter/«Найти»
(no search-as-you-type); no saved views/filters; no column chooser.
**Required:** debounced search-as-you-type via `/api/esf` (template partial swap, no
row-markup duplication).
**Effort:** M · **Value:** Med (felt comfort) · **Worth it:** Yes.

## 10. UX — **9 / 10**
**Why not 10:** Office/Acrobat-like, document-first, keyboard-first, confirmations
only where they matter, consistent components. Gaps: no dark theme / user settings;
**Russian only** (Kyrgyz is a state language — relevant for a KG gov product);
partial ARIA / no automated a11y audit.
**Required:** i18n scaffold (RU/KY); a11y pass; optional dark theme.
**Effort:** L (i18n) · **Value:** Med · **Worth it:** i18n yes for KG; theme optional.

## 11. Compliance — **8 / 10**
**Why not 10:** all 35 STI-007 fields round-trip (tested), GNS number format,
5-decimal price/qty, dotted timestamp, corrections + cancellation. Gaps:
**multi-sheet behaviour**, **no live parity certification** (no network access to
esf.salyk.kg), **no government ЭЦП** (digital signature), Kyrgyz language.
**Required:** multi-sheet; live diff; (if legally issuing) integrate the official
signing/submission — out of current scope and would need official API access.
**Effort:** L · **Value:** High (for real-world issuance) · **Worth it:** Yes, but several need official inputs.

## 12. Production — **7 / 10**
**Why not 10:** Dockerfile (non-root, migrate-on-start), prod compose, nginx (TLS +
security headers + gzip), smoke test, fail-closed secret, healthcheck. Gaps:
- **No observability** (no centralized logging/metrics/tracing/error tracking).
- **In-process rate limiter** → bypassable across >1 replica (the one real shared-state
  item). *(QR and PDF are regenerated on the fly per request — deterministic from the
  UUID / live template — so they are replica-safe; the `storage/qr` file write is a
  never-read cache and could simply be dropped.)*
- Default compose DB creds (`esf/esf`) — dev-only but present.
- `/docs` exposed in prod.
**Required:** logging/metrics/error-tracking; Redis-backed rate limit when running
>1 worker; ensure prod overrides creds; disable docs; drop the unused QR cache write.
**Effort:** M–L · **Value:** High · **Worth it:** Yes — these are the real "is it
production-grade at scale" items.

## 13. Testing — **7 / 10**
**Why not 10:** 55 green tests, per-test transaction isolation, atomic-publish
failure injection, real-browser verification (done manually this session). Gaps:
- **No CI** — tests aren't run automatically on push/PR (no gate).
- **No coverage measurement** — coverage % unknown/unproven.
- **One file, integration-only** — no unit/property tests, no automated browser/e2e
  or a11y/load tests in CI.
**Required:** GitHub Actions running pytest (+ a Postgres service) on every PR;
coverage report with a threshold; split tests into modules; add a headless-browser
e2e job for the JS-heavy editor/grid.
**Effort:** S (CI) → M (coverage/e2e) · **Value:** High · **Worth it:** Yes — top priority.

## 14. Documentation — **9 / 10**
**Why not 10:** extensive (CHANGELOG, DEPLOY/BACKUP/OPERATIONS/INSTALL, scalability/
compliance/audit reports, CLAUDE.md, per-iteration reports). Gaps: no consolidated
**README** entrypoint, no **ADR** index, no generated **API reference**.
**Required:** top-level README (quickstart + architecture diagram), an ADR folder,
publish the OpenAPI as a static API ref.
**Effort:** S · **Value:** Med · **Worth it:** Yes (cheap).

## 15. Deployment — **8 / 10**
**Why not 10:** containerized, non-root, migrations on entry, nginx TLS, smoke
test, BACKUP/DEPLOY docs. Gaps: **no CI/CD pipeline** (build/test/scan/deploy), no
IaC, no automated rollback/blue-green, no secrets-manager integration.
**Required:** CI/CD (build image → run tests/scan → push → deploy), secrets via a
manager, documented rollback.
**Effort:** M · **Value:** High · **Worth it:** Yes.

## 16. Maintainability — **7 / 10**
**Why not 10:** clean layered code, zero TODO/FIXME, pinned deps, good naming. Gaps:
- **No linter/formatter/type-checker** (no ruff/black/mypy/pre-commit) — style/types
  not enforced; regressions can slip in.
- A few oversized files (router, mega-template).
- Tests in a single file.
**Required:** ruff + black + mypy + pre-commit, wired into CI; split large files.
**Effort:** S–M · **Value:** High (compounding) · **Worth it:** Yes.

---

## Scorecard

| Category | Now | Target | Gap |
|----------|----:|-------:|----:|
| Architecture | 9 | 10 | 1 |
| Backend | 9 | 10 | 1 |
| Security | 7 | 10 | 3 |
| Performance | 8 | 10 | 2 |
| Database | 9 | 10 | 1 |
| PDF | 8 | 10 | 2 |
| Public Viewer | 9 | 10 | 1 |
| Editor | 9 | 10 | 1 |
| Dashboard | 9 | 10 | 1 |
| UX | 9 | 10 | 1 |
| Compliance | 8 | 10 | 2 |
| Production | 7 | 10 | 3 |
| Testing | 7 | 10 | 3 |
| Documentation | 9 | 10 | 1 |
| Deployment | 8 | 10 | 2 |
| Maintainability | 7 | 10 | 3 |
| **Overall** | **≈8.2** | **10** | — |

---

## "What are the minimum changes to make every category a true 10/10?"

Ranked by value/effort. The first six are cheap and lift the lowest categories
(Security, Testing, Maintainability, Production) the most.

1. **CI pipeline** (GitHub Actions: pytest against a Postgres service + coverage
   gate, on every PR). → Testing, Deployment, Maintainability. **Effort S, Value High.**
2. **Bump `python-multipart` ≥0.0.18 + add `pip-audit`/Dependabot.** Fixes the real
   CVE and keeps deps current. → Security. **Effort S, Value High.**
3. **ruff + black + mypy + pre-commit, enforced in CI.** → Maintainability, Backend.
   **Effort S, Value High.**
4. **Observability:** JSON logging + request-id middleware + error-tracking hook
   (Sentry/OTel optional) + disable `/docs` in prod. → Backend, Production, Security.
   **Effort M, Value High.**
5. **Stateless for horizontal scale:** Redis-backed rate limiter (the only genuine
   shared-state item — QR/PDF are already regenerated per request, so they're
   replica-safe). → Production, Scalability, Security. **Effort S–M, Value High.**
6. **DB hardening:** `statement_timeout`, documented PITR/WAL backups. → Database,
   Performance. **Effort S, Value Med.**
7. **Coverage + test split + a headless e2e job** for the JS editor/grid. → Testing.
   **Effort M, Value High.**
8. **README + ADRs + published API reference.** → Documentation. **Effort S, Value Med.**
9. **Search-as-you-type** + keyset pagination. → Dashboard, Performance. **Effort M, Value Med.**
10. **Multi-sheet documents** (needs a multi-sheet reference). → PDF, Editor,
    Public Viewer, Compliance. **Effort L, Value High** — the one big *product*
    item; the rest above are *engineering-process* items.

### Cannot reach 10 from inside this repo alone (need external inputs — flagged honestly)
- **Compliance / Public Viewer true 10:** requires **live esf.salyk.kg access** for
  a real pixel/behaviour diff, and — for legally issuing ESF — the **official ЭЦП /
  submission API**. These are organizational/credential gaps, not code gaps.
- I will **not** forge provenance (PDF `Producer`, government signature, QR pointing
  at salyk.kg) to fake "indistinguishable" — that is counterfeiting an official
  fiscal document, out of scope on principle.

## 18. Scalability — **8 / 10** *(bonus — explicitly requested in the section list)*
**Why not 10:** server-side pagination + trgm indexes make reads scale; the app is
**stateless except for the in-process rate limiter** (sessions sign with shared
`SECRET_KEY`, and QR/PDF are regenerated per request → replica-safe). Remaining
items: rate-limit state, and deep `OFFSET` at ~1M rows.
**Required:** Redis for the rate limiter; keyset pagination on the default sort.
**Effort:** S–M · **Value:** High at multi-replica scale · **Worth it:** Yes before scaling out.

---

### Bottom line
The product is **correct, well-architected and genuinely enterprise-shaped today**
(≈8.2/10). To make every category a true 10, the **highest-leverage minimum set** is
items **1–6** above (mostly **S/M effort, High value**: CI, the CVE bump, lint/type
gate, observability, shared-state for replicas, DB timeouts). Multi-sheet (#10) is
the only large *product* item, and full compliance certification needs official
access — both honestly flagged rather than faked.
