.PHONY: up down build logs test test-e2e clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

api-logs:
	docker compose logs -f api

worker-logs:
	docker compose logs -f worker

web-logs:
	docker compose logs -f web

restart-api:
	docker compose restart api

restart-worker:
	docker compose restart worker

test:
	docker compose run --rm api pytest -v

test-e2e:
	cd apps/web && pnpm test:e2e

db-migrate:
	docker compose run --rm api alembic upgrade head

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U rsswise -d rsswise

clean:
	docker compose down -v --rmi local
