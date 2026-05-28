# AI RSS Reader MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP in `docs/design.md`: an RSS reader that fetches feeds, permanently stores articles, extracts markdown body content, runs DeepSeek-based reading advice, and exposes article list, article detail, and feed management pages.

**Architecture:** Use the exact stack from `docs/design.md`: a Next.js frontend, a FastAPI backend, PostgreSQL persistence, and Celery workers backed by Redis. Keep the product pipeline explicit: Feed fetch creates Article rows, Article extraction writes `ArticleContent.content_markdown`, AI analysis writes one `ArticleAIAnalysis` row, and reanalysis uses the existing markdown without refetching RSS or re-extracting content.

**Tech Stack:** Frontend: Next.js, TypeScript, Tailwind CSS, cossui, `react-markdown`, `remark-gfm`, `rehype-sanitize`. Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, structlog. Database: PostgreSQL. Worker: Celery, Celery Beat, Redis. RSS / Extraction: feedparser, trafilatura. AI: DeepSeek API. Deploy: Docker Compose.

---

## Alignment Rules From `docs/design.md`

- RSS reader first; AI is only a pre-reading assistance layer.
- Do not add feed enable/disable, custom fetch frequency, user-facing fetch failure reasons, search, AI score, feed filter, recommendation filter, favorites, read-later, reading progress, last-read time, target readers, keyword filtering, or long AI summaries.
- Save article markdown as the internal body standard. Do not persist raw HTML.
- Reanalysis must use current markdown and overwrite the existing AI analysis row. It must not refetch RSS or re-extract article content.
- Feed refresh frequency is fixed at one hour through Celery Beat.
- Recommendation enum is exactly `deep_read`, `skim`, `skip`; frontend labels are exactly `值得精读`, `适合略读`, `可以跳过`.

## File Structure

- `docker-compose.yml`: local PostgreSQL, Redis, API, worker, beat, and web services.
- `.env.example`: shared local environment variables for the compose stack.
- `apps/api/pyproject.toml`: FastAPI backend dependencies and test tools.
- `apps/api/alembic/**`: database migration setup.
- `apps/api/app/core/config.py`: Pydantic settings.
- `apps/api/app/core/logging.py`: structlog setup.
- `apps/api/app/db/session.py`: SQLAlchemy engine and session factory.
- `apps/api/app/models.py`: SQLAlchemy models matching section 6 of `docs/design.md`.
- `apps/api/app/schemas.py`: Pydantic request and response schemas.
- `apps/api/app/services/feed_service.py`: feed add/delete/list/refresh and dedupe logic.
- `apps/api/app/services/extraction_service.py`: trafilatura extraction to markdown.
- `apps/api/app/services/ai_service.py`: DeepSeek call and strict output validation.
- `apps/api/app/tasks.py`: Celery tasks for feed refresh, article extraction, and AI analysis.
- `apps/api/app/beat.py`: fixed hourly Celery Beat schedule.
- `apps/api/app/routers/feeds.py`: feed management API.
- `apps/api/app/routers/articles.py`: article list/detail/read-state/reanalysis API.
- `apps/api/app/main.py`: FastAPI app entrypoint.
- `apps/api/tests/**`: backend unit and integration tests.
- `apps/web/package.json`: Next.js frontend dependencies.
- `apps/web/app/**`: App Router pages.
- `apps/web/components/**`: cossui-based UI components and markdown renderer.
- `apps/web/lib/api.ts`: typed API client for FastAPI.
- `apps/web/tests/e2e/**`: Playwright smoke tests.

---

## Task 1: Scaffold the Aligned Monorepo and Compose Stack

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/Dockerfile`
- Create: `apps/web/package.json`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next.config.mjs`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/postcss.config.mjs`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/app/globals.css`

- [ ] **Step 1: Add shared environment defaults**

Create `.env.example`:

```bash
POSTGRES_DB=rsswise
POSTGRES_USER=rsswise
POSTGRES_PASSWORD=rsswise
DATABASE_URL=postgresql+psycopg://rsswise:rsswise@postgres:5432/rsswise
REDIS_URL=redis://redis:6379/0
API_BASE_URL=http://api:8000
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 2: Add Docker Compose services**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-rsswise}
      POSTGRES_USER: ${POSTGRES_USER:-rsswise}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-rsswise}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    build:
      context: ./apps/api
    env_file: .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./apps/api:/app
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: ./apps/api
    env_file: .env
    command: celery -A app.tasks.celery_app worker --loglevel=INFO
    volumes:
      - ./apps/api:/app
    depends_on:
      - api
      - redis

  beat:
    build:
      context: ./apps/api
    env_file: .env
    command: celery -A app.tasks.celery_app beat --loglevel=INFO
    volumes:
      - ./apps/api:/app
    depends_on:
      - worker
      - redis

  web:
    build:
      context: ./apps/web
    env_file: .env
    command: pnpm dev --hostname 0.0.0.0
    volumes:
      - ./apps/web:/app
      - web_node_modules:/app/node_modules
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
  web_node_modules:
```

