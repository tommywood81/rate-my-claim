# DigitalOcean deployment guide

Deploy Rate My Claim on a single Droplet with Docker Compose (suitable for MVP production) or scale out using managed databases later.

## Recommended topology (Droplet)

| Component | Service |
|-----------|---------|
| Edge | nginx (TLS termination) |
| App | FastAPI backend + Celery worker |
| UI | Next.js (standalone production build) |
| Data | PostgreSQL 16 + pgvector, Redis 7 |

```text
Internet → Droplet :443 (nginx) → frontend:3000
                              → backend:8000
         Celery worker ← Redis ← Postgres (pgvector)
```

## 1. Provision infrastructure

1. Create a **Droplet** (Ubuntu 22.04+, 4 GB RAM minimum for OpenAI enrichment workloads).
2. Create a **managed PostgreSQL** cluster (optional but recommended) with pgvector enabled, or run Postgres in Compose on the Droplet for smaller installs.
3. Create a **managed Redis** (optional) or use the Compose Redis service.
4. Point DNS `A` / `AAAA` records to the Droplet or load balancer.

## 2. Prepare the host

```bash
apt update && apt install -y docker.io docker-compose-plugin git
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Clone the repository and configure environment:

```bash
git clone https://github.com/your-org/rate-my-claim.git
cd rate-my-claim
cp .env.production.example .env
# Edit .env: SECRET_KEY, OPENAI_API_KEY, DATABASE_URL, PUBLIC_APP_URL, CORS_ORIGINS, COOKIE_SECURE=true
```

## 3. TLS certificates

Place Let’s Encrypt certificates (or your CA bundle) on the host:

```bash
mkdir -p nginx/certs
# fullchain.pem and privkey.pem → nginx/certs/
```

Use **certbot** on the host or terminate TLS at a DigitalOcean Load Balancer and run nginx on HTTP internally.

## 4. Build and run

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend alembic upgrade head
docker compose exec -e SEED_DEVELOPMENT=true backend python scripts/seed_development.py
```

Verify:

- `https://your-domain/health`
- `https://your-domain/` (frontend)
- Moderation login with seeded moderator (development seed only — change passwords in production)

## 5. Observability (optional)

```bash
docker compose --profile observability up -d prometheus grafana otel-collector
```

Restrict Grafana/Prometheus ports with UFW or private networking.

## 6. Operations

| Task | Command |
|------|---------|
| Logs | `docker compose logs -f backend celery` |
| Restart API | `docker compose restart backend` |
| Migrations | `docker compose exec backend alembic upgrade head` |
| Reload nginx after backend IP change | `docker compose exec nginx nginx -s reload` |

## 7. Scaling on DigitalOcean

- **Vertical**: larger Droplet, more Celery `--concurrency`.
- **Horizontal API**: multiple Droplets behind a Load Balancer; shared Postgres + Redis; stateless backend replicas.
- **Workers**: dedicated Droplet(s) running only `celery` service.
- **Database**: migrate to **Managed PostgreSQL**; update `DATABASE_URL` / `DATABASE_SYNC_URL`.

See [aws-scaling.md](./aws-scaling.md) for cross-cloud scaling patterns.
