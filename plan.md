# Environment Variables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mixed root `.env` workflow with a clear, safe, application-owned environment variable layout for `apps/web`, `apps/api`, Docker Compose, local development, tests, production, and future CI/CD.

**Architecture:** Split env ownership by runtime boundary. Vite reads only public `VITE_*` values from `apps/web/.env`; FastAPI, Celery worker, and Celery beat read backend runtime values from `apps/api/.env`; Docker Compose interpolation reads dependency-service values from `.env.compose`. Keep production values in deployment-only files and keep all real env files out of Git and image build contexts.

**Tech Stack:** React + Vite in `apps/web`, FastAPI + Pydantic Settings + SQLAlchemy + Alembic + Celery in `apps/api`, PostgreSQL, Redis, Docker Compose, Caddy, pnpm, uv.

---

## Current State

The repository currently uses `apps/web` and `apps/api`, not `frontend` and `backend`.

Tracked files involved:

- `README.md`
- `Makefile`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`
- `.env.example`
- `.gitignore`
- `apps/web/package.json`
- `apps/web/vite.config.ts`
- `apps/web/Dockerfile`
- `apps/web/Dockerfile.prod`
- `apps/web/.dockerignore`
- `apps/web/src/lib/api.ts`
- `apps/api/pyproject.toml`
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py`
- `apps/api/Dockerfile`
- `apps/api/Dockerfile.prod`
- `apps/api/.dockerignore`
- `apps/api/app/core/config.py`
- `apps/api/app/main.py`
- `apps/api/app/db/session.py`
- `apps/api/app/services/ai_service.py`
- `apps/api/app/tasks.py`
- `scripts/deploy.sh`

Real env files currently present but not tracked:

- `.env`
- `apps/api/.env`

Observed variable ownership today:

| Variable | Current reader | Correct owner |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `apps/web/src/lib/api.ts`, `apps/web/Dockerfile.prod`, `docker-compose.prod.yml` | `apps/web/.env*` and Compose build arg |
| `DATABASE_URL` | `apps/api/app/core/config.py`, SQLAlchemy, Alembic, Celery | `apps/api/.env*` |
| `REDIS_URL` | Celery broker/backend | `apps/api/.env*` |
| `DEEPSEEK_API_KEY` | `apps/api/app/services/ai_service.py` | `apps/api/.env*`, secret |
| `DEEPSEEK_BASE_URL` | AI service | `apps/api/.env*` |
| `DEEPSEEK_MODEL` | AI service | `apps/api/.env*` |
| `CORS_ORIGINS` | `apps/api/app/main.py` | `apps/api/.env*` |
| `POSTGRES_DB` | Compose interpolation | `.env.compose*` |
| `POSTGRES_USER` | Compose interpolation | `.env.compose*` |
| `POSTGRES_PASSWORD` | Compose interpolation | `.env.compose*`, secret |
| `POSTGRES_PORT` | Compose interpolation | `.env.compose*` |
| `REDIS_PORT` | Compose interpolation | `.env.compose*` |
| `API_BASE_URL` | Present in real env, no current code reader | Remove as stale |
| `NEXT_PUBLIC_API_BASE_URL` | Present in real env, no current code reader | Remove as stale Next.js migration residue |

Current risks:

- `docker-compose.yml` and `docker-compose.prod.yml` use root `.env` as `env_file` for `api`, `worker`, `beat`, and `web`, which mixes Compose interpolation, backend secrets, and frontend public values.
- `apps/api/.env` contains variables that do not belong to API runtime, including `POSTGRES_*` and stale `NEXT_PUBLIC_*`.
- `apps/api/.dockerignore` does not exclude `.env` or `.env.*`; API Docker builds can copy real secrets into image layers through `COPY . .`.
- `.gitignore` ignores only a subset of real env files and does not cover future files such as `.env.compose`, `.env.production`, `apps/web/.env`, and `apps/api/.env.production`.
- Real env file permissions are currently `0644`; production env files should be `0600`.
- No `.github/workflows` directory exists yet, so CI/CD env handling is not implemented.

Confirmed non-risks:

- Real `.env` files are not currently tracked by Git.
- Git history only shows `.env.example`, not real `.env` files.
- No current frontend code reads `VITE_OPENAI_API_KEY`, `VITE_DATABASE_URL`, `VITE_JWT_SECRET`, `DATABASE_URL`, `DEEPSEEK_API_KEY`, or other backend secrets.