- [ ] **Step 3: Add FastAPI project metadata**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "rsswise-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13",
  "celery[redis]>=5.4",
  "fastapi>=0.115",
  "feedparser>=6.0",
  "openai>=1.0",
  "psycopg[binary]>=3.2",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "python-dotenv>=1.0",
  "redis>=5.0",
  "sqlalchemy>=2.0",
  "structlog>=24.0",
  "trafilatura>=1.12",
  "uvicorn[standard]>=0.30"
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27",
  "pytest>=8.0",
  "pytest-mock>=3.14",
  "ruff>=0.6"
]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 4: Add API Dockerfile**

Create `apps/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]"

COPY . .
```

- [ ] **Step 5: Add Next.js frontend package**

Create `apps/web/package.json`:

```json
{
  "name": "rsswise-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "next": "latest",
    "react": "latest",
    "react-dom": "latest",
    "react-markdown": "latest",
    "rehype-sanitize": "latest",
    "remark-gfm": "latest"
  },
  "devDependencies": {
    "@playwright/test": "latest",
    "@types/node": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "autoprefixer": "latest",
    "eslint": "latest",
    "eslint-config-next": "latest",
    "postcss": "latest",
    "tailwindcss": "latest",
    "typescript": "latest"
  }
}
```

Install and initialize cossui components inside `apps/web`:

```bash
pnpm install
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add @coss/button @coss/badge @coss/tabs @coss/input @coss/table
```

- [ ] **Step 6: Add frontend shell**

Create `apps/web/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "RSSWise",
  description: "AI RSS Reader"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="border-b bg-white">
          <nav className="mx-auto flex max-w-5xl gap-4 px-4 py-3">
            <Link href="/articles" className="font-semibold">RSSWise</Link>
            <Link href="/articles">文章</Link>
            <Link href="/feeds">Feed</Link>
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
```

Create `apps/web/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/articles");
}
```

- [ ] **Step 7: Verify scaffold**

Run:

```bash
cp .env.example .env
docker compose build
docker compose up postgres redis
```

Expected: PostgreSQL and Redis start successfully.

- [ ] **Step 8: Commit**

```bash
git add .env.example docker-compose.yml apps/api apps/web
git commit -m "chore: scaffold aligned rsswise stack"
```

---

## Task 2: Implement Backend Configuration, Logging, Models, and Migration

**Files:**
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/app/core/logging.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/models.py`
- Create: `apps/api/app/schemas.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/0001_initial.py`
- Create: `apps/api/tests/test_models.py`

- [ ] **Step 1: Write database model test**

Create `apps/api/tests/test_models.py`:

```python
from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed


def test_models_match_design_entities():
    assert Feed.__tablename__ == "feeds"
    assert Article.__tablename__ == "articles"
    assert ArticleContent.__tablename__ == "article_contents"
    assert ArticleAIAnalysis.__tablename__ == "article_ai_analyses"
```

- [ ] **Step 2: Add configuration and logging**

Create `apps/api/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

Create `apps/api/app/core/logging.py`:

```python
import logging
import structlog


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 3: Add SQLAlchemy models aligned to `docs/design.md`**

Create `apps/api/app/models.py`:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


class ReadingRecommendation(str, enum.Enum):
    deep_read = "deep_read"
    skim = "skim"
    skip = "skip"


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000), unique=True, index=True)
    site_url: Mapped[str | None] = mapped_column(String(2000))
    favicon_url: Mapped[str | None] = mapped_column(String(2000))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="feed", cascade="all, delete")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_articles_url"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    feed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(2000), index=True)
    author: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    summary_from_feed: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(2000))
    guid: Mapped[str | None] = mapped_column(String(2000), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    feed: Mapped[Feed] = relationship(back_populates="articles")
    content: Mapped["ArticleContent"] = relationship(back_populates="article", cascade="all, delete")
    ai_analysis: Mapped["ArticleAIAnalysis"] = relationship(back_populates="article", cascade="all, delete")


class ArticleContent(Base):
    __tablename__ = "article_contents"

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(Enum(ExtractionStatus), default=ExtractionStatus.pending)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    article: Mapped[Article] = relationship(back_populates="content")


class ArticleAIAnalysis(Base):
    __tablename__ = "article_ai_analyses"

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    one_sentence_summary: Mapped[str | None] = mapped_column(String(200))
    reading_recommendation: Mapped[ReadingRecommendation | None] = mapped_column(Enum(ReadingRecommendation))
    reading_reason: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), default=AnalysisStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    article: Mapped[Article] = relationship(back_populates="ai_analysis")
```

- [ ] **Step 4: Add database session and app entrypoint**

Create `apps/api/app/db/session.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI

from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="RSSWise API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Add initial Alembic migration**

Create `apps/api/alembic/env.py` with `target_metadata = Base.metadata` from `app.models`, and create `apps/api/alembic/versions/0001_initial.py` that creates `feeds`, `articles`, `article_contents`, and `article_ai_analyses` with the columns defined in Step 3.

- [ ] **Step 6: Run backend checks**

Run:

```bash
cd apps/api
pytest tests/test_models.py
alembic upgrade head
```

Expected: model test passes and the migration applies to PostgreSQL.

- [ ] **Step 7: Commit**

```bash
git add apps/api
git commit -m "feat: add aligned backend data model"
```

---

## Task 3: Implement Feed Management and RSS Ingestion

**Files:**
- Create: `apps/api/app/services/feed_service.py`
- Create: `apps/api/app/routers/feeds.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_feed_service.py`

- [ ] **Step 1: Write feed service tests**

Create `apps/api/tests/test_feed_service.py`:

```python
from app.services.feed_service import parse_feed_items


