# Setup & Reproduction

## Prerequisites
- Docker Desktop (with containerd image-store **disabled** — see AI_USAGE.md
  for why; k3d image import fails otherwise)
- k3d, kubectl
- Python 3.12+ recommended for local venvs (host Python 3.14 breaks
  psycopg2-binary/pydantic-core builds — see AI_USAGE.md)

## Option A — Local Docker Compose (fastest)
```bash
docker compose -f docker/docker-compose.yml up -d --build
sleep 5
curl -s http://localhost:8080/health
curl -s http://localhost:8081/healthz
```
UI: http://localhost:8081  API: http://localhost:8080

## Option B — Kubernetes (k3d)
```bash
k3d cluster create minipay \
  --port "8080:8080@loadbalancer" \
  --port "8081:8081@loadbalancer" \
  --agents 1

docker build -t minipay-api:v1 -f app/api/Dockerfile app/api
docker build -t minipay-ui:v1 -f app/ui/Dockerfile app/ui
docker pull postgres:16-alpine
k3d image import minipay-api:v1 minipay-ui:v1 postgres:16-alpine -c minipay

kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secret.yaml
kubectl apply -f k8s/02-configmap.yaml
kubectl apply -f k8s/03-db.yaml
kubectl apply -f k8s/04a-schema-configmap.yaml
kubectl apply -f k8s/04b-schema-job.yaml
kubectl apply -f k8s/05-api.yaml
kubectl apply -f k8s/05b-api-service.yaml
kubectl apply -f k8s/06-ui.yaml
kubectl apply -f k8s/06b-ui-service-patch.yaml

# seed data (regenerate if seed.sql not present — it's gitignored)
python3 app/db/generate_data.py > seed.sql
kubectl exec -i -n minipay deploy/minipay-db -- psql -U minipay -d minipay < seed.sql

kubectl get pods -n minipay
curl -s http://localhost:8080/health
curl -s http://localhost:8081/healthz
```

## Python support CLI
```bash
cd python
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
python support_tool.py --help
```

## API tests
```bash
cd tests/api
pip install -r requirements.txt  # if present
pytest -v
```

## Known environment issues (see AI_USAGE.md for full detail)
- Host Python 3.14 cannot build psycopg2-binary/pydantic-core — use a 3.12
  venv, or rely on the containerized API for anything DB-related.
- Docker Desktop's containerd image-store setting must be OFF for
  `k3d image import` to work reliably.
