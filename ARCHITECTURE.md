# Architecture

## Components
- **Postgres 16** — `customers`, `transactions`, `callbacks` tables
  (`app/db/schema.sql`). Seeded with 1,000 customers / 55,000 transactions
  via `app/db/generate_data.py` (deterministic, seed=42).
- **API (FastAPI, sync psycopg2)** — `/health` (DB-aware), `/api/customers`,
  `/api/payments`, `/api/payments/{ref}`. API-key auth via `X-API-Key` header
  (disabled when unset, for local dev convenience). Idempotent payment
  submission by `transaction_ref` (200 + `Idempotent-Replay: true` on
  resubmit, not a duplicate insert).
- **UI** — static HTML/JS served by nginx, talks directly to the API
  (CORS open). No build step, minimal footprint for the container image.

## Why these choices
- **Sync psycopg2, not async**: simplest to reason about and defend at this
  scale; async adds complexity with no throughput benefit for an L2-support
  demo app.
- **Idempotency by transaction_ref, not a dedicated idempotency-key header**:
  matches how the domain naturally dedupes (a transaction ref IS the
  business idempotency key), avoids adding infrastructure not asked for.
- **API replicas=2, UI replicas=1**: API is stateless (all state in
  Postgres) and worth demonstrating horizontal scalability for; UI is static
  files with no meaningful availability argument for extra replicas here.
- **DB as Deployment+PVC, not StatefulSet**: single replica, no failover
  requirement in scope — StatefulSet semantics would need to be justified
  and aren't earning anything here.
- **Schema via ConfigMap+Job (idempotent), seed data via kubectl exec+pipe**:
  schema.sql is small/static (fits ConfigMap's 1MiB limit) and needs to run
  once per fresh cluster — a Job is the right primitive. seed.sql is 55k+
  rows, exceeds ConfigMap's limit, and only needs to run interactively once
  per environment setup — streaming it is simpler and avoids inventing
  unnecessary infrastructure.
- **Readiness probe on `/health` (DB-aware)**: ensures Kubernetes pulls API
  pods out of Service rotation the moment Postgres is unreachable, rather
  than serving 500s to users while claiming to be Ready.

## Data flow
UI → API (HTTP, `X-API-Key` header) → Postgres (psycopg2, sync).
K8s: `minipay-ui` Service → `minipay-api` Service → `minipay-db` Service,
all ClusterIP internally; api/ui additionally exposed as LoadBalancer for
external access via k3d's servicelb on the ports reserved at cluster
creation (8080, 8081).

## Known limitations
- No TLS between components (fine for this local assessment; would use
  cert-manager + Ingress TLS termination in a real cluster).
- Secret is a plaintext K8s Secret manifest committed to git — acceptable
  for local dev only, not production practice (see AI_USAGE.md).
- No HPA configured — replica counts are static, chosen for the reasons
  above rather than load-tested.