def test_parse_feed_items_keeps_design_fields():
    parsed = parse_feed_items(
        """
        <rss version="2.0"><channel>
          <title>Example Feed</title>
          <link>https://example.com</link>
          <item>
            <guid>post-1</guid>
            <title>First Post</title>
            <link>https://example.com/post-1</link>
            <author>Ada</author>
            <pubDate>Wed, 01 Jan 2026 00:00:00 GMT</pubDate>
            <description>Summary</description>
          </item>
        </channel></rss>
        """
    )

    assert parsed.feed_title == "Example Feed"
    assert parsed.site_url == "https://example.com"
    assert parsed.items[0].title == "First Post"
    assert parsed.items[0].guid == "post-1"
    assert parsed.items[0].summary_from_feed == "Summary"
```

- [ ] **Step 2: Implement RSS parsing and dedupe inputs**

Create `apps/api/app/services/feed_service.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from urllib.request import Request, urlopen
from uuid import UUID

import feedparser
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIAnalysis, ArticleContent, Feed


@dataclass(frozen=True)
class ParsedFeedItem:
    title: str
    url: str
    author: str | None
    published_at: datetime | None
    summary_from_feed: str | None
    cover_image_url: str | None
    guid: str | None


@dataclass(frozen=True)
class ParsedFeed:
    feed_title: str
    site_url: str | None
    items: list[ParsedFeedItem]


def parse_feed_items(xml: str) -> ParsedFeed:
    feed = feedparser.parse(xml)
    items: list[ParsedFeedItem] = []

    for entry in feed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            continue

        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime(*entry.published_parsed[:6])

        media = getattr(entry, "media_content", []) or getattr(entry, "media_thumbnail", [])
        cover_image_url = media[0].get("url") if media else None

        items.append(
            ParsedFeedItem(
                title=title,
                url=url,
                author=getattr(entry, "author", None),
                published_at=published_at,
                summary_from_feed=getattr(entry, "summary", None),
                cover_image_url=cover_image_url,
                guid=getattr(entry, "id", None),
            )
        )

    return ParsedFeed(
        feed_title=getattr(feed.feed, "title", None) or "Untitled Feed",
        site_url=getattr(feed.feed, "link", None),
        items=items,
    )