---

## Target File Layout

```bash
rsswise/
  .env.example
  .env.compose
  .env.compose.example

  apps/web/
    .env
    .env.example

  apps/api/
    .env
    .env.example
    .env.test
    .env.test.example
```

Production deployment layout:

```bash
rsswise/
  .env.compose.production
  apps/api/.env.production
  apps/web/.env.production
```

Production may alternatively store backend runtime secrets outside the repo checkout:

```bash
/etc/rsswise/api.env
/etc/rsswise/compose.env
```

If that external layout is used, `docker-compose.prod.yml` must point `env_file` at `/etc/rsswise/api.env` and deployment scripts must pass `--env-file /etc/rsswise/compose.env`.

Worker and beat do not get separate env files yet. They run from the same `apps/api` package and need the same `DATABASE_URL`, `REDIS_URL`, and AI settings. Add `apps/worker/.env.example` only if the worker becomes a separate application directory.

---

## Security Rules

- `apps/web/.env*` may contain only `VITE_*` variables.
- `apps/web/.env*` must never contain database URLs, JWT/session secrets, API provider secret keys, S3 secret keys, SMTP passwords, Stripe secret keys, or Redis credentials.
- `apps/api/.env*` contains backend runtime values only.
- `.env.compose*` contains Compose interpolation values only: dependency service credentials, published ports, Compose project name, and frontend build args.
- Real env files are never committed.
- All committed env files must end in `.example`.
- API Docker build context must exclude `.env` and `.env.*`.
- Production env files must be mode `600`.
- Vite variables are public at build time. Any `VITE_*` value must be treated as visible to users.

---

## Variable Ownership

| Variable | Owner | Sensitive | Frontend allowed | Example | Notes |
| --- | --- | --- | --- | --- | --- |
| `VITE_API_BASE_URL` | web | No | Yes | `/api` | Vite build-time public API base URL |
| `VITE_SENTRY_DSN` | web | No | Yes | `https://public@example.ingest.sentry.io/1` | Future frontend monitoring; public by design |
| `APP_ENV` | api | No | No | `development` | `development`, `test`, or `production` |
| `LOG_LEVEL` | api | No | No | `INFO` | Future replacement for hard-coded logging level |
| `DATABASE_URL` | api | Yes | No | `postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise` | Use `127.0.0.1` for host-run local API; use `postgres` in containers |
| `REDIS_URL` | api | Maybe | No | `redis://127.0.0.1:6379/0` | Celery broker/backend |
| `CORS_ORIGINS` | api | No | No | `http://127.0.0.1:3000,http://localhost:3000` | Comma-separated origins |
| `DEEPSEEK_API_KEY` | api | Yes | No | empty locally | Third-party AI secret |
| `DEEPSEEK_BASE_URL` | api | No | No | `https://api.deepseek.com` | DeepSeek-compatible endpoint |
| `DEEPSEEK_MODEL` | api | No | No | `deepseek-chat` | AI model name |
| `JWT_SECRET` | api | Yes | No | `change-me-in-production` | Future auth |
| `SESSION_SECRET` | api | Yes | No | `change-me-in-production` | Future session/cookie signing |
| `S3_ENDPOINT_URL` | api | No | No | `https://s3.example.com` | Future file storage |
| `S3_BUCKET` | api | No | No | `rsswise-assets` | Future file storage bucket |
| `S3_ACCESS_KEY_ID` | api | Yes | No | `rsswise` | Future file storage credential |
| `S3_SECRET_ACCESS_KEY` | api | Yes | No | `change-me-in-production` | Future file storage secret |
| `SMTP_HOST` | api | No | No | `smtp.example.com` | Future email |
| `SMTP_PORT` | api | No | No | `587` | Future email |
| `SMTP_USER` | api | Maybe | No | `rsswise@example.com` | Future email |
| `SMTP_PASSWORD` | api | Yes | No | `change-me-in-production` | Future email secret |
| `SENTRY_DSN` | api | Low | No | `https://private@example.ingest.sentry.io/1` | Future backend monitoring |
| `POSTGRES_DB` | compose | No | No | `rsswise` | PostgreSQL init database |
| `POSTGRES_USER` | compose | Low | No | `rsswise` | PostgreSQL init user |
| `POSTGRES_PASSWORD` | compose | Yes | No | `rsswise-dev-password` | PostgreSQL init password |
| `POSTGRES_PORT` | compose | No | No | `5432` | Host port for local dependency container |
| `REDIS_PORT` | compose | No | No | `6379` | Host port for local dependency container |
| `COMPOSE_PROJECT_NAME` | compose | No | No | `rsswise` | Optional Docker Compose project name |

