# AI Usage

## Tools used
- Claude (Anthropic, Sonnet) — architecture decisions, code generation,
  troubleshooting partner, incident investigation support, documentation
  drafting.

## Tasks AI was used for
- Scaffolding the FastAPI service, schema, and data generator
- Writing Kubernetes manifests (namespace, secret, configmap, deployments,
  services, schema-loading Job)
- Diagnosing two real infrastructure failures (below)
- Drafting incident RCAs (INCIDENT-001/002/003) from raw investigation
  evidence I gathered myself
- Drafting this documentation set (README, SETUP, ARCHITECTURE, this file)

## Representative prompts / interaction summaries
1. "Help with step 4, I got this error" (pasted a psycopg2-binary build
   failure) — AI diagnosed host Python 3.14 as incompatible with
   psycopg2-binary/pydantic-core (no prebuilt wheels, PyO3 doesn't support
   3.14), recommended containerizing the API rather than chasing a host
   Python version.
2. "k3d image import failing with content digest error" — AI walked through
   isolating the fault (tried a stock postgres image to rule out an
   app-specific build issue), identified Docker Desktop's containerd
   image-store as the root cause, and gave the fix (disable the setting,
   recreate cluster).
3. "The Service shows no traffic reaching pods after deploying the starter
   broken-api.yaml" — AI directed me to inspect `kubectl describe svc`
   endpoints directly rather than only checking pod status, which surfaced
   the selector mismatch independent of the readiness-probe defect.
4. "Why is transaction search slow at 55k rows?" — AI suggested running
   `EXPLAIN (ANALYZE, BUFFERS)` on the actual lookup query rather than
   guessing at an index, which produced the before/after evidence in
   `sql/PERFORMANCE.md`.
5. "Write the schema-loading Job" — AI's first draft did not include an
   idempotency check; I asked it to reconsider since Jobs can be re-applied
   during debugging, and it added the `to_regclass` guard so re-runs don't
   throw `relation already exists` errors.

6. "GUI tests failing with empty #custResult, no console errors" — AI had
   me log actual browser network traffic (page.on("request")/("response"))
   rather than guess, which showed zero POST requests ever fired after the
   click. Root cause: `page.click("text=Create Customer")` matched the
   `<h2>Create Customer</h2>` heading (first DOM match) instead of the
   `<button>`, since the legacy text-selector API does not enforce
   uniqueness. Fixed by switching to `get_by_role("button", name=...)`,
   which targets by accessible role and is unambiguous.

## How I validated AI output
- Every API endpoint change was smoke-tested with curl (and later through
  the UI) before being accepted, including status codes, idempotency
  headers, and error-shape checks (404/422).
- Every K8s manifest change was applied to a live k3d cluster and verified
  with `kubectl get pods/svc`, `kubectl describe`, and an end-to-end
  create-customer → create-payment → resubmit → lookup flow.
- SQL fix (index) was validated with actual before/after `EXPLAIN ANALYZE`
  output, not accepted on the AI's explanation alone.
- Deterministic test data (`random.seed(42)`) meant row counts and status
  splits were cross-checked for exact match across every environment
  (local Docker, k3d) rather than assumed consistent.

## Example where I corrected/rejected AI output
- A `TXN999003` payment returned `status: "FAILED"` during UI testing. My
  first instinct was that this was a bug in the payment endpoint. Before
  accepting AI's explanation, I checked the actual logic
  (`hash(transaction_ref) % 100 < 90` in `create_payment`) and confirmed
  this specific ref legitimately falls in the ~10% deterministic-failure
  bucket by design — not a defect. I did not accept "looks fine" as an
  answer without reading the code path myself.
- Committing a plaintext Kubernetes Secret manifest to git was flagged by
  AI as fine for local dev but explicitly *not* production practice; I
  required this tradeoff be stated explicitly in ARCHITECTURE.md rather
  than left implicit, since an evaluator could otherwise read it as an
  oversight rather than a deliberate scope decision.

## Design decisions made and defensible in interview
- API replicas=2 demonstrates statelessness (all state in Postgres) and
  horizontal scalability.
- DB-aware `/health` readiness probe: Kubernetes pulls API pods out of
  Service rotation if Postgres becomes unreachable, rather than serving
  500s while claiming Ready.
- ConfigMap+Job for schema.sql (small, static, needs idempotent one-time
  apply) vs. `kubectl exec`+pipe for seed.sql (55k+ rows, exceeds
  ConfigMap's 1MiB limit) — matched the tool to the artifact's size and
  lifecycle rather than using one pattern everywhere.
- pg8000 (pure-Python) chosen over psycopg2 for the Python support CLI
  specifically because it runs on the host machine, where the same
  Python 3.14/psycopg2-binary incompatibility from the API step applies;
  containerizing a CLI tool would hurt its usability for an L2 engineer
  running it ad-hoc.

## Blockers / limitations, stated honestly
- Rancher: attempted and documented, not completed — see RANCHER.md. Root
  cause identified (cluster-agent cannot reach rancher-server across
  separate Docker networks via `localhost`); fix documented but not
  executed given SCORING.md's 5-point weight vs. higher-weighted areas.
- GUI test automation: completed (see tests/ui/, evidence/gui-test-output.txt).
  Playwright drives the actual static console against the live API: health
  indicator, customer+payment+lookup happy path, and a duplicate-ref
  conflict case (3 tests, all passing). Built after API/K8s/SQL work per
  SCORING.md's weighting (incidents/K8s/SQL at 20/15/15 vs. GUI at 10),
  once time allowed.
