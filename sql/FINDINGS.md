# SQL Investigation — Notable Findings

## Duplicate transaction references (query 4)
11 duplicate transaction_ref pairs found, each ending in `4999`/`9999` at
regular ~5,000-row intervals — consistent with the synthetic data generator's
intentional duplicate-injection logic (`database/generate_data.py`). This
confirms the generator's known behavior; a real occurrence of duplicate refs
in production would indicate a client-side retry without idempotency, or a
generator/upstream bug on the payment initiator's side.

## Sep 17 anomalous success rate (query 5)
`2026-09-17` shows a 50% success rate (1/2) versus ~82% every other day. This
is not a data quality bug — it reflects manual API test transactions created
during Step 4/8 validation (e.g. TXNTEST0001, TXN999002), which fall outside
the generator's Sep 1–10 date range. Flagged explicitly so it isn't mistaken
for a real anomaly.

## Reconciliation gap (query 6)
45,148 transactions are marked SUCCESS, but only 42,463 (94.1%) have a
matching successful callback recorded — 2,685 successful payments
(~$134M notional, proportionally) have no confirmed successful callback
delivery. This is a genuine, actionable finding: it means the payment
succeeded on the processing side but the downstream notification to the
customer/merchant may never have been confirmed delivered. In a real system
this would warrant a callback-retry/dead-letter investigation, not just a
one-off manual resend.

## Processing time asymmetry (query 7)
FAILED transactions take longer on average to reach a terminal state (59.5s
avg / 114s p95) than SUCCESS transactions (45.6s avg / 86s p95). This is
consistent with failure paths typically involving additional retries/timeouts
before giving up, rather than failing fast.