---

## Implementation Tasks

### Task 1: Harden Ignore Rules Before Moving Secrets

**Files:**

- Modify: `.gitignore`
- Modify: `apps/api/.dockerignore`
- Modify: `apps/web/.dockerignore`

- [ ] **Step 1: Replace env ignore rules in `.gitignore`**

Change the local env section to this exact block:

```gitignore
# Local env files
.env
.env.*
**/.env
**/.env.*
!.env.example
!.env.compose.example
!**/.env.example
!**/.env.*.example
*.local
```

Keep the rest of `.gitignore` unchanged.

- [ ] **Step 2: Exclude API env files from Docker build context**

Update `apps/api/.dockerignore` to include env exclusions:

```gitignore
__pycache__/
.pytest_cache/
.ruff_cache/
.venv/
*.pyc
.env
.env.*
!.env.example
!.env.*.example
```

- [ ] **Step 3: Tighten web Docker env exclusions**

Update the env section in `apps/web/.dockerignore` to:

```gitignore
.env
.env.*
!.env.example
!.env.*.example
```

Keep existing build-output and dependency exclusions.

- [ ] **Step 4: Verify ignore behavior**

Run:

```bash
git check-ignore .env .env.compose .env.compose.production apps/api/.env apps/api/.env.production apps/web/.env apps/web/.env.production
```

Expected: each path is printed as ignored.

Run:

```bash
git check-ignore .env.example .env.compose.example apps/api/.env.example apps/api/.env.test.example apps/web/.env.example
```

Expected: no output, because example files are allowed.

- [ ] **Step 5: Commit**

```bash
git add .gitignore apps/api/.dockerignore apps/web/.dockerignore
git commit -m "chore(env): prevent env files from entering git and images"
```

**Rollback:** Revert this commit with `git revert <commit-sha>`. Do not remove the ignore hardening unless it blocks a verified workflow.

---

### Task 2: Add Committed Env Templates

**Files:**

- Create: `.env.compose.example`
- Modify: `.env.example`
- Create: `apps/api/.env.example`
- Create: `apps/api/.env.test.example`
- Create: `apps/web/.env.example`

- [ ] **Step 1: Create `.env.compose.example`**

```bash
# Docker Compose interpolation values for local dependency services.
# Copy to .env.compose for local development.

COMPOSE_PROJECT_NAME=rsswise

POSTGRES_DB=rsswise
POSTGRES_USER=rsswise
POSTGRES_PASSWORD=rsswise
POSTGRES_PORT=5432

REDIS_PORT=6379

# Public Vite build arg for production web image builds.
VITE_API_BASE_URL=/api
```

- [ ] **Step 2: Replace root `.env.example` with an index**

```bash
# RSSWise environment templates
#
# Runtime env files are split by owner:
#
# - .env.compose.example -> copy to .env.compose
# - apps/api/.env.example -> copy to apps/api/.env
# - apps/api/.env.test.example -> copy to apps/api/.env.test
# - apps/web/.env.example -> copy to apps/web/.env
#
# Real .env files must never be committed.
```

- [ ] **Step 3: Create `apps/web/.env.example`**

```bash
# Public Vite variables only.
# Every variable in this file is exposed to browser JavaScript.

VITE_API_BASE_URL=/api
```

- [ ] **Step 4: Create `apps/api/.env.example`**

```bash
# Backend runtime variables for host-run local development.
# Copy to apps/api/.env.

APP_ENV=development
LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL=redis://127.0.0.1:6379/0

CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 5: Create `apps/api/.env.test.example`**

```bash
# Backend test variables.
# Copy to apps/api/.env.test when running tests that need explicit test env files.

APP_ENV=test
LOG_LEVEL=WARNING

DATABASE_URL=postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL=redis://127.0.0.1:6379/1

CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 6: Verify templates are tracked and real files are ignored**

Run:

```bash
git status --short
git check-ignore .env.compose apps/api/.env apps/api/.env.test apps/web/.env
```

Expected: new `.example` files appear in `git status`; real env targets are ignored.

