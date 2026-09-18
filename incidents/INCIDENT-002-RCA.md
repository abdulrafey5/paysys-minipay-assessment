# INCIDENT-002 – Application Unavailable After Deployment

**Priority:** P1
**Status:** Resolved (reproduced against the supplied starter manifest, then fixed)

## Observations
A deployment using `starter/kubernetes/broken-api.yaml` shows pods reaching a
Running state, but the application is not reachable through the Service.

## Reproduction steps
1. `kubectl apply -f starter/kubernetes/broken-api.yaml` (image tag substituted
   with a real built image to isolate this from a separate image-availability issue)
2. `kubectl get pods` — pod(s) reach `Running` but **not `Ready`**
   (`READY 0/1`), because the readiness probe targets port 8081 while the
   container only listens on 8080 (see finding #2 in
   `investigation/kubernetes-findings.md`)
3. `kubectl describe svc minipay-api` — `Endpoints: <none>`, because the
   Service selector (`app: minipay-backend`) does not match the pod label
   (`app: minipay-api`) (finding #4)
4. `curl` to the Service — connection fails / times out, regardless of pod
   health, because there are no valid endpoints to route to

## Evidence gathered
- `kubectl get pods -o wide` — pod IPs assigned, container running, but not Ready
- `kubectl describe pod <pod>` — readiness probe failures logged
  (`Readiness probe failed: HTTP probe failed with statuscode: 000` — connection
  refused on 8081)
- `kubectl describe svc minipay-api` — `Endpoints: <none>`

## Hypotheses considered
1. Image pull failure — ruled out once a real image tag was substituted; the
   readiness/selector defects reproduce independently of the image
2. Application crash-looping — ruled out; container process stays up, it's a
   probe/routing misconfiguration, not an app-level crash
3. Network policy blocking traffic — ruled out; no NetworkPolicy objects exist
   in this cluster/namespace
4. **Probe port misconfiguration + Service selector mismatch** — confirmed via
   direct inspection of the manifest and `describe` output

## Root cause (compounding, two independent causes)
1. Readiness probe on port 8081 against a container that only exposes 8080 →
   pod never becomes Ready
2. Service selector (`minipay-backend`) does not match pod label
   (`minipay-api`) → Service has no endpoints even for a Ready pod

Full defect list: `investigation/kubernetes-findings.md`.

## Immediate corrective action
Applied corrected manifests (`k8s/05-api.yaml`, `k8s/05b-api-service.yaml`)
with probes retargeted to the actual container port and the Service selector
aligned to the pod labels.

## Permanent corrective / preventive action
- Add a CI manifest-lint step (e.g. `kubeconform` or `kubectl apply --dry-run=server`)
  before merge, which would catch the missing-namespace and schema-invalid cases
  but not silently-wrong-but-valid selector/port mismatches
- Add a smoke-test step post-deploy: `kubectl rollout status` **and** an actual
  HTTP request through the Service (not just pod Ready state) before considering
  a deploy successful — this is the check that would have caught the selector
  mismatch that `rollout status` alone would miss
- Peer review of any manifest change touching `selector`/`labels` or probe ports,
  since these are silent-failure-mode fields (no validation error, just wrong behavior)

## Validation performed after fix
```bash
kubectl -n minipay get pods            # 2/2 Ready
kubectl -n minipay describe svc minipay-api   # Endpoints populated with pod IPs
curl http://<node-ip>:8080/health      # 200 OK, {"status":"ok","db":"reachable"}
```
Full end-to-end flow (create customer → create payment → lookup) re-validated
against the cluster after the fix.
