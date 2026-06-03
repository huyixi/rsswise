# rsswise

AI-assisted RSS reader MVP aligned to `docs/design.md`.

## Stack

- Frontend: Next.js, TypeScript, Tailwind CSS, cossui, react-markdown, remark-gfm, rehype-sanitize
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, structlog
- Database: PostgreSQL
- Worker: Celery, Celery Beat, Redis
- RSS / Extraction: feedparser, trafilatura
- AI: DeepSeek API
- Deploy: Docker Compose behind host Caddy

## Local Development

```bash
cp .env.example .env
make install
make dev-up
make db-migrate
```

Run the local application processes in separate terminals:

```bash
make api
make worker
make beat
make web
```

Open:

- Web: `http://127.0.0.1:3000`
- API health: `http://127.0.0.1:8000/health`

`make dev-up` starts only PostgreSQL and Redis through `docker-compose.dev.yml`.
The existing full-stack Docker Compose workflow is still available with `docker compose up`.

## Checks

```bash
make check
```