- [ ] **Step 7: Commit**

```bash
git add .env.example .env.compose.example apps/api/.env.example apps/api/.env.test.example apps/web/.env.example
git commit -m "chore(env): add split environment templates"
```

**Rollback:** Revert this commit. Existing local `.env` files remain untouched.

---

### Task 3: Make Backend Settings Explicit and Test-Friendly

**Files:**

- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/core/logging.py`
- Test: `apps/api/tests/test_config.py`

- [ ] **Step 1: Add focused config tests**

Create `apps/api/tests/test_config.py`:

```python
from app.core.config import Settings


def test_settings_reads_explicit_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        deepseek_api_key="",
    )

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url == "redis://127.0.0.1:6379/0"


def test_settings_ignores_frontend_and_compose_only_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/rsswise",
        redis_url="redis://127.0.0.1:6379/0",
        VITE_API_BASE_URL="/api",
        POSTGRES_PASSWORD="secret",
        NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000",
    )

    assert not hasattr(settings, "VITE_API_BASE_URL")
    assert not hasattr(settings, "POSTGRES_PASSWORD")
    assert not hasattr(settings, "NEXT_PUBLIC_API_BASE_URL")
```

- [ ] **Step 2: Run the config tests and confirm they fail**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_config.py -v
```

Expected: failure because `Settings` does not define `app_env` or `log_level`.

- [ ] **Step 3: Update `apps/api/app/core/config.py`**

Replace its contents with:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str
    redis_url: str

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

This keeps the current `apps/api/.env` behavior because commands run from `apps/api`.

- [ ] **Step 4: Update `apps/api/app/core/logging.py`**

Replace its contents with:

```python
import logging

import structlog

from app.core.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_config.py -v
cd apps/api && uv run --no-sync pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core/config.py apps/api/app/core/logging.py apps/api/tests/test_config.py
git commit -m "chore(api): document backend runtime settings"
```

**Rollback:** Revert this commit. Backend will return to the existing `DATABASE_URL`, `REDIS_URL`, DeepSeek, and CORS-only settings.

---

### Task 4: Move Local Commands to Split Env Ownership

**Files:**

- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Update Makefile variables**

Replace the top variable block in `Makefile` with:

```make
COMPOSE_DEV := docker compose --env-file .env.compose -f docker-compose.dev.yml
COMPOSE_PROD := docker compose --env-file .env.compose.production -f docker-compose.prod.yml
API_DIR := apps/api
WEB_DIR := apps/web
DEPLOY_SCRIPT := scripts/deploy.sh

SSH_HOST ?= rsswise-prod
SSH_PATH ?= /home/ubuntu/rsswise

API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_HOST ?= 127.0.0.1
```

Remove these lines:

```make
DATABASE_URL ?= postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL ?= redis://127.0.0.1:6379/0
VITE_API_BASE_URL ?= /api
API_ENV := DATABASE_URL="$(DATABASE_URL)" REDIS_URL="$(REDIS_URL)"
WEB_ENV := VITE_API_BASE_URL="$(VITE_API_BASE_URL)"
```

- [ ] **Step 2: Update Makefile command targets**

Change the command targets to:

```make
test:
	cd $(API_DIR) && uv run --no-sync pytest -v

api:
	cd $(API_DIR) && uv run --no-sync uvicorn app.main:app --host $(API_HOST) --port $(API_PORT) --reload

db-migrate:
	cd $(API_DIR) && uv run --no-sync alembic upgrade head

worker:
	cd $(API_DIR) && uv run --no-sync celery -A app.tasks.celery_app worker --loglevel=INFO

beat:
	cd $(API_DIR) && uv run --no-sync celery -A app.tasks.celery_app beat --loglevel=INFO

web:
	cd $(WEB_DIR) && pnpm dev --host $(WEB_HOST)

web-build:
	cd $(WEB_DIR) && pnpm build

check:
	cd $(API_DIR) && uv run --no-sync pytest -v
	cd $(API_DIR) && uv run --no-sync ruff check app tests
	cd $(WEB_DIR) && pnpm build
```

- [ ] **Step 3: Update README local setup**

Replace the local development setup block with:

```markdown
```bash
cp .env.compose.example .env.compose
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env

make install
make dev-up
make db-migrate
```
```

Keep the existing process commands:

```markdown
```bash
make api
make worker
make beat
make web
```
```

Add this note:

