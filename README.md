# rsswise

AI-assisted RSS reader MVP aligned to `docs/design.md`.

## Stack

- Frontend: Next.js, TypeScript, Tailwind CSS, cossui, react-markdown, remark-gfm, rehype-sanitize
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, structlog
- Database: PostgreSQL
- Worker: Celery, Celery Beat, Redis
- RSS / Extraction: feedparser, trafilatura
- AI: DeepSeek API
- Deploy: Docker Compose

## Local Run

```bash
cp .env.example .env
docker compose build
docker compose up
```

Open:

- Web: `http://127.0.0.1:3000`
- API health: `http://127.0.0.1:8000/health`

## Checks

```bash
cd apps/api && pytest && ruff check app tests
cd apps/web && pnpm build && pnpm test:e2e
```
