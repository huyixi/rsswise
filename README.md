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
cp .env.compose.example .env.compose
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
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

`make dev-up` reads `.env.compose` and starts only PostgreSQL and Redis through `docker-compose.dev.yml`.
`make api`, `make worker`, `make beat`, and `make db-migrate` run from `apps/api` and read `apps/api/.env`.
`make web` runs from `apps/web` and reads only public Vite variables from `apps/web/.env`.
The existing full-stack Docker Compose workflow is still available with `docker compose --env-file .env.compose up`.

## Checks

```bash
make check
```

## Production Environment

On the server, create deployment-only env files:

```bash
cp .env.compose.example .env.compose.production
cp apps/api/.env.example apps/api/.env.production
chmod 600 .env.compose.production apps/api/.env.production
```

For production containers, `apps/api/.env.production` must use Compose service names:

```bash
DATABASE_URL=postgresql+psycopg://rsswise:<password>@postgres:5432/rsswise
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://rss.huyixi.com
```

`VITE_API_BASE_URL` is public and is read from `.env.compose.production` as a web image build arg. Changing it requires rebuilding the web image.

### Email Digest

Email digests are configured in the web settings dialog, including recipient, enabled state, send interval in days, and send time. The backend sends mail through SMTP values from `apps/api/.env` or `apps/api/.env.production`:

```text
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=rsswise@example.com
SMTP_PASSWORD=change-me
SMTP_FROM_EMAIL=rsswise@example.com
SMTP_FROM_NAME=RSSWise
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

The digest send interval and send time are stored in the database. Send time is interpreted as `Asia/Shanghai`.
