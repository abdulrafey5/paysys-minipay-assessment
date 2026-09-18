# MiniPay — Paysys Labs Implementation & L2 Support Assessment

Candidate: Abdul Rafey
Position: Implementation & L2 Support Engineer

## What this is
A small payment-processing app (Postgres + FastAPI + static UI) deployed to
Kubernetes (k3d), with SQL performance investigation, Python support tooling,
and three incident investigations (RCA-documented) covering the areas in
SCORING.md.

## Repository layout
- `app/` — API (FastAPI) and UI (static/nginx) source + Dockerfiles
- `docker/` — local docker-compose stack (db+api+ui) for fast local dev
- `k8s/` — Kubernetes manifests deployed against k3d (namespace, secret,
  configmap, db+PVC, schema-load Job, api Deployment/Service, ui Deployment/Service)
- `sql/` — performance investigation: before/after EXPLAIN ANALYZE, findings
- `python/` — L2 support CLI (`support_tool.py`) + pure-logic diagnostics lib + unit tests
- `investigation/` — INCIDENT-001 RCA, Kubernetes starter-manifest defect findings
- `incidents/` — INCIDENT-002, INCIDENT-003 RCAs
- `tests/api/` — pytest suite against the running API
- `tests/ui/` — not completed (see AI_USAGE.md for why)
- `evidence/` — supporting screenshots/logs where reproducible commands aren't enough
- `AI_USAGE.md` — AI tool usage, prompts, validation, corrections
Note: kubernetes/ folder is named k8s/ for clarity (structure improvement per INSTRUCTIONS.md).

## Quick start
See `SETUP.md` for full reproduction steps. Short version:
```bash
docker compose -f docker/docker-compose.yml up -d --build
# or, for the Kubernetes path:
k3d cluster create minipay --port "8080:8080@loadbalancer" --port "8081:8081@loadbalancer" --agents 1
kubectl apply -f k8s/
```

## Status
See `AI_USAGE.md` for detailed troubleshooting log and `investigation/`,
`incidents/`, `sql/` for the incident/SQL investigations. Rancher status:
see `RANCHER.md` (attempted / documented per INSTRUCTIONS.md fallback provision).
