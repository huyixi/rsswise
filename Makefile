.PHONY: help install dev-up dev-down dev-logs dev-reset deploy-check deploy api worker beat test web web-build check db-migrate env-check epub-test hooks-install hooks-run-pre-commit hooks-run-pre-push

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

help:
	@echo "Local development commands:"
	@echo "  make install      Install backend and frontend dependencies"
	@echo "  make dev-up       Start PostgreSQL and Redis"
	@echo "  make dev-down     Stop local dependencies"
	@echo "  make dev-logs     Show dependency logs"
	@echo "  make dev-reset    Reset local dependency data"
	@echo "  make api          Run backend API locally"
	@echo "  make worker       Run Celery worker locally"
	@echo "  make beat         Run Celery beat locally"
	@echo "  make db-migrate   Run database migrations locally"
	@echo "  make test         Run backend tests"
	@echo "  make web          Run frontend locally"
	@echo "  make web-build    Build frontend"
	@echo "  make env-check    Check env safety rules"
	@echo "  make check        Run local checks (tests + build)"
	@echo "  make hooks-install          Install Lefthook Git hooks"
	@echo "  make hooks-run-pre-commit  Run pre-commit hook manually"
	@echo "  make hooks-run-pre-push    Run pre-push hook manually"
	@echo "  make epub-test    Generate test EPUB from DB (no email)"
	@echo ""
	@echo "Deploy commands:"
	@echo "  make deploy-check Run full checks before deploy"
	@echo "  make deploy       Fast deploy to server"

install:
	cd $(API_DIR) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB_DIR) && pnpm install
	pnpm install
	pnpm exec lefthook install

deploy-check: check

deploy:
	SSH_HOST="$(SSH_HOST)" SSH_PATH="$(SSH_PATH)" COMPOSE_PROD="$(COMPOSE_PROD)" $(DEPLOY_SCRIPT)

dev-up:
	$(COMPOSE_DEV) up -d postgres redis

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f

dev-reset:
	$(COMPOSE_DEV) down -v

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

env-check:
	./scripts/check-env-safety.sh

hooks-install:
	pnpm install
	pnpm exec lefthook install

hooks-run-pre-commit:
	pnpm exec lefthook run pre-commit

hooks-run-pre-push:
	pnpm exec lefthook run pre-push

epub-test:
	cd $(API_DIR) && uv run --no-sync python scripts/generate_test_epub.py

check:
	cd $(API_DIR) && uv run --no-sync pytest -v
	cd $(API_DIR) && uv run --no-sync ruff check app tests
	cd $(WEB_DIR) && pnpm build
	./scripts/check-env-safety.sh
