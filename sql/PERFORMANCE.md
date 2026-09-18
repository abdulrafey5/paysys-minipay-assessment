# SQL Performance Investigation

## Target query
Lookup of a single transaction by `transaction_ref` — the single most frequent
query pattern in the system (used by `GET /api/payments/{ref}`, the Python
support CLI's `--transaction` flag, and L2 investigation generally).

```sql
SELECT * FROM transactions WHERE transaction_ref = 'TXN00054999';
```

## Problem identified
The `transactions` table had **no index on `transaction_ref`** — only the
primary key on the surrogate `id` column. Every lookup by reference performed
a full sequential scan of the entire table.

## Before

Seq Scan on transactions (cost=0.00..1364.50 rows=1 width=75)
(actual time=3.786..3.787 rows=2 loops=1)
Filter: ((transaction_ref)::text = 'TXN00054999'::text)
Rows Removed by Filter: 55000
Buffers: shared hit=677
Execution Time: 3.810 ms


`Rows Removed by Filter: 55000` confirms every one of the 55,000 rows was
read and evaluated to find a match. This is an **O(n)** access pattern: cost
scales linearly with table size, which is precisely the symptom reported in
INCIDENT-003 ("transaction investigation becomes slow as transaction volume
increases... expected to deteriorate further").

## Change made

```sql
CREATE INDEX idx_transactions_transaction_ref ON transactions(transaction_ref);
```

A plain B-tree index was chosen (not `UNIQUE`) because query #4 in
`sql/investigation-queries.sql` confirmed the data legitimately contains
duplicate `transaction_ref` values today — adding a `UNIQUE` constraint would
have failed to apply against existing data and would silently change
application semantics. Fixing duplicate-prevention is a separate,
application-layer concern (ideally enforced at write time via the API's
existing idempotency check), not something to retrofit onto historical data
via a blind schema constraint.

## After

Index Scan using idx_transactions_transaction_ref on transactions
(cost=0.41..8.43 rows=1 width=75) (actual time=0.054..0.055 rows=2 loops=1)
Index Cond: ((transaction_ref)::text = 'TXN00054999'::text)
Buffers: shared hit=1 read=3
Execution Time: 0.109 ms


## Result
- Execution time: 3.81ms → 0.109ms (~35x faster on this 55k-row table)
- Buffer reads: 677 → 4 (~170x fewer pages touched)
- More importantly: access pattern changed from **O(n)** to **O(log n)**.
  The millisecond improvement is modest at current volume, but the
  algorithmic change is what actually prevents the "further deterioration"
  INCIDENT-003 warns about as transaction volume grows past 55,000 —
  a sequential scan would keep getting linearly worse; an index scan
  stays fast at 10x or 100x the current volume.

## Trade-off acknowledged
This index adds a small write-amplification cost (every INSERT to
`transactions` now also updates the index) and additional storage.
For a table whose read pattern (lookup-by-ref, from support tooling,
reconciliation, and the API) vastly outweighs its write pattern (one
insert per payment), this trade-off is clearly justified.
