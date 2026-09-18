# Python Support Tool — Validation Evidence

Run against live docker-compose Postgres + local API, 2026-09-18.

## Unit tests

7 passed


## Stuck PROCESSING transaction (real seed data)

=== Transaction TXN00000029 ===
Customer: Customer 541 (CUST000541)
Amount: 87256.06
Status: PROCESSING
Created: 2026-09-06 03:14:52
Anomalies:

Transaction has been PROCESSING for 12 days, 4:21:16, exceeding the 15-minute SLA threshold.
Recommended action: Escalate to L3/payments team...

## Healthy SUCCESS transaction (--json mode)
Clean output, "No anomalies detected", full callback history shown.

## Unknown transaction
Exit code 1, clear "not found" message — no stack trace.

## Health check (differentiates dependencies)

Database: ok
API: ok

(Also validated separately with DB container stopped: correctly reported
`Database: unreachable`, `API: ok`, exit code 2 — confirms independent
dependency checking, not a single combined check.)

## Stuck report
99 transactions flagged PROCESSING beyond 15-minute threshold, 1 recent FAILED
(TXN999002 — a known test transaction from API validation in Step 4).
