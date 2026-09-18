# INCIDENT-003 – Transaction Search Performance

**Priority:** P2
**Status:** Resolved

## Observations
Operations reported transaction investigation becoming slow as volume grows,
with searches taking several seconds and expected to worsen further.

## Data volume used for investigation
55,000 synthetic transactions (`database/generate_data.py`, seeded/deterministic),
satisfying the incident's "~50,000+ transactions" requirement.

## Evidence gathered
`EXPLAIN (ANALYZE, BUFFERS)` on the most common access pattern — lookup by
`transaction_ref` — showed a full sequential scan reading all 55,000 rows
(`Rows Removed by Filter: 55000`), 677 buffer pages, 3.81ms per lookup.
Full evidence: `sql/PERFORMANCE.md`.

## Root cause
No index existed on `transaction_ref`, the column used for essentially every
transaction lookup (API `GET /api/payments/{ref}`, support CLI, reconciliation
queries). Every lookup degraded linearly (O(n)) with table growth — exactly
matching the reported "expected to deteriorate further" trajectory.

## Fix
`CREATE INDEX idx_transactions_transaction_ref ON transactions(transaction_ref);`
(plain B-tree, not UNIQUE — see `sql/PERFORMANCE.md` for why UNIQUE was
deliberately avoided given known legitimate duplicate refs in the data).

## Validation
Post-fix `EXPLAIN ANALYZE` on the identical query showed `Index Scan` instead
of `Seq Scan`: 0.109ms execution time (~35x faster), 4 buffer reads (~170x
fewer). Full before/after evidence: `sql/PERFORMANCE.md`.

## Preventive action
- Add index coverage review to the schema-change checklist for any column
  used in a `WHERE` clause on a table expected to grow past a few thousand rows
- Consider `pg_stat_statements` in production to proactively surface slow
  query patterns before they become support incidents
- Load-test new schemas against realistic data volume (not just empty/small
  dev datasets) before release — this defect would not have been visible
  against a small hand-seeded dev database
