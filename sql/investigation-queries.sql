-- ============================================================
-- 02-database.md — SQL & Data Investigation
-- Run: psql -U minipay -d minipay -f sql/investigation-queries.sql
-- ============================================================

-- 1. Transaction count and total value by status and day
SELECT
    date_trunc('day', created_at)::date AS tx_day,
    status,
    count(*) AS tx_count,
    sum(amount) AS total_value
FROM transactions
GROUP BY tx_day, status
ORDER BY tx_day, status;

-- 2. Top 10 customers by successful transaction value
SELECT
    c.customer_ref,
    c.name,
    count(*) AS successful_tx_count,
    sum(t.amount) AS total_successful_value
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY total_successful_value DESC
LIMIT 10;

-- 3. Transactions stuck in PROCESSING for more than 15 minutes
SELECT
    transaction_ref,
    customer_id,
    amount,
    created_at,
    now() - created_at AS time_in_processing
FROM transactions
WHERE status = 'PROCESSING'
  AND created_at < now() - interval '15 minutes'
ORDER BY created_at ASC;

-- 4. Duplicate transaction references
SELECT
    transaction_ref,
    count(*) AS occurrences
FROM transactions
GROUP BY transaction_ref
HAVING count(*) > 1
ORDER BY occurrences DESC;

-- 5. Daily success rate as a percentage
SELECT
    date_trunc('day', created_at)::date AS tx_day,
    count(*) FILTER (WHERE status = 'SUCCESS') AS success_count,
    count(*) AS total_count,
    round(
        100.0 * count(*) FILTER (WHERE status = 'SUCCESS') / NULLIF(count(*), 0),
        2
    ) AS success_rate_pct
FROM transactions
GROUP BY tx_day
ORDER BY tx_day;

-- 6. Reconciliation: successful transactions vs callback-success
WITH tx_success AS (
    SELECT id, amount FROM transactions WHERE status = 'SUCCESS'
),
callback_success AS (
    SELECT DISTINCT transaction_id
    FROM callbacks
    WHERE callback_status = 'SUCCESS'
)
SELECT
    (SELECT count(*) FROM tx_success) AS successful_tx_count,
    (SELECT sum(amount) FROM tx_success) AS successful_tx_value,
    (SELECT count(*) FROM tx_success ts JOIN callback_success cs ON cs.transaction_id = ts.id)
        AS reconciled_count,
    (SELECT count(*) FROM tx_success ts
        WHERE NOT EXISTS (SELECT 1 FROM callback_success cs WHERE cs.transaction_id = ts.id))
        AS unreconciled_count;

-- 7. Average and p95 processing time (created_at -> completed_at)
SELECT
    status,
    count(*) AS n,
    avg(extract(epoch FROM (completed_at - created_at)))::numeric(10,2) AS avg_seconds,
    percentile_cont(0.95) WITHIN GROUP (
        ORDER BY extract(epoch FROM (completed_at - created_at))
    )::numeric(10,2) AS p95_seconds
FROM transactions
WHERE completed_at IS NOT NULL
GROUP BY status;
