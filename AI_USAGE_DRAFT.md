# AI Usage — running notes (to be finalized into AI_USAGE.md)

## Tools used
- Claude (Sonnet) — architecture decisions, code generation, troubleshooting partner, step-by-step review

## Notable AI-assisted troubleshooting (real infra bugs, not scripted)
1. Host WSL2 Python 3.14 incompatible with psycopg2-binary/pydantic-core (no wheels, PyO3 unsupported) → resolved by containerizing local dev instead of chasing host Python version. Deliberate reproducibility decision, not a workaround.
2. Docker Desktop containerd image-store corruption broke `k3d image import` for ANY image (even stock postgres:16-alpine) → isolated as host image-store issue, not app-specific, by testing with a stock image. Fixed by disabling "Use containerd for pulling and storing images," restarting Docker, recreating k3d cluster + reimporting.

## Corrected/validated AI output (examples for AI_USAGE.md requirement)
- Confirmed TXNXXXX "FAILED" result was expected deterministic behavior (hash(transaction_ref)%100<90 in create_payment), not a bug — validated logic before accepting.
- Flagged that committing a plaintext Secret manifest is fine for local dev only, NOT production practice — would use vault/external-secrets/sealed-secrets or out-of-band apply in production. Explicit tradeoff, not hidden.
- Chose ConfigMap+Job for schema.sql (small/static) vs kubectl exec+pipe for seed.sql (55k+ rows, exceeds 1MiB ConfigMap limit) — right tool per artifact size/lifecycle, not a blanket pattern.

## Design decisions made and defensible in interview
- API replicas=2: demonstrates statelessness, all state in Postgres, horizontal scalability.
- readinessProbe hits /health which pings DB: Service correctly pulls API pods out of rotation if DB unreachable, rather than serving 503s.
- k3d servicelb shows EXTERNAL-IP <pending> — cosmetic/expected in local k3d (klipper-lb still binds reserved host ports); a real cloud LB would populate this.

## Blockers/limitations to state honestly
- (fill in as they arise — Rancher attempt status, any test coverage gaps, etc.)