```markdown
`make dev-up` reads `.env.compose` and starts only PostgreSQL and Redis.
`make api`, `make worker`, `make beat`, and `make db-migrate` run from `apps/api` and read `apps/api/.env`.
`make web` runs from `apps/web` and reads only public Vite variables from `apps/web/.env`.
```

- [ ] **Step 4: Create local env files from examples**

Run:

```bash
cp .env.compose.example .env.compose
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
chmod 600 .env.compose apps/api/.env apps/web/.env
```

Expected: no output.

- [ ] **Step 5: Verify local dependency startup**

Run:

```bash
make dev-up
docker compose --env-file .env.compose -f docker-compose.dev.yml ps
```

Expected: `postgres` and `redis` are running or healthy.

- [ ] **Step 6: Verify app commands**

Run:

```bash
make db-migrate
make test
make web-build
```

Expected: migrations complete, backend tests pass, frontend build succeeds.

- [ ] **Step 7: Commit**

```bash
git add Makefile README.md
git commit -m "chore(env): load local env files by application"
```

**Rollback:** Revert this commit. Existing local `.env` files remain in place; old Makefile inline defaults return.

---

### Task 5: Separate Docker Compose Interpolation From Runtime Env

**Files:**

- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Keep `docker-compose.dev.yml` dependency-only**

Keep the file dependency-only and continue using Compose interpolation:

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

This file is already close to the target. The main change is operational: always call it through `--env-file .env.compose`.

- [ ] **Step 2: Update `docker-compose.yml` for full-stack local containers**

Replace `env_file: .env` under `api`, `worker`, and `beat` with:

```yaml
env_file:
  - ./apps/api/.env
environment:
  DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-rsswise}:${POSTGRES_PASSWORD:-rsswise}@postgres:5432/${POSTGRES_DB:-rsswise}
  REDIS_URL: redis://redis:6379/0
```

The `env_file` keeps shared API settings such as `APP_ENV`, `LOG_LEVEL`, `CORS_ORIGINS`, and `DEEPSEEK_*`. The explicit `environment` block overrides only container-specific dependency URLs, because `apps/api/.env` is optimized for host-run local development and uses `127.0.0.1`.

Remove `env_file: .env` from `web`. For Vite dev in a container, use:

```yaml
environment:
  VITE_API_BASE_URL: ${VITE_API_BASE_URL:-/api}
```

This keeps backend secrets out of the web container.

- [ ] **Step 3: Update `docker-compose.prod.yml` runtime env files**

Replace `env_file: .env` under `api`, `worker`, and `beat` with:

```yaml
env_file:
  - ./apps/api/.env.production
```

Keep web build args:

```yaml
args:
  VITE_API_BASE_URL: ${VITE_API_BASE_URL:-/api}
```

- [ ] **Step 4: Verify Compose config rendering**

Run:

```bash
docker compose --env-file .env.compose -f docker-compose.dev.yml config
docker compose --env-file .env.compose -f docker-compose.yml config
```

Expected: config renders without missing variable errors.

For production config, create a local dry-run file if needed:

```bash
cp apps/api/.env.example apps/api/.env.production
cp .env.compose.example .env.compose.production
docker compose --env-file .env.compose.production -f docker-compose.prod.yml config
rm -f apps/api/.env.production .env.compose.production
```

Expected: config renders. The copied production files are ignored by Git.

- [ ] **Step 5: Verify web container does not receive backend secrets**

Run:

```bash
docker compose --env-file .env.compose -f docker-compose.yml config | rg -n "web:|DATABASE_URL|DEEPSEEK_API_KEY|POSTGRES_PASSWORD|VITE_API_BASE_URL"
```

Expected: `VITE_API_BASE_URL` may appear under `web`; backend secrets must not appear under `web`.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml docker-compose.prod.yml
git commit -m "chore(env): split compose and runtime env files"
```

**Rollback:** Revert this commit. If production deploy is blocked, restore the previous `env_file: .env` temporarily while keeping `.dockerignore` hardening.

---

### Task 6: Clean Real Local Env Files

**Files:**

- Modify local only: `.env`
- Modify local only: `apps/api/.env`
- Create local only: `.env.compose`
- Create local only: `apps/web/.env`

Do not commit any files from this task.

- [ ] **Step 1: Move Compose values out of root `.env`**

Create `.env.compose` from `.env.compose.example`:

```bash
cp .env.compose.example .env.compose
chmod 600 .env.compose
```

If current `.env` contains customized `POSTGRES_*`, copy only these values into `.env.compose`:

```bash
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_PORT
REDIS_PORT
VITE_API_BASE_URL
```

- [ ] **Step 2: Clean `apps/api/.env`**

Rewrite local `apps/api/.env` so it contains only:

```bash
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
DEEPSEEK_API_KEY=<keep-current-real-value-or-empty>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

