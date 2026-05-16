# Rate My Claim

Evidence-backed **semantic claim intelligence** platform (Stage 1 MVP): claim submission, async OpenAI enrichment with retrieval-first prompts, pgvector duplicate detection and hybrid search, structured verdicts with citations, moderation workflows, public claim pages, and discovery voting.

## Stage 1 — what is implemented

These items match the Stage 1 scope from `notebooks/instructions.txt` (claim intake, AI analysis, evidence/citations, embeddings & search, duplicates, public pages, voting, moderation) and are present in this repo.

### Core platform

- **Monorepo**: `backend/` (FastAPI), `frontend/` (Next.js), `nginx/`, root `docker-compose.yml`.
- **PostgreSQL + pgvector**: schema for users, claims, pending claims, evidence, votes, relationships, revisions, `ai_analysis`, moderation actions, audit logs, publisher profiles, ingestion jobs, reputation events, refresh tokens; **HNSW** vector indexes; **FTS** `search_vector` on claims with update trigger.
- **Redis** wired for readiness checks; **Celery** worker for async enrichment (`claims.process_pending`).
- **API**: versioned **`/api/v1`** routes with typed Pydantic bodies and **success/error JSON envelopes**; **Prometheus** metrics at `/metrics`; **`/health`** and **`/ready`** (DB + Redis).

### Claims & AI

- **Submit** → `POST /api/v1/pending-claims` stores `pending_claims`, enqueues Celery.
- **Pipeline (real OpenAI, no mock AI)**: embedding (`text-embedding-3-small`, 1536 dims) → vector **duplicate candidates** (no auto-merge) → **canonicalization** (JSON) → **retrieval-first** context (similar claims’ evidence + optional user URLs fetched via **httpx** + **trafilatura**) → **structured verdict** + confidence analysis + summary → rows in **`ai_analysis`**; pending ends in **`awaiting_moderation`** (or `failed`).
- **Hybrid search**: `GET /api/v1/search/claims` blends semantic (pgvector), lexical (`ts_rank_cd`), and simple quality signals.
- **Public claims**: list/browse, **`GET /api/v1/claims/{slug}`** detail with evidence grouped by stance and AI sections visually separated (frontend mirrors this).

### Moderation & governance

- **Moderator queue**: `GET /api/v1/moderation/pending-claims` (cursor pagination).
- **Actions**: `POST /api/v1/moderation/actions` — **approve** (creates `claims`, `evidence` with embeddings, copies key `ai_analysis` to the claim, revisions + moderation action rows) or **reject**.
- **RBAC**: roles on `users` (`user`, `moderator`, `expert`, `admin`); moderator-only routes; **first registered user is `admin`** (bootstrap).

### Auth & discovery

- **JWT** access + refresh tokens; refresh rows in DB with **rotation** and **revocation**; **HTTP-only cookies** (`rmc_access`, `rmc_refresh`) + Bearer support for API clients.
- **Discovery voting**: `POST /api/v1/claims/{id}/votes` updates **`claim_votes`** and **`claims.discovery_score`**.

### Frontend (Stage 1 surfaces)

- **Next.js 15** App Router, TypeScript strict, **Tailwind**, **TanStack Query**.
- Pages: **home** (recent claims + search entry), **browse/search** (`/claims`), **claim detail** (`/claims/[slug]`, SEO metadata), **submit**, **moderation** (same-origin cookie auth to API).

### Tests & docs

- **pytest**: health check, Phase 2 repository wiring tests; optional **pgvector integration** test when `RUN_PG_INTEGRATION=1`.
- **README** documents required **environment variables** for local and Docker usage (no committed `.env.example`).

---

## Stage 1 — what still needs to be done (or was deferred)

These are gaps versus the full instruction set in `notebooks/instructions.txt`, or natural follow-ups before calling Stage 1 “complete” in a strict audit sense.

### Security & hardening (spec asks for more)

