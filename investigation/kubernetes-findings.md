# Kubernetes Findings — starter/kubernetes/broken-api.yaml

The supplied starter manifest (`starter/kubernetes/broken-api.yaml`) was reviewed
before being replaced. Defects were identified by inspection and confirmed by
attempting to apply the file as-is against a working cluster.

## Defects identified

| # | Defect | Evidence | Impact |
|---|---|---|---|
| 1 | `image: YOUR_IMAGE_HERE` | literal placeholder value | `ImagePullBackOff` / `ErrImagePull` — pod never becomes Ready |
| 2 | Readiness probe targets port `8081` | `readinessProbe.httpGet.port: 8081`, but the only declared `containerPort` is `8080` | Container never listening on 8081 → readiness probe fails indefinitely → pod never marked Ready → Service never gets this pod as an endpoint |
| 3 | Liveness probe targets port `8080` while readiness targets `8081` | inconsistent ports across the two probes on the same container | Even if readiness were fixed independently, this asymmetry signals a copy/paste error rather than an intentional design |
| 4 | Service selector `app: minipay-backend` does not match Deployment/pod label `app: minipay-api` | `selector` vs `template.metadata.labels` | **Service has zero endpoints regardless of pod health.** This alone fully explains "pods appear to start, but users cannot access the application" (INCIDENT-002) — traffic has nowhere valid to route to |
| 5 | Service `targetPort: 8081` | mismatched against actual `containerPort: 8080` | Even with #4 fixed, traffic would be forwarded to the wrong container port |
| 6 | No `resources.requests`/`limits` | absent from container spec | No scheduling guarantees; a noisy-neighbor pod could starve this workload; no OOM/CPU-throttle protection |
| 7 | DB connection info passed as plain `env.value`, not from a `Secret` | hardcoded `DB_HOST` value inline | Credentials (if extended to include a password) would be stored in plaintext in the manifest / `kubectl describe` output / git history |
| 8 | No `Namespace` object supplied | `namespace: minipay` referenced but never created | `kubectl apply` fails outright against a clean cluster unless the namespace is created out-of-band first |

Defects #4 and #2/#3/#5 are each **independently sufficient** to cause INCIDENT-002's
symptom ("pods start, app unreachable") — a compounding-cause scenario, not a
single bug. Both are called out explicitly rather than stopping at the first one found.

## Corrected implementation

Rather than patch the starter file in place, a full working manifest set was built
under `k8s/`, addressing each defect above:

- `00-namespace.yaml` — explicit Namespace object (fixes #8)
- `01-secret.yaml` — DB password via Secret + `secretKeyRef` (fixes #7; documented as
  a local-dev-only plaintext Secret in AI_USAGE.md — not production practice)
- `02-configmap.yaml` — non-secret DB connection config, keys matched exactly to the
  application's expected env var names
- `03-db.yaml` — Postgres Deployment + PVC for persistent storage + ClusterIP Service
- `04a/04b` — one-time idempotent schema-load Job (checks `to_regclass` before
  creating tables, safe to re-run)
- `05-api.yaml` / `05b-api-service.yaml` — API Deployment (real image tag, both
  probes correctly on port 8080, resource requests/limits set) + Service (selector
  and targetPort correctly matched to the Deployment) — fixes #1, #2, #3, #5, #6
- `06-ui.yaml` / `06b-ui-service.yaml` — same pattern for the UI

## Validation performed

```bash
kubectl -n minipay get svc,deploy,pods
kubectl -n minipay logs deploy/minipay-api
kubectl -n minipay describe svc minipay-api    # confirms Endpoints are populated
curl http://<node-ip>:8080/health
```

Result: 2/2 API replicas Running and Ready, Service endpoints populated
(previously would have been empty under defect #4), full create-customer →
create-payment → lookup flow validated end-to-end against the cluster (not just
docker-compose).

See `incidents/INCIDENT-002-RCA.md` for the incident-response framing of this
same investigation.
