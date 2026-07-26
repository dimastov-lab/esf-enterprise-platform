# COMPLIANCE_ITERATION_02.md — pg_trgm search indexes (scalability)

**Hat:** Enterprise Architect / Performance. **Policy:** "measure, improve,
measure, document."

## Decision
The v6.1 `SCALABILITY_REPORT.md` flagged that substring search (`ILIKE '%term%'`
on party name/INN, ESF number, note) can't use a b-tree index and would degrade
to a sequential scan at ≥100k documents. I added **pg_trgm GIN indexes** to remove
that cliff. Chosen because it is additive, backward-compatible, zero-downside, and
closes a documented gap (migration `a7d4e91c25f8`).

`pg_trgm` is a *trusted* extension on PostgreSQL 13+, so `CREATE EXTENSION` needs
no superuser in production.

Indexes added (GIN, `gin_trgm_ops`):
`esf_parties.name`, `esf_parties.inn`, `esf_documents.esf_number`,
`esf_supply_info.note`.

## Measurement (honest)
Seeded 50,000 documents; searched a unique party-name term.

| | Query plan (party-name ILIKE) | Wall-clock (full paginate) |
|---|---|---|
| **Without** trgm | **Seq Scan**, cost 1853 | ~157 ms |
| **With** trgm | **Bitmap Index Scan**, cost 55 | ~159 ms |

- **Plan:** the index is used; the party-name lookup cost drops **~33×**
  (sequential scan eliminated).
- **Wall-clock:** unchanged at 50k — at this size the search predicate is not the
  bottleneck (fixed ORM/count/page overhead dominates a near-empty result set).

### Honest conclusion
This is **preventive infrastructure, not a felt win at today's scale.** The plan
proves the optimisation works (no more table scan for search), so it removes the
O(n) cliff that would dominate at 100k–1M rows — the regime where the seq scan
would cost hundreds of ms to seconds. At realistic current volumes search is
already fine without it. Net: cheap, correct insurance with ~zero downside; not a
change an accountant would feel today.

## Quality gate
- Regression: green (search/dashboard/RBAC verified; functional search unchanged —
  the index only changes the plan, not the results).
- Architecture: additive migration, no code/API change.
- Security: no new surface; auth/scoping unchanged.
- Cleanup: all seeded benchmark data removed; no residue in the dev DB.

## Self-review verdict
"Would I merge this?" Yes — it's correct, harmless, and closes a documented gap.
"Would an accountant feel it today?" No — it's for the 100k+ regime. Therefore the
**next iteration targets a felt daily improvement**, not infra.

## Next iteration (planned, felt UX)
Instant **search-as-you-type** on the dashboard via the existing `/api/esf`
endpoint (debounced fetch + client row render), so finding a document needs no
Enter/click and no full-page reload — combined with these indexes it gives a true
enterprise "search feels instant at any scale" experience.