- **CSRF**: double-submit or equivalent for cookie-based sessions on mutating routes (not fully implemented).
- **Rate limiting**: Redis-backed limits (e.g. SlowAPI) on auth and submission endpoints (not wired).
- **Password reset / email verification**: flows and mailer integration (not built).
- **Stricter security headers / CSP**: optional nginx and Next.js hardening pass.

### Spec’d UX and libraries

- **shadcn/ui**: UI is Tailwind-only; shadcn components were not generated/integrated.
- **React Flow** graph and rich **timeline** (confidence / moderation / evidence history) — called out in later phases of the notebook; not in the current UI.
- **robots.txt / XML sitemap** — not added as Next routes yet.

### Backend depth

- **Redis caching** of AI/duplicate/search outputs (keys/TTL policy) — Redis is used for readiness, not yet for application-level cache as described in the instructions.
- **Broader ingestion**: RSS feeds, scheduled refresh jobs, richer ingestion job UI (MVP is URL fetch + similar-claim evidence).
- **Event bus → external queues**: in-process patterns exist; full analytics/observability pipelines (Grafana dashboards, distributed tracing) are not set up.
- **Additional automated tests**: API integration tests, repository tests, Celery task tests, frontend Vitest/RTL (minimal pytest only today).
- **Tooling**: `uv` + `ruff format` / strict `mypy` in CI, **pre-commit** (husky / lint-staged per notebook) — not configured at repo root.

### Operations

- **DigitalOcean / AWS / K8s** deployment guides beyond local Docker (README mentions troubleshooting only).
- **Seed scripts** for demo data (optional; instructions mention realistic seed data for tests).

When the items above are addressed in line with `notebooks/instructions.txt`, Stage 1 can be closed out formally and work can move to the next phased scope (graphs, timelines, deeper observability, etc.).

## Architecture

- **Backend**: FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL **pgvector**, Redis, Celery.
- **Frontend**: Next.js App Router (TypeScript), Tailwind CSS, TanStack Query.
- **Edge**: nginx routes `/api/*` to the API and `/` to Next.js.
- **AI**: OpenAI — **`text-embedding-3-small`** for embeddings; **`gpt-4o-mini`** for canonicalization, summaries, and structured verdicts (configurable via env / settings). Provider abstraction includes an **Ollama**-compatible client for future local models.

## Prerequisites

- Docker & Docker Compose
- An **OpenAI API key** (`OPENAI_API_KEY`)

## Quick start

Create a **`.env`** file in the repository root (see **Environment variables** below), then:

```bash
docker compose up --build
```

Open `http://localhost:8080` (nginx). API health: `http://localhost:8080/health`, metrics: `http://localhost:8080/metrics`.

The first registered user becomes **admin** (bootstrap). Promote moderators by updating `users.role` in PostgreSQL (`moderator` or `admin`).

## Common commands

| Task | Command |
|------|---------|
| DB migrations (inside backend container) | `docker compose run --rm backend alembic upgrade head` |
| Celery worker logs | `docker compose logs -f celery` |
| Backend only (local venv) | `cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload` |

## Environment variables

Add **`.env`** at the repo root (never commit secrets). Docker Compose loads it for backend, celery, and frontend. Example skeleton matching local defaults:

```env
# Never commit this file with real secrets.

SECRET_KEY=<random-string-at-least-32-chars>
OPENAI_API_KEY=

# Optional: cap OpenAI usage during development (see README)
# OPENAI_ENFORCE_TOKEN_BUDGETS=true
# OPENAI_MAX_TOKENS_PER_DAY=200000
# OPENAI_MAX_TOKENS_PER_CLAIM_SCOPE=80000

POSTGRES_USER=rmc
POSTGRES_PASSWORD=rmc_dev_password
POSTGRES_DB=rate_my_claim

DATABASE_URL=postgresql+asyncpg://rmc:rmc_dev_password@postgres:5432/rate_my_claim
DATABASE_SYNC_URL=postgresql+psycopg2://rmc:rmc_dev_password@postgres:5432/rate_my_claim

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
PUBLIC_APP_URL=http://localhost:8080
COOKIE_SECURE=false

HTTP_PORT=8080
```

