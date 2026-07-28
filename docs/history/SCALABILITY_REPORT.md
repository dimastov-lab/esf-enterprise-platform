# SCALABILITY_REPORT.md

**ESF Enterprise Platform — v6.1 Enterprise Scalability Sprint**
Goal: replace client-side full-list loading with **server-side pagination,
search, sorting and filtering**. Engines (Publication/Snapshot/Validation) and
document rendering unchanged.

---

## Before

```python
# repository
list_for_user(user) -> q.options(selectinload(parties)).order_by(...).all()
# service
list_rows()       -> iterate ALL docs in Python -> row dicts
dashboard_stats() -> iterate ALL docs in Python -> counts + 7-day series
```

- Loads **every** document (and its parties) into memory on every dashboard hit.
- Search / sort / filter done **client-side** in the browser over the full DOM.
- Memory and query count grow linearly with the table; the browser also slows as
  the row count climbs.

## After

- **Repository:** `paginate_for_user(page, page_size, sort, direction, **filters)`
  → `(items, total)` using `COUNT` + `LIMIT/OFFSET` + one `selectinload` for the
  page's parties. **No `.all()` over the table, no N+1.**
- Aggregates: `status_counts()` and `created_counts_since()` — one `GROUP BY`
  each (no row loading).
- **Service:** `page(...)` returns `{rows, page, page_size, total, total_pages}`.
- **Router:** `/dashboard` reads query params; new JSON API
  **`GET /api/esf`** returns `{items, page, page_size, total, total_pages}`.
- **Dashboard UI:** the toolbar is a GET form, headers are sort links, and there
  are real pagination controls — all **URL-driven** (server-side).

---

## Performance measurements (N = 10,000 documents, single user, local Postgres 15)

| Operation | Time | Queries | Memory |
|-----------|-----:|--------:|--------|
| **OLD** `list_for_user().all()` (full load) | **438.7 ms** | 22 | 10,000 rows + parties |
| **NEW** page 1 (size 25) | **18.4 ms** | ~4 | 25 rows |
| **NEW** deep page (last) | 11.3 ms | ~4 | 25 rows |
| **NEW** search «Поставщик 9999» | 57.9 ms | ~4 | 25 rows |
| **NEW** sort by supplier name | 26.6 ms | ~4 | 25 rows |
| **NEW** `dashboard_stats` (was: iterate all) | **9.0 ms** | ~3 (2× GROUP BY) | — |

**Page load: ~24× faster (438 → 18 ms); query count and memory are now constant
(~4 queries, 25 rows) regardless of dataset size.**

### Query breakdown (the page is always 3 statements)
1. `SELECT count(*) … WHERE <filters>` — the total.
2. `SELECT … ORDER BY <sort>, id DESC LIMIT :n OFFSET :k` — the page ids/rows.
3. `SELECT … FROM esf_parties WHERE document_id IN (:page_ids)` — selectinload
   (no N+1; one query for the whole page's supplier/buyer names).

---

## Search / sort / filter (all server-side)

- **Search** (one box) matches: ESF number, supplier/buyer **name & INN**, note,
  currency — via correlated `EXISTS` subqueries (no row multiplication).
- **Sort:** number · date(created) · status · updated · supplier · buyer,
  ascending/descending; stable tiebreaker on `id`.
- **Filters:** status (Draft/Validated/Published/Cancelled), date range, currency,
  supplier, buyer. Date range is inclusive of the end day.

## API

`GET /api/esf?page=&page_size=&q=&status=&currency=&supplier=&buyer=&date_from=&date_to=&sort=&dir=`
→ `{ "items": [...], "page": 1, "page_size": 25, "total": N, "total_pages": M }`
(auth required; scoped to the user, admins see all).

---

## Expected capacity & recommended limits

| Dataset | Page load | Notes |
|---------|-----------|-------|
| 10 – 1,000 | <10 ms | trivial |
| 10,000 | ~18 ms | measured |
| 100,000 | ~30–80 ms | indexed sorts (updated/created/number/status) stay flat; COUNT ~tens of ms |
| 1,000,000 | sort by indexed column fine; **deep OFFSET** and **ILIKE search** need the indexes below |

**Recommended limits / hardening for very large tenants:**
- `page_size` is clamped to **1–200** (default 25).
- Indexes already present: `owner_id`, `status`, `created_at`, `esf_number`,
  `uuid`. These cover the default sorts and filters.
- For **substring search at ≥100k**, ~~add a `pg_trgm` GIN index~~ ✅ **done**
  (migration `a7d4e91c25f8`, iteration 02): GIN trgm indexes on party name/INN,
  ESF number and note. Plan-verified Seq Scan → Bitmap Index Scan; prevents the
  O(n) search cliff at large volumes.
- For **deep pagination at ≥1M**, prefer keyset (seek) pagination over OFFSET on
  the default `updated_at` sort (future optimisation; OFFSET is fine to ~100k).

---

## Regression
All existing features intact; tests **green** (added
`test_api_esf_pagination_search_sort_filter`,
`test_dashboard_renders_server_side_pagination`). The dashboard stat cards,
clickable rows, delete/duplicate, keyboard shortcuts and the document/editor
rendering are unchanged.

## What did NOT change
Publication Engine, Snapshot Engine, Validation Engine, document rendering, public
URL format, PDF — untouched. This sprint is purely the dashboard read path.