When editing the real file, keep the existing `DEEPSEEK_API_KEY` value if it is already valid. Do not paste the secret into commits, logs, screenshots, or chat.

- [ ] **Step 3: Create `apps/web/.env`**

```bash
cp apps/web/.env.example apps/web/.env
chmod 600 apps/web/.env
```

Expected content:

```bash
VITE_API_BASE_URL=/api
```

- [ ] **Step 4: Stop using root `.env` for runtime**

After tasks 4 and 5 pass, archive the root `.env` locally:

```bash
mv .env .env.legacy
chmod 600 .env.legacy
```

Do not commit `.env.legacy`; it is ignored.

- [ ] **Step 5: Verify real env files are ignored**

Run:

```bash
git status --short --ignored -uall | rg '(^!! \.env|apps/api/\.env|apps/web/\.env|\.env\.compose)'
```

Expected: real env files appear as ignored, not staged or tracked.

**Rollback:** Move `.env.legacy` back to `.env` and restore the previous Makefile/Compose commits if local startup fails.

---

### Task 7: Update Production Deploy Workflow

**Files:**

- Modify: `scripts/deploy.sh`
- Modify: `README.md`
- Optional modify: `Caddyfile`

- [ ] **Step 1: Make production Compose command explicit**

The Makefile should already set:

```make
COMPOSE_PROD := docker compose --env-file .env.compose.production -f docker-compose.prod.yml
```

Keep `scripts/deploy.sh` using `COMPOSE_PROD` from the environment. No deploy script change is needed if the Makefile variable is updated.

- [ ] **Step 2: Add production env instructions to README**

Add:

```markdown
## Production Environment

On the server, create deployment-only env files:

```bash
cp .env.compose.example .env.compose.production
cp apps/api/.env.example apps/api/.env.production
chmod 600 .env.compose.production apps/api/.env.production
```

For production containers, `apps/api/.env.production` must use service names:

```bash
DATABASE_URL=postgresql+psycopg://rsswise:<password>@postgres:5432/rsswise
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://rss.huyixi.com
```

`VITE_API_BASE_URL` remains public and is read from `.env.compose.production` as a web image build arg.
Changing `VITE_API_BASE_URL` requires rebuilding the web image.
```

- [ ] **Step 3: Verify deployment command locally without deploying**

Run:

```bash
make -n deploy
```

Expected: output shows `COMPOSE_PROD="docker compose --env-file .env.compose.production -f docker-compose.prod.yml"` passed to `scripts/deploy.sh`.

- [ ] **Step 4: Verify production Compose config on the server**

Run on the server:

```bash
cd /home/ubuntu/rsswise
docker compose --env-file .env.compose.production -f docker-compose.prod.yml config
```

Expected: config renders and `api`, `worker`, and `beat` use `apps/api/.env.production`.

- [ ] **Step 5: Commit**

```bash
git add Makefile README.md scripts/deploy.sh Caddyfile
git commit -m "docs(env): document production env workflow"
```

If `scripts/deploy.sh` and `Caddyfile` were not changed, omit them from `git add`.

**Rollback:** Revert the README/Makefile deploy-doc commit and run the old production command manually.

---

### Task 8: Add CI/CD Env Guardrails

**Files:**

- Create: `.github/workflows/check.yml`

- [ ] **Step 1: Create CI workflow directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create `.github/workflows/check.yml`**

```yaml
name: check

on:
  pull_request:
  push:
    branches:
      - main

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: rsswise
          POSTGRES_USER: rsswise
          POSTGRES_PASSWORD: rsswise
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U rsswise -d rsswise"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    defaults:
      run:
        working-directory: apps/api
    env:
      APP_ENV: test
      LOG_LEVEL: WARNING
      DATABASE_URL: postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
      REDIS_URL: redis://127.0.0.1:6379/1
      CORS_ORIGINS: http://127.0.0.1:3000,http://localhost:3000
      DEEPSEEK_API_KEY: ""
      DEEPSEEK_BASE_URL: https://api.deepseek.com
      DEEPSEEK_MODEL: deepseek-chat
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: uv venv
      - run: uv pip install -e ".[dev]"
      - run: uv run --no-sync pytest -v
      - run: uv run --no-sync ruff check app tests

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    env:
      VITE_API_BASE_URL: /api
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 11.3.0
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: pnpm
          cache-dependency-path: apps/web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
```