def fetch_feed_xml(url: str) -> str:
    request = Request(url, headers={"User-Agent": "RSSWise/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def list_feeds_for_api(db: Session) -> list[dict]:
    feeds = db.execute(select(Feed).order_by(Feed.created_at.desc())).scalars().all()
    return [
        {
            "id": str(feed.id),
            "title": feed.title,
            "url": feed.url,
            "site_url": feed.site_url,
            "favicon_url": feed.favicon_url,
            "last_fetched_at": feed.last_fetched_at.isoformat() if feed.last_fetched_at else None,
        }
        for feed in feeds
    ]


def add_feed_from_url(db: Session, url: str) -> Feed:
    parsed = parse_feed_items(fetch_feed_xml(url))
    feed = db.execute(select(Feed).where(Feed.url == url)).scalar_one_or_none()
    if feed is None:
        feed = Feed(url=url, title=parsed.feed_title)
        db.add(feed)

    feed.title = parsed.feed_title
    feed.site_url = parsed.site_url
    feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
    feed.last_fetched_at = datetime.utcnow()
    db.flush()

    new_articles = upsert_feed_articles(db, feed, parsed)
    db.commit()
    enqueue_extraction(new_articles)
    return feed


def refresh_feed_by_id(db: Session, feed_id: UUID) -> int:
    feed = db.get(Feed, feed_id)
    if feed is None:
        raise ValueError("feed not found")

    parsed = parse_feed_items(fetch_feed_xml(feed.url))
    feed.title = parsed.feed_title
    feed.site_url = parsed.site_url
    feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
    feed.last_fetched_at = datetime.utcnow()
    new_articles = upsert_feed_articles(db, feed, parsed)
    db.commit()
    enqueue_extraction(new_articles)
    return len(new_articles)


def delete_feed_by_id(db: Session, feed_id: UUID) -> None:
    feed = db.get(Feed, feed_id)
    if feed is not None:
        db.delete(feed)
        db.commit()


def upsert_feed_articles(db: Session, feed: Feed, parsed: ParsedFeed) -> list[Article]:
    new_articles: list[Article] = []
    for item in parsed.items:
        existing = db.execute(
            select(Article).where(
                or_(
                    Article.url == item.url,
                    Article.guid == item.guid if item.guid else False,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.title = item.title
            existing.author = item.author
            existing.published_at = item.published_at
            existing.summary_from_feed = item.summary_from_feed
            existing.cover_image_url = item.cover_image_url
            continue

        article = Article(
            feed_id=feed.id,
            title=item.title,
            url=item.url,
            author=item.author,
            published_at=item.published_at,
            summary_from_feed=item.summary_from_feed,
            cover_image_url=item.cover_image_url,
            guid=item.guid,
            is_read=False,
        )
        db.add(article)
        db.flush()
        db.add(ArticleContent(article_id=article.id))
        db.add(ArticleAIAnalysis(article_id=article.id))
        new_articles.append(article)

    return new_articles


def enqueue_extraction(articles: list[Article]) -> None:
    from app.tasks import extract_article_task

    for article in articles:
        extract_article_task.delay(str(article.id))
```

- [ ] **Step 3: Add feed API router**

Create `apps/api/app/routers/feeds.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Feed
from app.services.feed_service import (
    add_feed_from_url,
    delete_feed_by_id,
    list_feeds_for_api,
)
from app.tasks import refresh_feed_task

router = APIRouter(prefix="/feeds", tags=["feeds"])


class FeedCreate(BaseModel):
    url: HttpUrl


@router.get("")
def list_feeds(db: Session = Depends(get_db)):
    return list_feeds_for_api(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_feed(payload: FeedCreate, db: Session = Depends(get_db)):
    feed = add_feed_from_url(db, str(payload.url))
    return {"id": str(feed.id), "title": feed.title, "url": feed.url}


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_feed(feed_id: UUID, db: Session = Depends(get_db)):
    if db.get(Feed, feed_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feed not found")
    refresh_feed_task.delay(str(feed_id))
    return {"feed_id": str(feed_id), "status": "queued"}


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(feed_id: UUID, db: Session = Depends(get_db)):
    delete_feed_by_id(db, feed_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Mount router**

Modify `apps/api/app/main.py`:

```python
from fastapi import FastAPI

from app.core.logging import configure_logging
from app.routers import feeds

configure_logging()

app = FastAPI(title="RSSWise API")
app.include_router(feeds.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run checks**

Run:

```bash
cd apps/api
pytest tests/test_feed_service.py
ruff check app tests
```

Expected: tests and lint pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/feed_service.py apps/api/app/routers/feeds.py apps/api/app/main.py apps/api/tests/test_feed_service.py
git commit -m "feat: add feed ingestion api"
```

---

## Task 4: Implement Article Extraction With trafilatura

**Files:**
- Create: `apps/api/app/services/extraction_service.py`
- Create: `apps/api/tests/test_extraction_service.py`
- Modify: `apps/api/app/tasks.py`

- [ ] **Step 1: Write extraction test**

Create `apps/api/tests/test_extraction_service.py`:

```python
from app.services.extraction_service import extract_markdown_from_html


def test_extract_markdown_from_html_removes_unrelated_content():
    html = """
    <html><body>
      <nav>Navigation</nav>
      <article>
        <h1>Readable Title</h1>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
      </article>
    </body></html>
    """

    markdown = extract_markdown_from_html(html, "https://example.com/post")

    assert "Readable Title" in markdown
    assert "First paragraph." in markdown
    assert "Navigation" not in markdown
```

- [ ] **Step 2: Implement markdown extraction**

Create `apps/api/app/services/extraction_service.py`:

```python
import trafilatura


def extract_markdown_from_html(html: str, url: str) -> str:
    markdown = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )
    if not markdown:
        raise ValueError("article extraction returned no markdown")
    return "\n\n".join(block.strip() for block in markdown.split("\n\n") if block.strip())


def fetch_and_extract_markdown(url: str) -> str:
    html = trafilatura.fetch_url(url)
    if not html:
        raise ValueError("article fetch returned no html")
    return extract_markdown_from_html(html, url)
```

- [ ] **Step 3: Add Celery extraction task**

Create `apps/api/app/tasks.py`:

```python
from datetime import datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import ArticleContent, ExtractionStatus
from app.services.extraction_service import fetch_and_extract_markdown

celery_app = Celery("rsswise", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="articles.extract")
def extract_article_task(article_id: str) -> None:
    with SessionLocal() as db:
        content = db.execute(
            select(ArticleContent).where(ArticleContent.article_id == UUID(article_id))
        ).scalar_one()
        content.extraction_status = ExtractionStatus.processing
        db.commit()

        try:
            markdown = fetch_and_extract_markdown(content.article.url)
            content.content_markdown = markdown
            content.extraction_status = ExtractionStatus.success
            content.extracted_at = datetime.utcnow()
            db.commit()
            analyze_article_task.delay(article_id)
        except Exception:
            content.extraction_status = ExtractionStatus.failed
            db.commit()
            raise
```

This task stores only markdown in `ArticleContent.content_markdown`; raw HTML is discarded after extraction.

- [ ] **Step 4: Run checks**

Run:

```bash
cd apps/api
pytest tests/test_extraction_service.py
ruff check app tests
```

Expected: tests and lint pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/extraction_service.py apps/api/app/tasks.py apps/api/tests/test_extraction_service.py
git commit -m "feat: extract article markdown"
```

---

## Task 5: Implement DeepSeek AI Analysis

**Files:**
- Create: `apps/api/app/services/ai_service.py`
- Create: `apps/api/tests/test_ai_service.py`
- Modify: `apps/api/app/tasks.py`

- [ ] **Step 1: Write strict parsing tests**

Create `apps/api/tests/test_ai_service.py`:

```python
import pytest

from app.services.ai_service import parse_ai_result


def test_parse_ai_result_accepts_design_enum():
    result = parse_ai_result(
        '{"one_sentence_summary":"Short summary.","reading_recommendation":"skim","reading_reason":"Useful context."}'
    )

    assert result.reading_recommendation == "skim"


def test_parse_ai_result_rejects_score_output():
    with pytest.raises(ValueError):
        parse_ai_result(
            '{"one_sentence_summary":"Short summary.","reading_recommendation":"score_9","reading_reason":"Useful."}'
        )
```

- [ ] **Step 2: Implement DeepSeek service**

Create `apps/api/app/services/ai_service.py`:

```python
from pydantic import BaseModel, Field, ValidationError
from openai import OpenAI

from app.core.config import settings


class AIAnalysisResult(BaseModel):
    one_sentence_summary: str = Field(min_length=1, max_length=160)
    reading_recommendation: str
    reading_reason: str = Field(min_length=1, max_length=500)


def parse_ai_result(content: str) -> AIAnalysisResult:
    try:
        result = AIAnalysisResult.model_validate_json(content)
    except ValidationError as exc:
        raise ValueError("invalid ai analysis json") from exc

    if result.reading_recommendation not in {"deep_read", "skim", "skip"}:
        raise ValueError("invalid reading_recommendation")

    return result


def analyze_markdown_with_deepseek(markdown: str) -> AIAnalysisResult:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required")

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 RSS 阅读前分析助手。只返回 JSON。"
                    "字段必须是 one_sentence_summary, reading_recommendation, reading_reason。"
                    "reading_recommendation 只能是 deep_read, skim, skip。"
                    "不要输出长摘要、分数、target readers 或 keywords。"
                ),
            },
            {"role": "user", "content": markdown[:40000]},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty ai response")
    return parse_ai_result(content)
```

- [ ] **Step 3: Add AI Celery task and reanalysis helper**

Extend `apps/api/app/tasks.py` with:

```python
from app.models import AnalysisStatus, ArticleAIAnalysis
from app.services.ai_service import analyze_markdown_with_deepseek


@celery_app.task(name="articles.analyze")
def analyze_article_task(article_id: str) -> None:
    with SessionLocal() as db:
        analysis = db.get(ArticleAIAnalysis, UUID(article_id))
        content = db.get(ArticleContent, UUID(article_id))
        if analysis is None or content is None or not content.content_markdown:
            raise ValueError("article requires markdown before analysis")

        analysis.analysis_status = AnalysisStatus.processing
        db.commit()

        try:
            result = analyze_markdown_with_deepseek(content.content_markdown)
            analysis.one_sentence_summary = result.one_sentence_summary
            analysis.reading_recommendation = result.reading_recommendation
            analysis.reading_reason = result.reading_reason
            analysis.analysis_status = AnalysisStatus.success
            analysis.updated_at = datetime.utcnow()
            db.commit()
        except Exception:
            analysis.analysis_status = AnalysisStatus.failed
            analysis.updated_at = datetime.utcnow()
            db.commit()
            raise
```

For “重新 AI 分析”, enqueue only `analyze_article_task`. Do not enqueue extraction and do not fetch RSS.

- [ ] **Step 4: Run checks**

Run:

```bash
cd apps/api
pytest tests/test_ai_service.py
ruff check app tests
```

Expected: tests and lint pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ai_service.py apps/api/app/tasks.py apps/api/tests/test_ai_service.py
git commit -m "feat: add deepseek article analysis"
```

---

## Task 6: Implement Hourly Feed Refresh With Celery Beat

**Files:**
- Modify: `apps/api/app/tasks.py`
- Create: `apps/api/app/beat.py`
- Create: `apps/api/tests/test_beat.py`

- [ ] **Step 1: Add beat schedule test**

Create `apps/api/tests/test_beat.py`:

```python
from app.beat import beat_schedule


def test_feed_refresh_runs_hourly():
    schedule = beat_schedule["refresh-all-feeds-hourly"]

    assert schedule["task"] == "feeds.refresh_all"
    assert schedule["schedule"] == 3600.0
```

- [ ] **Step 2: Implement schedule**

Create `apps/api/app/beat.py`:

```python
beat_schedule = {
    "refresh-all-feeds-hourly": {
        "task": "feeds.refresh_all",
        "schedule": 3600.0,
    }
}
```

Modify Celery config in `apps/api/app/tasks.py`:

```python
from app.beat import beat_schedule

celery_app.conf.beat_schedule = beat_schedule
```

- [ ] **Step 3: Add refresh tasks**

Add to `apps/api/app/tasks.py`:

```python
from sqlalchemy import select

from app.models import Feed
from app.services.feed_service import refresh_feed_by_id


@celery_app.task(name="feeds.refresh_all")
def refresh_all_feeds_task() -> None:
    with SessionLocal() as db:
        feed_ids = [str(row[0]) for row in db.execute(select(Feed.id)).all()]

    for feed_id in feed_ids:
        refresh_feed_task.delay(feed_id)


@celery_app.task(name="feeds.refresh")
def refresh_feed_task(feed_id: str) -> None:
    with SessionLocal() as db:
        refresh_feed_by_id(db, UUID(feed_id))
```

- [ ] **Step 4: Run checks**

Run:

```bash
cd apps/api
pytest tests/test_beat.py
ruff check app tests
```

Expected: tests and lint pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/beat.py apps/api/app/tasks.py apps/api/tests/test_beat.py
git commit -m "feat: schedule hourly feed refresh"
```

---

## Task 7: Implement Article API and Read State

**Files:**
- Create: `apps/api/app/routers/articles.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/test_articles_api.py`

- [ ] **Step 1: Write API behavior tests**

Create `apps/api/tests/test_articles_api.py`:

```python
from app.models import ReadingRecommendation


def test_recommendation_labels_are_design_values():
    labels = {
        ReadingRecommendation.deep_read.value: "值得精读",
        ReadingRecommendation.skim.value: "适合略读",
        ReadingRecommendation.skip.value: "可以跳过",
    }

    assert labels == {
        "deep_read": "值得精读",
        "skim": "适合略读",
        "skip": "可以跳过",
    }
```

- [ ] **Step 2: Add article router**

Create `apps/api/app/routers/articles.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Article
from app.tasks import analyze_article_task

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
def list_articles(status_filter: str = "all", db: Session = Depends(get_db)):
    if status_filter not in {"all", "read", "unread"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status_filter")

    statement = (
        select(Article)
        .options(joinedload(Article.feed), joinedload(Article.ai_analysis))
        .order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
    )
    if status_filter == "read":
        statement = statement.where(Article.is_read.is_(True))
    if status_filter == "unread":
        statement = statement.where(Article.is_read.is_(False))

    articles = db.execute(statement).scalars().all()
    return [
        {
            "id": str(article.id),
            "title": article.title,
            "source_title": article.feed.title,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "one_sentence_summary": article.ai_analysis.one_sentence_summary if article.ai_analysis else None,
            "reading_recommendation": article.ai_analysis.reading_recommendation.value if article.ai_analysis and article.ai_analysis.reading_recommendation else None,
            "is_read": article.is_read,
        }
        for article in articles
    ]


@router.get("/{article_id}")
def get_article(article_id: UUID, db: Session = Depends(get_db)):
    article = db.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(joinedload(Article.feed), joinedload(Article.content), joinedload(Article.ai_analysis))
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")

    return {
        "id": str(article.id),
        "title": article.title,
        "source_title": article.feed.title,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "url": article.url,
        "one_sentence_summary": article.ai_analysis.one_sentence_summary if article.ai_analysis else None,
        "reading_recommendation": article.ai_analysis.reading_recommendation.value if article.ai_analysis and article.ai_analysis.reading_recommendation else None,
        "reading_reason": article.ai_analysis.reading_reason if article.ai_analysis else None,
        "content_markdown": article.content.content_markdown if article.content else None,
    }


@router.post("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(article_id: UUID, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    article.is_read = True
    db.commit()
    return None


@router.post("/{article_id}/unread", status_code=status.HTTP_204_NO_CONTENT)
def mark_unread(article_id: UUID, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    article.is_read = False
    db.commit()
    return None


@router.post("/{article_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze(article_id: UUID, db: Session = Depends(get_db)):
    if db.get(Article, article_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    analyze_article_task.delay(str(article_id))
    return {"status": "queued"}
```

- [ ] **Step 3: Mount article router**

Modify `apps/api/app/main.py`:

```python
from app.routers import articles, feeds

app.include_router(feeds.router)
app.include_router(articles.router)
```

- [ ] **Step 4: Run checks**

Run:

```bash
cd apps/api
pytest tests/test_articles_api.py
ruff check app tests
```

Expected: tests and lint pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/routers/articles.py apps/api/app/main.py apps/api/tests/test_articles_api.py
git commit -m "feat: add article reading api"
```

---

## Task 8: Build Next.js Article List and Detail Pages

**Files:**
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/components/recommendation-badge.tsx`
- Create: `apps/web/components/markdown-content.tsx`
- Create: `apps/web/app/articles/page.tsx`
- Create: `apps/web/app/articles/[id]/page.tsx`
- Create: `apps/web/app/articles/[id]/actions.ts`

- [ ] **Step 1: Add API client**

Create `apps/web/lib/api.ts`:

```ts
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API GET ${path} failed`);
  return response.json() as Promise<T>;
}

export async function apiPost(path: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}${path}`, { method: "POST" });
  if (!response.ok) throw new Error(`API POST ${path} failed`);
}
```

- [ ] **Step 2: Add recommendation badge**

Create `apps/web/components/recommendation-badge.tsx`:

```tsx
const labels = {
  deep_read: "值得精读",
  skim: "适合略读",
  skip: "可以跳过"
} as const;

export function RecommendationBadge({ value }: { value: keyof typeof labels }) {
  return <span className="rounded border px-2 py-1 text-xs">{labels[value]}</span>;
}
```

- [ ] **Step 3: Add sanitized markdown renderer**

Create `apps/web/components/markdown-content.tsx`:

```tsx
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ markdown }: { markdown: string }) {
  return (
    <article className="prose prose-slate max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
```

- [ ] **Step 4: Build article list page**

Create `apps/web/app/articles/page.tsx`:

```tsx
import Link from "next/link";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { apiGet } from "@/lib/api";

type ArticleListItem = {
  id: string;
  title: string;
  source_title: string;
  published_at: string | null;
  one_sentence_summary: string | null;
  reading_recommendation: "deep_read" | "skim" | "skip" | null;
  is_read: boolean;
};

export default async function ArticlesPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const params = await searchParams;
  const status = params.status === "read" || params.status === "unread" ? params.status : "all";
  const articles = await apiGet<ArticleListItem[]>(`/articles?status_filter=${status}`);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">文章</h1>
        <div className="flex gap-2">
          <Link href="/articles">全部</Link>
          <Link href="/articles?status=read">已读</Link>
          <Link href="/articles?status=unread">未读</Link>
        </div>
      </div>
      <div className="divide-y rounded border bg-white">
        {articles.map((article) => (
          <Link key={article.id} href={`/articles/${article.id}`} className="block p-4">
            <div className="flex justify-between gap-4">
              <div>
                <h2 className={article.is_read ? "text-slate-500" : "font-medium"}>{article.title}</h2>
                <p className="text-sm text-slate-500">{article.source_title}</p>
                {article.one_sentence_summary ? <p className="mt-2 text-sm">{article.one_sentence_summary}</p> : null}
              </div>
              <div className="flex flex-col items-end gap-2">
                {article.reading_recommendation ? <RecommendationBadge value={article.reading_recommendation} /> : null}
                <span className="text-xs text-slate-500">{article.is_read ? "已读" : "未读"}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Build detail page and actions**

Create `apps/web/app/articles/[id]/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { apiPost } from "@/lib/api";

export async function markUnread(articleId: string) {
  await apiPost(`/articles/${articleId}/unread`);
  revalidatePath(`/articles/${articleId}`);
  revalidatePath("/articles");
}

export async function reanalyze(articleId: string) {
  await apiPost(`/articles/${articleId}/reanalyze`);
  revalidatePath(`/articles/${articleId}`);
}
```

Create `apps/web/app/articles/[id]/page.tsx`:

```tsx
import { MarkdownContent } from "@/components/markdown-content";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { apiGet, apiPost } from "@/lib/api";
import { markUnread, reanalyze } from "./actions";

type ArticleDetail = {
  id: string;
  title: string;
  source_title: string;
  published_at: string | null;
  url: string;
  one_sentence_summary: string | null;
  reading_recommendation: "deep_read" | "skim" | "skip" | null;
  reading_reason: string | null;
  content_markdown: string | null;
};

export default async function ArticleDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  await apiPost(`/articles/${id}/read`);
  const article = await apiGet<ArticleDetail>(`/articles/${id}`);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{article.title}</h1>
      <p className="text-sm text-slate-500">{article.source_title}</p>
      <a href={article.url} target="_blank" rel="noreferrer">原文链接</a>

      <section className="rounded border bg-white p-4">
        <h2 className="font-medium">AI 信息</h2>
        {article.reading_recommendation ? <RecommendationBadge value={article.reading_recommendation} /> : null}
        {article.one_sentence_summary ? <p>{article.one_sentence_summary}</p> : null}
        {article.reading_reason ? <p className="text-sm text-slate-600">{article.reading_reason}</p> : null}
        <div className="mt-3 flex gap-2">
          <form action={markUnread.bind(null, article.id)}>
            <button>标记未读</button>
          </form>
          <form action={reanalyze.bind(null, article.id)}>
            <button>重新 AI 分析</button>
          </form>
        </div>
      </section>

      <MarkdownContent markdown={article.content_markdown ?? "正文处理中"} />
    </div>
  );
}
```

- [ ] **Step 6: Run checks**

Run:

```bash
cd apps/web
pnpm build
```

Expected: frontend build passes.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat: add article reading pages"
```

---

## Task 9: Build Feed Management Page

**Files:**
- Create: `apps/web/app/feeds/actions.ts`
- Create: `apps/web/app/feeds/page.tsx`

- [ ] **Step 1: Add feed actions**

Create `apps/web/app/feeds/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { apiPost } from "@/lib/api";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function addFeed(formData: FormData) {
  const url = String(formData.get("url") ?? "").trim();
  if (!url) return;
  const response = await fetch(`${apiBaseUrl}/feeds`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url })
  });
  if (!response.ok) throw new Error("add feed failed");
  revalidatePath("/feeds");
  revalidatePath("/articles");
}

export async function refreshFeed(feedId: string) {
  await apiPost(`/feeds/${feedId}/refresh`);
  revalidatePath("/feeds");
}

export async function deleteFeed(feedId: string) {
  const response = await fetch(`${apiBaseUrl}/feeds/${feedId}`, { method: "DELETE" });
  if (!response.ok) throw new Error("delete feed failed");
  revalidatePath("/feeds");
  revalidatePath("/articles");
}
```

- [ ] **Step 2: Build feed page**

Create `apps/web/app/feeds/page.tsx`:

```tsx
import { apiGet } from "@/lib/api";
import { addFeed, deleteFeed, refreshFeed } from "./actions";

type Feed = {
  id: string;
  title: string;
  url: string;
  site_url: string | null;
  favicon_url: string | null;
  last_fetched_at: string | null;
};

export default async function FeedsPage() {
  const feeds = await apiGet<Feed[]>("/feeds");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Feed 管理</h1>
      <form action={addFeed} className="flex gap-2">
        <label className="sr-only" htmlFor="url">Feed URL</label>
        <input id="url" name="url" type="url" required className="flex-1 rounded border px-3 py-2" />
        <button>添加 Feed</button>
      </form>

      <div className="divide-y rounded border bg-white">
        {feeds.map((feed) => (
          <div key={feed.id} className="flex justify-between gap-4 p-4">
            <div>
              <div className="flex items-center gap-2">
                {feed.favicon_url ? <img src={feed.favicon_url} alt="" className="h-4 w-4" /> : null}
                <h2 className="font-medium">{feed.title}</h2>
              </div>
              <p className="break-all text-sm text-slate-500">{feed.url}</p>
              {feed.site_url ? <p className="text-sm text-slate-500">{feed.site_url}</p> : null}
              <p className="text-sm text-slate-500">
                最后抓取时间：{feed.last_fetched_at ?? "尚未抓取"}
              </p>
            </div>
            <div className="flex gap-2">
              <form action={refreshFeed.bind(null, feed.id)}>
                <button>刷新</button>
              </form>
              <form action={deleteFeed.bind(null, feed.id)}>
                <button>删除</button>
              </form>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run checks**

Run:

```bash
cd apps/web
pnpm build
```

Expected: frontend build passes.

- [ ] **Step 4: Commit**

```bash
git add apps/web/app/feeds
git commit -m "feat: add feed management page"
```

---

## Task 10: End-to-End MVP Verification

**Files:**
- Create: `apps/web/tests/e2e/articles.spec.ts`
- Create: `apps/web/tests/e2e/feeds.spec.ts`
- Create: `README.md`

- [ ] **Step 1: Add E2E tests**

Create `apps/web/tests/e2e/articles.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("article list has required filters", async ({ page }) => {
  await page.goto("/articles");
  await expect(page.getByRole("heading", { name: "文章" })).toBeVisible();
  await expect(page.getByRole("link", { name: "全部" })).toBeVisible();
  await expect(page.getByRole("link", { name: "已读" })).toBeVisible();
  await expect(page.getByRole("link", { name: "未读" })).toBeVisible();
});
```

Create `apps/web/tests/e2e/feeds.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("feed management exposes MVP actions", async ({ page }) => {
  await page.goto("/feeds");
  await expect(page.getByRole("heading", { name: "Feed 管理" })).toBeVisible();
  await expect(page.getByLabel("Feed URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "添加 Feed" })).toBeVisible();
});
```

- [ ] **Step 2: Add README**

Create `README.md`:

````md
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
````

- [ ] **Step 3: Run final verification**

Run:

```bash
docker compose build
docker compose up -d postgres redis
cd apps/api && alembic upgrade head && pytest && ruff check app tests
cd ../web && pnpm build && pnpm test:e2e
docker compose down
```

Expected: migrations, backend tests, backend lint, frontend build, and E2E tests pass.

- [ ] **Step 4: Product-scope checklist**

Verify these match `docs/design.md`:

- Feed add/delete/list/manual refresh exists.
- Feed add immediately queues fetch and processing.
- Celery Beat refreshes all feeds every hour.
- RSS saves title, url, author, published_at, summary_from_feed, cover_image_url, guid.
- Articles dedupe by URL and/or GUID.
- Raw HTML is not stored.
- Markdown body is stored only in `ArticleContent.content_markdown`.
- Detail page displays AI information before markdown body.
- Reanalysis queues only AI analysis and overwrites `ArticleAIAnalysis`.
- Article list supports only all/read/unread filters.
- Unsupported features listed in `docs/design.md` do not appear in API or UI.

- [ ] **Step 5: Commit**

```bash
git add README.md apps/web/tests/e2e
git commit -m "test: verify aligned mvp flow"
```

---

## Spec Coverage Review

- Section 3.1 RSS source management: Tasks 3, 6, and 9.
- Section 3.2 article aggregation: Tasks 2 and 3.
- Section 3.3 body extraction: Task 4.
- Section 3.4 AI analysis: Task 5 and Task 7 reanalysis endpoint.
- Section 3.5 read state: Task 7 and Task 8 detail flow.
- Section 4 pages: Tasks 8 and 9.
- Section 5 processing flows: Tasks 3 through 7.
- Section 6 data model: Task 2 uses Feed, Article, ArticleContent, and ArticleAIAnalysis as separate tables.
- Section 7 statuses: Task 2 models extraction and analysis statuses as `pending`, `processing`, `success`, `failed`.
- Section 8 technology stack: This plan uses the exact frontend, backend, database, worker, RSS/extraction, AI, and deploy stack listed in `docs/design.md`.

## Execution Handoff

Plan complete and saved to `plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, and keep each task independently testable.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, batching work with review checkpoints.
