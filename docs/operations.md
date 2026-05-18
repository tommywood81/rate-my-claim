# Operations runbook

Day-two operations for Rate My Claim.

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — process up |
| `GET /ready` | Readiness — Postgres + Redis reachable |
| `GET /metrics` | Prometheus scrape (restrict in production) |

Through nginx locally: `http://localhost:8080/health`

## Deploy / upgrade

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec nginx nginx -s reload
```

Development stack:

```bash
docker compose up -d --build
```

## Migrations

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Rollback (destructive on disposable env only):

```bash
docker compose exec backend alembic downgrade -1
```

## Seed and demo data

```bash
docker compose exec -e SEED_DEVELOPMENT=true backend python scripts/seed_development.py
docker compose exec backend python scripts/seed_graph_demo.py
```

## Celery

```bash
docker compose logs -f celery
docker compose exec celery celery -A app.workers.celery_app inspect ping
```

Re-queue enrichment: moderation UI or `POST /api/v1/moderation/pending-claims/{id}/reprocess`

## Observability

```bash
docker compose --profile observability up -d
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (dashboard: **Rate My Claim — Operations**)
- Enable traces: `OTEL_ENABLED=true` in `.env`, restart `backend`

## Backups

- **Postgres**: volume `postgres_data` on Compose installs — snapshot the volume or use `pg_dump` from the `postgres` container.
- **Redis**: ephemeral by default; broker queues can be rebuilt. Persist only if you enable AOF/RDB intentionally.

## Incident response

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| 502 after `restart backend` | nginx cached old container IP | `docker compose exec nginx nginx -s reload` |
| Enrichment stuck | Celery down or OpenAI budget | Check `celery` logs; Redis keys `rmc:openai:*` |
| 429 `OPENAI_TOKEN_BUDGET_EXCEEDED` | Daily/scope cap | Raise limits or `OPENAI_ENFORCE_TOKEN_BUDGETS=false` (dev only) |
| 401 moderation | Missing session cookies | Login on same origin; check `COOKIE_SECURE` vs HTTP |
| Empty search results | Missing embeddings | Ensure claims have `embedding` populated |

## Security checklist (production)

- [ ] Rotate `SECRET_KEY` and database passwords
- [ ] `COOKIE_SECURE=true`, correct `CORS_ORIGINS` and `PUBLIC_APP_URL`
- [ ] TLS terminated (nginx prod or load balancer)
- [ ] `/metrics` not public (see `nginx.prod.conf` ACLs)
- [ ] Remove or disable development seed accounts
- [ ] Store `OPENAI_API_KEY` in a secret manager