- [ ] **Step 3: Validate workflow syntax locally if `actionlint` is available**

Run:

```bash
actionlint .github/workflows/check.yml
```

Expected: no output.

If `actionlint` is unavailable, run:

```bash
git diff --check .github/workflows/check.yml
```

Expected: no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/check.yml
git commit -m "ci: add split frontend and backend checks"
```

**Rollback:** Revert this commit. Local env workflow remains unaffected.

---

### Task 9: Add Secret Leak Checks

**Files:**

- Create: `scripts/check-env-safety.sh`
- Modify: `Makefile`

- [ ] **Step 1: Create `scripts/check-env-safety.sh`**

```sh
#!/bin/sh
set -eu

tracked_env_files=$(git ls-files | grep -E '(^|/)\.env($|\.)' | grep -vE '(\.example|\.env\.compose\.example)$' || true)
if [ -n "$tracked_env_files" ]; then
	echo "Tracked real env files found:" >&2
	echo "$tracked_env_files" >&2
	exit 1
fi

frontend_secret_refs=$(rg -n 'VITE_.*(SECRET|TOKEN|PASSWORD|DATABASE|JWT|OPENAI|DEEPSEEK|STRIPE|S3)' apps/web .env.example .env.compose.example apps/web/.env.example || true)
if [ -n "$frontend_secret_refs" ]; then
	echo "Dangerous frontend env names found:" >&2
	echo "$frontend_secret_refs" >&2
	exit 1
fi

web_bundle_secret_refs=""
if [ -d apps/web/dist ]; then
	web_bundle_secret_refs=$(rg -n 'DEEPSEEK_API_KEY|DATABASE_URL|POSTGRES_PASSWORD|JWT_SECRET|SESSION_SECRET|S3_SECRET_ACCESS_KEY|STRIPE_SECRET_KEY|OPENAI_API_KEY' apps/web/dist || true)
fi

if [ -n "$web_bundle_secret_refs" ]; then
	echo "Sensitive names found in web bundle:" >&2
	echo "$web_bundle_secret_refs" >&2
	exit 1
fi

echo "env safety checks passed"
```

- [ ] **Step 2: Make the script executable**

Run:

```bash
chmod +x scripts/check-env-safety.sh
```

- [ ] **Step 3: Add a Makefile target**

Add `env-check` to `.PHONY`:

```make
.PHONY: help install dev-up dev-down dev-logs dev-reset deploy-check deploy api worker beat test web web-build check db-migrate env-check
```

Add target:

```make
env-check:
	./scripts/check-env-safety.sh
```

Update `check` to include:

```make
	./scripts/check-env-safety.sh
```

Place it after frontend build so bundle scanning can inspect `apps/web/dist`.

- [ ] **Step 4: Run safety checks**

Run:

```bash
make env-check
make check
```

Expected: `env safety checks passed`; backend tests, ruff, and frontend build pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile scripts/check-env-safety.sh
git commit -m "chore(env): add env safety checks"
```

**Rollback:** Revert this commit. The split env structure remains intact.

---

## Local Development Flow After Migration

First-time setup:

```bash
cp .env.compose.example .env.compose
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
chmod 600 .env.compose apps/api/.env apps/web/.env

make install
make dev-up
make db-migrate
```

Run the app:

```bash
make api
make worker
make beat
make web
```

Open:

- Web: `http://127.0.0.1:3000`
- API health: `http://127.0.0.1:8000/health`

The local backend runs on the host and uses:

```bash
DATABASE_URL=postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL=redis://127.0.0.1:6379/0
```

Containerized production backend uses service names:

```bash
DATABASE_URL=postgresql+psycopg://rsswise:<password>@postgres:5432/rsswise
REDIS_URL=redis://redis:6379/0
```

---

## Production Flow After Migration

On the server:

```bash
cd /home/ubuntu/rsswise
cp .env.compose.example .env.compose.production
cp apps/api/.env.example apps/api/.env.production
chmod 600 .env.compose.production apps/api/.env.production
```

