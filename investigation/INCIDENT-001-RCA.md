# INCIDENT-001 – Intermittent Transaction Search Failure

**Priority:** P2
**Status:** Resolved (defect deliberately introduced per incident instructions, then diagnosed and fixed)

## Note on reproduction
This implementation's `GET /api/payments/{ref}` endpoint did not naturally
exhibit this fault. Per the incident's own instructions ("where your own
implementation does not naturally reproduce this fault, deliberately
introduce a realistic defect, demonstrate the failure, and then
diagnose/fix it"), a defect was deliberately introduced: a
`processing_duration_seconds` field was added to the response, computed as
`(completed_at - created_at)`, without checking whether `completed_at` was
NULL.

## Observations
Users report transaction searches intermittently return HTTP 500 — some
transaction refs work, others fail.

## Reproduction steps
1. Query a transaction with status `SUCCESS` (has a non-null `completed_at`):
   `GET /api/payments/TXN00000001` → 200 OK
2. Query a transaction with status `PROCESSING` (`completed_at` is NULL by
   design — see `database/schema.sql`):
   `GET /api/payments/TXN00000029` → **500 Internal Server Error**

## Evidence gathered
Container logs show:

File "/app/main.py", line 180, in get_payment
duration = (tx["completed_at"] - tx["created_at"]).total_seconds()
TypeError: unsupported operand type(s) for -: 'NoneType' and 'datetime.datetime'


## Hypotheses considered
1. Database connectivity/timeout — ruled out; SUCCESS-status lookups against
   the same connection pool succeed consistently
2. Malformed transaction_ref input — ruled out; the failing ref is
   well-formed and exists in the database
3. **Status-dependent NULL field access** — confirmed: every PROCESSING-status
   transaction fails identically, every SUCCESS/FAILED-status transaction
   succeeds identically. Failure correlates perfectly with `completed_at IS NULL`.

## Root cause
`get_payment()` unconditionally computed `completed_at - created_at` without
checking for NULL. Since ~5% of transactions are legitimately in PROCESSING
status with `completed_at IS NULL` (by schema design), any lookup of a
PROCESSING transaction reliably crashed. This presents as "intermittent" from
a user's perspective because which specific transaction_ref they happen to
search determines whether they hit the bug — it is fully deterministic
per-transaction, not actually random.

## Immediate corrective action
Deployed a null check: if `completed_at` is NULL, `processing_duration_seconds`
is returned as `null` rather than the calculation being attempted.

## Permanent corrective / preventive action
- Regression test added (`tests/api/test_incident_001_regression.py`) asserting
  a known PROCESSING-status transaction never returns 500 — run as part of
  the standard API test suite so this class of defect cannot silently return
  in a future change
- General principle for code review: any arithmetic/comparison involving a
  nullable database column (per schema: `completed_at`, `failure_code`) should
  have an explicit NULL-handling test case before merge, not just a happy-path test
- Consider a typed response model (Pydantic) that makes nullable fields
  explicit in the API contract, rather than relying on manual dict construction

## Validation performed after fix

curl http://localhost:18080/api/payments/TXN00000001 → 200, processing_duration_seconds: 29.0
curl http://localhost:18080/api/payments/TXN00000029 → 200, processing_duration_seconds: null (previously 500)
pytest tests/api/test_incident_001_regression.py -v → 1 passed


## Note on troubleshooting this fix itself
While applying this fix, a manual edit introduced an indentation error
(a duplicated, wrongly-indented `return result` statement) that crashed the
container on startup, and separately a stale Docker image cache briefly
masked whether the fix was actually deployed. Both were diagnosed via
`docker compose logs` and resolved with `python3 -m py_compile` (syntax
check) and `docker compose build --no-cache` respectively. Documented here
and in `AI_USAGE.md` as a real example of validating changes by testing
them, not assuming a code edit worked.