Critical:

- `SECRET_KEY` — JWT signing (min 32 chars).
- `DATABASE_URL` — async SQLAlchemy DSN (`postgresql+asyncpg://…`).
- `OPENAI_API_KEY` — required for embeddings and enrichment.
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — cache and task broker.

### OpenAI token budgets (development safety)

Counts are stored in **Redis** using `total_tokens` from API responses (with rough pre-call estimates to block calls that would obviously exceed caps). Scope keys group usage: `pending:{uuid}` (Celery enrichment), `claim:{uuid}` (moderator “Generate AI analysis” on a claim), `search:{uuid}` (per search request embedding), `approve_pending:{uuid}` (moderation approve embeddings).

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPENAI_ENFORCE_TOKEN_BUDGETS` | `true` | Set `false` to disable all caps. |
| `OPENAI_MAX_TOKENS_PER_DAY` | `200000` | Max **total** OpenAI tokens per **UTC calendar day** (`0` = no daily cap). |
| `OPENAI_MAX_TOKENS_PER_CLAIM_SCOPE` | `80000` | Max tokens per **scope** above (`0` = no per-scope cap). |

If a cap is hit, synchronous API routes return **429** with `OPENAI_TOKEN_BUDGET_EXCEEDED`; Celery enrichment marks the pending row **failed** with an explanatory `error_message`.

1. Claim submitted → `pending_claims` row, Celery task `claims.process_pending`.
2. Embedding stored on pending row; vector similarity finds duplicate **candidates** (never auto-merges).
3. Canonicalization + retrieval from similar claims’ evidence and optional user URLs (HTTP fetch + `trafilatura`).
4. Structured verdict JSON stored in `ai_analysis` (isolated from canonical tables).
5. Moderator approves → `claims` + `evidence` rows with embeddings; pending marked `completed`.

## Testing

```bash
cd backend
pytest
```

By default, **one integration test is skipped** (`RUN_PG_INTEGRATION` not set). Unit tests cover health and Phase 2 repository wiring.

### Phase 2 verification (database + domain)

Per `notebooks/instructions.txt` Phase 2, the relational model and pgvector layer are implemented in Alembic + SQLAlchemy. Use the following to validate locally:

| Check | Command / notes |
|--------|------------------|
| **Migrations apply** | Already run on `backend` container start (`alembic upgrade head`). To re-run: `docker compose run --rm backend alembic upgrade head` |
| **Migrations rollback** (destructive) | `docker compose run --rm backend alembic downgrade base` then `alembic upgrade head` — drops all app tables; use only on disposable volumes |
| **Seed data** | With stack up: `docker compose exec -e SEED_DEVELOPMENT=true backend python scripts/seed_development.py` — creates `seed_admin` / `seed_moderator`, a sample claim with **1536-dim** embeddings, evidence, alias, revision, publisher, audit/system rows. Idempotent if `seed_admin` already exists. Optional password: `SEED_PASSWORD=...` |
| **pgvector query smoke** | `RUN_PG_INTEGRATION=1` and a real `DATABASE_URL` (asyncpg) pointing at your Postgres, then `cd backend && pytest tests/test_phase2_pgvector_integration.py -q` |

**Repositories (Phase 2):** shared `RepositoryBase`; domain access in `ClaimRepository`, `HybridSearchRepository`, `UserRepository`, `AIAnalysisRepository`, `EvidenceRepository`, `GraphRepository` (aliases, revisions, relationships), `PlatformRepository` (publisher, ingestion jobs, reputation, moderation listing), `AuditRepository` (audit logs, system events).

## Troubleshooting

- **Migrations fail on pgvector**: ensure image `pgvector/pgvector:pg16` and extension `CREATE EXTENSION vector` (handled in initial migration).
- **Celery tasks not running**: confirm `celery` service is up and broker URLs match Redis DB indices.
- **401 on moderation**: log in via `POST /api/v1/auth/login` on the same origin so cookies are set.

## License

See `LICENSE`.