Edit `.env.compose.production`:

```bash
COMPOSE_PROJECT_NAME=rsswise
POSTGRES_DB=rsswise
POSTGRES_USER=rsswise
POSTGRES_PASSWORD=<strong-production-password>
VITE_API_BASE_URL=/api
```

Edit `apps/api/.env.production`:

```bash
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://rsswise:<strong-production-password>@postgres:5432/rsswise
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://rss.huyixi.com
DEEPSEEK_API_KEY=<real-secret>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Deploy:

```bash
make deploy
```

Manual equivalent:

```bash
docker compose --env-file .env.compose.production -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose --env-file .env.compose.production -f docker-compose.prod.yml exec -T api uv run --no-sync alembic upgrade head
```

---

## Validation Checklist

Run before considering the migration complete:

```bash
git ls-files | rg '(^|/)\.env($|\.)'
```

Expected: only example env files are listed.

```bash
git check-ignore .env .env.compose .env.compose.production apps/api/.env apps/api/.env.production apps/web/.env apps/web/.env.production
```

Expected: every real env path is ignored.

```bash
rg -n 'VITE_.*(SECRET|TOKEN|PASSWORD|DATABASE|JWT|OPENAI|DEEPSEEK|STRIPE|S3)' apps/web .env.example .env.compose.example apps/web/.env.example
```

Expected: no output.

```bash
docker compose --env-file .env.compose -f docker-compose.dev.yml config
docker compose --env-file .env.compose -f docker-compose.yml config
```

Expected: config renders.

```bash
cd apps/api && uv run --no-sync pytest -v
cd apps/api && uv run --no-sync ruff check app tests
cd apps/web && pnpm build
./scripts/check-env-safety.sh
```

Expected: all commands pass.

Production server:

```bash
stat -c '%a %n' .env.compose.production apps/api/.env.production
```

Expected:

```text
600 .env.compose.production
600 apps/api/.env.production
```

macOS equivalent:

```bash
stat -f '%Lp %N' .env.compose.production apps/api/.env.production
```

Expected:

```text
600 .env.compose.production
600 apps/api/.env.production
```

---

## Historical Secret Leak Response

If a real secret is ever committed:

1. Immediately rotate the leaked secret at the provider. Do this before rewriting Git history.
2. Remove the secret from the current tree.
3. Use `git filter-repo` or BFG to purge the secret from history.
4. Force-push rewritten branches only after coordinating with every developer using the repo.
5. Rebuild and redeploy images that may contain the secret.
6. Invalidate any tokens, sessions, or database passwords related to the leak.

Do not rely on deleting a commit or editing `.gitignore`; a committed secret must be treated as compromised.

---

## Risks and Rollback

Risk: local host-run API accidentally uses container hostnames.

- Symptom: connection failure to `postgres` or `redis` from host-run `make api`.
- Fix: `apps/api/.env` must use `127.0.0.1`.
- Rollback: restore old Makefile inline `DATABASE_URL` and `REDIS_URL`.

Risk: production container accidentally uses host addresses.

- Symptom: API container cannot connect to `127.0.0.1:5432`.
- Fix: `apps/api/.env.production` must use `postgres` and `redis` service names.
- Rollback: edit production env file and restart `api`, `worker`, and `beat`.

Risk: frontend API URL change does not take effect.

- Cause: `VITE_API_BASE_URL` is build-time, not runtime.
- Fix: rebuild the web image with the corrected `.env.compose.production`.
- Rollback: restore previous `.env.compose.production` value and rebuild web.

Risk: Docker Compose fails because `.env.compose` is missing.

- Fix: `cp .env.compose.example .env.compose`.
- Rollback: temporarily run `docker compose -f docker-compose.dev.yml ...` without `--env-file` only for local defaults.

Risk: CI build cannot access dependencies.

- Fix: verify GitHub Actions service containers and package-manager setup.
- Rollback: disable CI workflow by reverting the `.github/workflows/check.yml` commit.

Recommended commit order:

1. `chore(env): prevent env files from entering git and images`
2. `chore(env): add split environment templates`
3. `chore(api): document backend runtime settings`
4. `chore(env): load local env files by application`
5. `chore(env): split compose and runtime env files`
6. `docs(env): document production env workflow`
7. `ci: add split frontend and backend checks`
8. `chore(env): add env safety checks`
