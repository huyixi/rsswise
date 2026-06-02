# Local Development Infra Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split local development so Docker Compose runs only PostgreSQL and Redis while application processes run on the local machine.

**Architecture:** Add a dedicated dependency-only Compose file for local development. Move day-to-day development commands to Makefile targets that run API, worker, beat, web, tests, and build checks locally with explicit local service URLs.

**Tech Stack:** Docker Compose, PostgreSQL 16, Redis 7, FastAPI, Celery, uv, pytest, ruff, Next.js, pnpm.

---

## Task 1: Add Dependency-Only Compose File

**Files:**

- Create: `docker-compose.dev.yml`

- [ ] **Step 1: Verify the target file is absent**

Run:

```bash
test -f docker-compose.dev.yml
```

Expected: command exits with status 1 before implementation.

- [ ] **Step 2: Create `docker-compose.dev.yml`**

Add PostgreSQL and Redis only:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-rsswise}
      POSTGRES_USER: ${POSTGRES_USER:-rsswise}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-rsswise}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-rsswise} -d ${POSTGRES_DB:-rsswise}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_dev_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_dev_data:
  redis_dev_data:
```

- [ ] **Step 3: Validate the Compose config**

Run:

```bash
docker compose -f docker-compose.dev.yml config --services
```

Expected output contains exactly:

```text
postgres
redis
```

## Task 2: Replace Makefile With Local Development Commands

**Files:**

- Modify: `Makefile`

- [ ] **Step 1: Verify new targets are absent before implementation**

Run:

```bash
make -n dev-up
```

Expected: `No rule to make target 'dev-up'`.

- [ ] **Step 2: Add local development variables**

Use `?=` defaults so shell environment variables can override local addresses:

```makefile
COMPOSE_DEV := docker compose -f docker-compose.dev.yml
API_DIR := apps/api
WEB_DIR := apps/web

DATABASE_URL ?= postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL ?= redis://127.0.0.1:6379/0
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_HOST ?= 127.0.0.1
NEXT_PUBLIC_API_BASE_URL ?= http://127.0.0.1:8000

API_ENV := DATABASE_URL="$(DATABASE_URL)" REDIS_URL="$(REDIS_URL)"
WEB_ENV := NEXT_PUBLIC_API_BASE_URL="$(NEXT_PUBLIC_API_BASE_URL)"
```

- [ ] **Step 3: Add the help surface**

`make help` must print:

```text
Local development commands:
  make install      Install backend and frontend dependencies
  make dev-up       Start PostgreSQL and Redis
  make dev-down     Stop local dependencies
  make dev-logs     Show dependency logs
  make dev-reset    Reset local dependency data
  make api          Run backend API locally
  make worker       Run Celery worker locally
  make beat         Run Celery beat locally
  make db-migrate   Run database migrations locally
  make test         Run backend tests
  make web          Run frontend locally
  make web-build    Build frontend
  make check        Run test/build checks
```

- [ ] **Step 4: Add dependency service commands**

Implement:

```makefile
dev-up:
	$(COMPOSE_DEV) up -d postgres redis

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f

dev-reset:
	$(COMPOSE_DEV) down -v
```

- [ ] **Step 5: Add local backend commands**

Implement:

```makefile
install:
	cd $(API_DIR) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB_DIR) && pnpm install

test:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync pytest -v

api:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync uvicorn app.main:app --host $(API_HOST) --port $(API_PORT) --reload

db-migrate:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync alembic upgrade head

worker:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync celery -A app.tasks.celery_app worker --loglevel=INFO

beat:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync celery -A app.tasks.celery_app beat --loglevel=INFO
```

- [ ] **Step 6: Add local frontend and aggregate checks**

Implement:

```makefile
web:
	cd $(WEB_DIR) && $(WEB_ENV) pnpm dev --hostname $(WEB_HOST)

web-build:
	cd $(WEB_DIR) && $(WEB_ENV) pnpm build

check:
	cd $(API_DIR) && $(API_ENV) uv run --no-sync pytest -v
	cd $(API_DIR) && $(API_ENV) uv run --no-sync ruff check app tests
	cd $(WEB_DIR) && $(WEB_ENV) pnpm build
```

- [ ] **Step 7: Dry-run Makefile targets**

Run:

```bash
make -n dev-up
make -n api
make -n worker
make -n beat
make -n test
make -n web
make -n web-build
make -n check
```

Expected: each command prints the intended local command without trying to build application containers.

## Task 3: Document the New Workflow

**Files:**

- Create: `docs/local-dev/design.md`
- Create: `docs/local-dev/plan.md`
- Modify: `README.md`

- [ ] **Step 1: Write the design document**

Create `docs/local-dev/design.md` with:

- Summary of dependency-only Compose plus local app processes.
- Current state of existing Compose files.
- Target command surface.
- Local environment defaults.
- Explicit out-of-scope list for object storage, independent MQ, CLI/codegen, and production deployment.
- Acceptance criteria.

- [ ] **Step 2: Write this implementation plan**

Create `docs/local-dev/plan.md` with the exact implementation tasks and verification commands.

- [ ] **Step 3: Update README local run instructions**

Replace the default local run section with:

```bash
make install
make dev-up
make db-migrate
make api
make worker
make beat
make web
```

Also document:

- API health URL: `http://127.0.0.1:8000/health`
- Web URL: `http://127.0.0.1:3000`
- Full-stack Docker Compose remains available through `docker compose up`.

## Task 4: Verify

**Files:**

- Inspect: `docker-compose.yml`
- Inspect: `docker-compose.prod.yml`

- [ ] **Step 1: Verify dependency services only**

Run:

```bash
docker compose -f docker-compose.dev.yml config --services
```

Expected:

```text
postgres
redis
```

- [ ] **Step 2: Verify Makefile command shape**

Run:

```bash
make help
make -n check
```

Expected:

- `make help` prints the local development command list.
- `make -n check` includes `uv run --no-sync pytest -v`, `uv run --no-sync ruff check app tests`, and `pnpm build`.

- [ ] **Step 3: Run local checks if dependencies are installed**

Run:

```bash
make test
make web-build
```

Expected:

- Backend tests pass.
- Frontend build passes.

If local dependencies are missing, run `make install` first or report the missing dependency as a verification blocker.

- [ ] **Step 4: Verify production Compose was not modified**

Run:

```bash
git diff -- docker-compose.yml docker-compose.prod.yml
```

Expected: no diff.
