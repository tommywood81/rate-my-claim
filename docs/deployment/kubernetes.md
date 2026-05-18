# Kubernetes migration notes

Path from Docker Compose to Kubernetes without rewriting application code.

## Workloads

| Compose service | Kubernetes resource |
|-----------------|---------------------|
| `backend` | `Deployment` + `Service` (ClusterIP :8000) |
| `frontend` | `Deployment` + `Service` (ClusterIP :3000) |
| `celery` | `Deployment` (no Service) |
| `nginx` | `Ingress` controller (replace container nginx) or `Deployment` |
| `postgres` | **Managed RDS** (recommended) or `StatefulSet` + PVC |
| `redis` | **ElastiCache** or `StatefulSet` |
| `prometheus` / `grafana` | Helm charts or managed observability |

## Sample layout

```text
Namespace: rate-my-claim
├── Ingress (cert-manager TLS)
├── Deployment/backend  (replicas: 2+)
├── Deployment/frontend (replicas: 2+)
├── Deployment/celery   (replicas: N, HPA on custom metric)
├── Secret/rmc-env      (from External Secrets Operator)
└── Job/alembic-migrate (helm hook or Argo CD PreSync)
```

## Configuration

- Mount environment from **Secrets** + **ConfigMaps** (mirror `.env.production.example` keys).
- `INTERNAL_API_URL=http://backend:8000` (cluster DNS service name).
- `DATABASE_URL` → managed Postgres hostname.
- Probes:
  - Liveness: `GET /health`
  - Readiness: `GET /ready`

## Ingress

Replace `nginx/nginx.prod.conf` with an **Ingress** resource:

- Path `/api` → `backend:8000`
- Path `/` → `frontend:3000`
- Annotate for larger `proxy-read-timeout` (120s) on API routes.

Restrict `/metrics` with internal Ingress or `NetworkPolicy`.

## Migrations

Run as a **Job** before rolling out new API version:

```yaml
command: ["sh", "-c", "alembic upgrade head"]
```

Use the same container image as `backend`.

## Autoscaling

| Workload | HPA signal |
|----------|------------|
| `backend` | CPU 70%, memory, request latency (via Prometheus adapter) |
| `celery` | Redis queue depth (`rmc_celery_queue_depth`) |
| `frontend` | CPU |

## Stateful data

Do **not** run production Postgres/Redis in-cluster unless you operate them day-to-day. Prefer cloud managed services for backups, failover, and patching.

## Docker Compose parity checklist

- [ ] Images built from `backend/Dockerfile` and `frontend/Dockerfile.prod`
- [ ] `NEXT_STANDALONE=1` build arg for frontend
- [ ] Celery broker URLs point to cluster Redis
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` points to in-cluster collector
- [ ] Cookie `COOKIE_SECURE=true` and correct `PUBLIC_APP_URL`

## GitOps

- Package manifests or Helm chart under `deploy/kubernetes/` (future).
- Argo CD / Flux sync from `main` with environment overlays (`staging`, `production`).
