# RSS Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add background RSS subscription import from OPML files and multi-line URL input, with current-task progress and per-feed results.

**Architecture:** Store import jobs and items in the database, enqueue a Celery task to process each item, and expose create/get APIs under `/feeds/imports`. Keep the UI inside the existing Feed management page with a batch import dialog, polling the job endpoint until completion.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Celery, feedparser, Pydantic v2, React 18, TanStack Query, Vite, Playwright, pytest.

**Source Spec:** `docs/rss-import/spec.md`

---

## File Map

- Create: `apps/api/alembic/versions/0004_feed_import_jobs.py`  
  Responsibility: add feed import job/item tables and enum columns.

- Modify: `apps/api/app/models.py`  
  Responsibility: define import status enums and SQLAlchemy models.

- Modify: `apps/api/app/schemas.py`  
  Responsibility: define request/response schemas for creating and reading imports.

- Create: `apps/api/app/services/feed_import_service.py`  
  Responsibility: parse URL text, parse OPML, normalize URLs, create jobs, process items, update counters.

- Modify: `apps/api/app/services/feed_service.py`  
  Responsibility: expose a lower-level add/subscribe result for import processing while preserving existing single-feed behavior.

- Modify: `apps/api/app/routers/feeds.py`  
  Responsibility: add `POST /feeds/imports` and `GET /feeds/imports/{import_id}`.

- Modify: `apps/api/app/tasks.py`  
  Responsibility: add `feeds.import` Celery task.

- Create: `apps/api/tests/test_feed_import_service.py`  
  Responsibility: cover parsing, duplicate handling, item processing, and counters.

- Modify: `apps/api/tests/test_feeds_api.py`  
  Responsibility: cover import create/get endpoints, auth, ownership, and limit errors.

- Modify: `apps/api/tests/test_tasks.py`  
  Responsibility: cover import task status transitions and partial failure behavior.

- Modify: `apps/web/src/lib/api.ts`  
  Responsibility: add feed import TypeScript types.

- Modify: `apps/web/src/lib/query-keys.ts`  
  Responsibility: add feed import query key helpers.

- Modify: `apps/web/src/routes/feeds/list.tsx`  
  Responsibility: add batch import dialog, OPML file reading, multi-line URL submission, polling, and result rendering.

- Modify: `apps/web/tests/e2e/feeds.spec.ts`  
  Responsibility: cover import entry point, URL import submission, OPML submission, polling result, and failed item display.

---

## Implementation Notes

- Keep existing `POST /feeds` behavior intact.
- Keep import state in the database, not Redis.
- Create one `FeedImportItem` per accepted input candidate, including duplicate candidates.
- Enforce the 200 limit by unique `dedupe_key`, not by raw input row count.
- Preserve trailing slashes, query strings, schemes, and paths during URL normalization.
- Do not add OPML export, category import, history list, SSE, WebSocket, or feed discovery.
- Use concise user-facing failure messages; do not expose raw exception text.
- Commit after each task when executing the plan.

---

### Task 1: Add Backend Model and Migration

**Files:**
- Create: `apps/api/alembic/versions/0004_feed_import_jobs.py`
- Modify: `apps/api/app/models.py`

- [ ] **Step 1: Confirm current migration head**

Run:

```bash
ls apps/api/alembic/versions
```

Expected: existing migrations include `0003_article_ai_blocks.py`.

- [ ] **Step 2: Add model enums and relationships**

In `apps/api/app/models.py`, add enums near the existing status enums:

```python
class FeedImportSourceType(str, enum.Enum):
    opml = "opml"
    urls = "urls"


class FeedImportJobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class FeedImportItemStatus(str, enum.Enum):
    pending = "pending"
    created = "created"
    subscribed = "subscribed"
    skipped = "skipped"
    failed = "failed"
```

Then add `FeedImportJob` and `FeedImportItem` models after `UserFeedSubscription`:

```python
class FeedImportJob(Base):
    __tablename__ = "feed_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    source_type: Mapped[FeedImportSourceType] = mapped_column(
        Enum(FeedImportSourceType, name="feed_import_source_type"),
    )
    status: Mapped[FeedImportJobStatus] = mapped_column(
        Enum(FeedImportJobStatus, name="feed_import_job_status"),
        default=FeedImportJobStatus.pending,
        index=True,
    )
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    subscribed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    items: Mapped[list["FeedImportItem"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FeedImportItem.created_at",
    )


class FeedImportItem(Base):
    __tablename__ = "feed_import_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feed_import_jobs.id", ondelete="CASCADE"),
        index=True,
    )
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_url: Mapped[str] = mapped_column(String(2000))
    normalized_url: Mapped[str] = mapped_column(String(2000), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(2000), index=True)
    status: Mapped[FeedImportItemStatus] = mapped_column(
        Enum(FeedImportItemStatus, name="feed_import_item_status"),
        default=FeedImportItemStatus.pending,
        index=True,
    )
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="SET NULL"),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[FeedImportJob] = relationship(back_populates="items")
    feed: Mapped[Feed | None] = relationship()
```

- [ ] **Step 3: Add Alembic migration**

Create `apps/api/alembic/versions/0004_feed_import_jobs.py`:

```python
"""feed import jobs

Revision ID: 0004_feed_import_jobs
Revises: 0003_article_ai_blocks
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_feed_import_jobs"
down_revision: str | None = "0003_article_ai_blocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_type = sa.Enum("opml", "urls", name="feed_import_source_type")
    job_status = sa.Enum("pending", "processing", "completed", "failed", name="feed_import_job_status")
    item_status = sa.Enum(
        "pending",
        "created",
        "subscribed",
        "skipped",
        "failed",
        name="feed_import_item_status",
    )
    source_type.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "feed_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("subscribed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feed_import_jobs_user_id", "feed_import_jobs", ["user_id"])
    op.create_index("ix_feed_import_jobs_status", "feed_import_jobs", ["status"])

    op.create_table(
        "feed_import_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_title", sa.String(length=500), nullable=True),
        sa.Column("raw_url", sa.String(length=2000), nullable=False),
        sa.Column("normalized_url", sa.String(length=2000), nullable=False),
        sa.Column("dedupe_key", sa.String(length=2000), nullable=False),
        sa.Column("status", item_status, nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["feed_import_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feed_import_items_job_id", "feed_import_items", ["job_id"])
    op.create_index("ix_feed_import_items_normalized_url", "feed_import_items", ["normalized_url"])
    op.create_index("ix_feed_import_items_dedupe_key", "feed_import_items", ["dedupe_key"])
    op.create_index("ix_feed_import_items_status", "feed_import_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_feed_import_items_status", table_name="feed_import_items")
    op.drop_index("ix_feed_import_items_dedupe_key", table_name="feed_import_items")
    op.drop_index("ix_feed_import_items_normalized_url", table_name="feed_import_items")
    op.drop_index("ix_feed_import_items_job_id", table_name="feed_import_items")
    op.drop_table("feed_import_items")

    op.drop_index("ix_feed_import_jobs_status", table_name="feed_import_jobs")
    op.drop_index("ix_feed_import_jobs_user_id", table_name="feed_import_jobs")
    op.drop_table("feed_import_jobs")

    sa.Enum(name="feed_import_item_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="feed_import_job_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="feed_import_source_type").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 4: Run model/API tests that create metadata**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: PASS. SQLite `Base.metadata.create_all` should create the new tables without errors.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/models.py apps/api/alembic/versions/0004_feed_import_jobs.py
git commit -m "feat(api): add feed import persistence models"
```

---

### Task 2: Add Import Schemas and Parsing Service

**Files:**
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/services/feed_import_service.py`
- Create: `apps/api/tests/test_feed_import_service.py`

- [ ] **Step 1: Write failing parsing tests**

Create `apps/api/tests/test_feed_import_service.py` with these initial tests:

```python
import pytest

from app.services.feed_import_service import (
    MAX_FEED_IMPORT_URLS,
    FeedImportCandidate,
    normalize_feed_url,
    parse_opml_feeds,
    parse_urls_text,
    prepare_import_candidates,
)


def test_parse_urls_text_trims_blank_lines_and_keeps_titles_empty():
    candidates = parse_urls_text(
        """
        https://example.com/feed.xml

        https://example.org/rss
        """
    )

    assert candidates == [
        FeedImportCandidate(source_title=None, raw_url="https://example.com/feed.xml"),
        FeedImportCandidate(source_title=None, raw_url="https://example.org/rss"),
    ]


def test_parse_opml_feeds_reads_nested_outlines():
    candidates = parse_opml_feeds(
        """
        <opml version="2.0">
          <body>
            <outline text="Folder">
              <outline text="Example" title="Example Title" xmlUrl="https://example.com/feed.xml" />
              <outline text="Second" xmlUrl="https://example.org/rss" />
            </outline>
          </body>
        </opml>
        """
    )

    assert candidates == [
        FeedImportCandidate(source_title="Example Title", raw_url="https://example.com/feed.xml"),
        FeedImportCandidate(source_title="Second", raw_url="https://example.org/rss"),
    ]


def test_parse_opml_rejects_invalid_xml():
    with pytest.raises(ValueError, match="OPML 解析失败"):
        parse_opml_feeds("<opml><body>")


def test_prepare_import_candidates_preserves_duplicates_as_items():
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="A", raw_url=" https://example.com/feed.xml "),
            FeedImportCandidate(source_title="A duplicate", raw_url="https://example.com/feed.xml"),
        ]
    )

    assert prepared.unique_count == 1
    assert [item.dedupe_key for item in prepared.items] == [
        "https://example.com/feed.xml",
        "https://example.com/feed.xml",
    ]


def test_prepare_import_candidates_enforces_unique_limit():
    candidates = [
        FeedImportCandidate(source_title=None, raw_url=f"https://example.com/{index}.xml")
        for index in range(MAX_FEED_IMPORT_URLS + 1)
    ]

    with pytest.raises(ValueError, match="最多导入 200 个 Feed"):
        prepare_import_candidates(candidates)


def test_normalize_feed_url_is_conservative():
    assert normalize_feed_url(" https://example.com/feed/?a=1 ") == "https://example.com/feed/?a=1"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_import_service.py -v
```

Expected: FAIL because `feed_import_service.py` does not exist.

- [ ] **Step 3: Add schemas**

In `apps/api/app/schemas.py`, import the new model enums and add:

```python
from app.models import (
    AnalysisStatus,
    ExtractionStatus,
    FeedImportItemStatus,
    FeedImportJobStatus,
    FeedImportSourceType,
    ReadingRecommendation,
)
```

Add these schemas after `FeedCreate`:

```python
class FeedImportCreate(BaseModel):
    source_type: FeedImportSourceType
    urls_text: str | None = None
    opml_xml: str | None = None

    @model_validator(mode="after")
    def validate_source_payload(self) -> "FeedImportCreate":
        if self.source_type == FeedImportSourceType.urls and not (self.urls_text or "").strip():
            raise ValueError("urls_text is required for URL imports")
        if self.source_type == FeedImportSourceType.opml and not (self.opml_xml or "").strip():
            raise ValueError("opml_xml is required for OPML imports")
        return self


class FeedImportItemRead(BaseModel):
    id: UUID
    source_title: str | None
    raw_url: str
    normalized_url: str
    dedupe_key: str
    status: FeedImportItemStatus
    feed_id: UUID | None
    message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FeedImportJobRead(BaseModel):
    id: UUID
    source_type: FeedImportSourceType
    status: FeedImportJobStatus
    total_count: int
    processed_count: int
    created_count: int
    subscribed_count: int
    skipped_count: int
    failed_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    items: list[FeedImportItemRead] = []

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Implement parsing service**

Create `apps/api/app/services/feed_import_service.py`:

```python
from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree

MAX_FEED_IMPORT_URLS = 200


@dataclass(frozen=True)
class FeedImportCandidate:
    source_title: str | None
    raw_url: str


@dataclass(frozen=True)
class PreparedFeedImportItem:
    source_title: str | None
    raw_url: str
    normalized_url: str
    dedupe_key: str


@dataclass(frozen=True)
class PreparedFeedImport:
    items: list[PreparedFeedImportItem]
    unique_count: int


def normalize_feed_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL 必须是 http 或 https 地址")
    return normalized


def parse_urls_text(text: str) -> list[FeedImportCandidate]:
    return [
        FeedImportCandidate(source_title=None, raw_url=line.strip())
        for line in text.splitlines()
        if line.strip()
    ]


def parse_opml_feeds(xml: str) -> list[FeedImportCandidate]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("OPML 解析失败") from exc

    candidates: list[FeedImportCandidate] = []
    for outline in root.iter("outline"):
        raw_url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlurl")
        if not raw_url:
            continue
        source_title = outline.attrib.get("title") or outline.attrib.get("text")
        candidates.append(
            FeedImportCandidate(
                source_title=source_title.strip() if source_title and source_title.strip() else None,
                raw_url=raw_url.strip(),
            )
        )
    return candidates


def prepare_import_candidates(candidates: list[FeedImportCandidate]) -> PreparedFeedImport:
    items: list[PreparedFeedImportItem] = []
    unique_keys: set[str] = set()

    for candidate in candidates:
        normalized_url = normalize_feed_url(candidate.raw_url)
        dedupe_key = normalized_url
        unique_keys.add(dedupe_key)
        items.append(
            PreparedFeedImportItem(
                source_title=candidate.source_title,
                raw_url=candidate.raw_url,
                normalized_url=normalized_url,
                dedupe_key=dedupe_key,
            )
        )

    if not items:
        raise ValueError("没有找到可导入的 Feed URL")

    if len(unique_keys) > MAX_FEED_IMPORT_URLS:
        raise ValueError(f"单次最多导入 {MAX_FEED_IMPORT_URLS} 个 Feed")

    return PreparedFeedImport(items=items, unique_count=len(unique_keys))
```

- [ ] **Step 5: Run parsing tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_import_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/schemas.py apps/api/app/services/feed_import_service.py apps/api/tests/test_feed_import_service.py
git commit -m "feat(api): parse feed import inputs"
```

---

### Task 3: Add Job Creation, API Endpoints, and Queueing

**Files:**
- Modify: `apps/api/app/services/feed_import_service.py`
- Modify: `apps/api/app/routers/feeds.py`
- Modify: `apps/api/tests/test_feeds_api.py`

- [ ] **Step 1: Add failing API tests**

In `apps/api/tests/test_feeds_api.py`, extend imports:

```python
from app.models import Base, Feed, FeedImportJob, FeedImportSourceType, UserFeedSubscription
```

Add tests:

```python
def test_create_url_import_requires_login(client: TestClient):
    response = client.post(
        "/feeds/imports",
        json={"source_type": "urls", "urls_text": "https://example.com/feed.xml"},
    )

    assert response.status_code == 401


def test_create_url_import_queues_job(client: TestClient, mocker):
    register(client, "importer@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")

    response = client.post(
        "/feeds/imports",
        json={
            "source_type": "urls",
            "urls_text": "https://example.com/feed.xml\nhttps://example.com/feed.xml",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "urls"
    assert data["status"] == "pending"
    assert data["total_count"] == 2
    assert data["items"] == []
    delay.assert_called_once_with(data["id"])


def test_create_opml_import_queues_job(client: TestClient, mocker):
    register(client, "opml@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")

    response = client.post(
        "/feeds/imports",
        json={
            "source_type": "opml",
            "opml_xml": "<opml><body><outline text='Example' xmlUrl='https://example.com/feed.xml' /></body></opml>",
        },
    )

    assert response.status_code == 201
    assert response.json()["total_count"] == 1
    delay.assert_called_once()


def test_create_import_rejects_too_many_unique_urls(client: TestClient, mocker):
    register(client, "limit@example.com")
    delay = mocker.patch("app.routers.feeds.import_feeds_task.delay")
    urls = "\n".join(f"https://example.com/{index}.xml" for index in range(201))

    response = client.post(
        "/feeds/imports",
        json={"source_type": "urls", "urls_text": urls},
    )

    assert response.status_code == 400
    assert "最多导入 200 个 Feed" in response.json()["detail"]
    delay.assert_not_called()


def test_get_import_only_returns_current_users_job(client: TestClient):
    first_user = register(client, "first-import@example.com")
    session_local = client.app.state.testing_session_local
    with session_local() as db:
        job = FeedImportJob(
            user_id=UUID(first_user["id"]),
            source_type=FeedImportSourceType.urls,
            total_count=0,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    register(client, "second-import@example.com")

    response = client.get(f"/feeds/imports/{job_id}")

    assert response.status_code == 404
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: FAIL because the endpoints and service functions do not exist.

- [ ] **Step 3: Add job creation service**

In `apps/api/app/services/feed_import_service.py`, add imports:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FeedImportItem,
    FeedImportJob,
    FeedImportSourceType,
    User,
)
```

Add:

```python
def create_feed_import_job(
    db: Session,
    user: User,
    source_type: FeedImportSourceType,
    prepared: PreparedFeedImport,
) -> FeedImportJob:
    job = FeedImportJob(
        user_id=user.id,
        source_type=source_type,
        total_count=len(prepared.items),
    )
    db.add(job)
    db.flush()

    for prepared_item in prepared.items:
        db.add(
            FeedImportItem(
                job_id=job.id,
                source_title=prepared_item.source_title,
                raw_url=prepared_item.raw_url,
                normalized_url=prepared_item.normalized_url,
                dedupe_key=prepared_item.dedupe_key,
            )
        )

    db.commit()
    return get_feed_import_job_for_user(db, user, job.id)


def get_feed_import_job_for_user(db: Session, user: User, job_id) -> FeedImportJob:
    job = db.execute(
        select(FeedImportJob)
        .options(selectinload(FeedImportJob.items))
        .where(FeedImportJob.id == job_id, FeedImportJob.user_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("import not found")
    return job
```

- [ ] **Step 4: Add router endpoints**

In `apps/api/app/routers/feeds.py`, extend imports:

```python
from app.models import Feed, FeedImportSourceType, User
from app.schemas import FeedCreate, FeedImportCreate, FeedImportJobRead
from app.services.feed_import_service import (
    create_feed_import_job,
    get_feed_import_job_for_user,
    parse_opml_feeds,
    parse_urls_text,
    prepare_import_candidates,
)
from app.tasks import import_feeds_task, refresh_feed_task
```

Add endpoints before `@router.post("/{feed_id}/refresh")` so `/imports` does not conflict with `/{feed_id}`:

```python
@router.post("/imports", response_model=FeedImportJobRead, status_code=status.HTTP_201_CREATED)
def create_feed_import(
    payload: FeedImportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        candidates = (
            parse_urls_text(payload.urls_text or "")
            if payload.source_type == FeedImportSourceType.urls
            else parse_opml_feeds(payload.opml_xml or "")
        )
        prepared = prepare_import_candidates(candidates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = create_feed_import_job(db, current_user, payload.source_type, prepared)
    import_feeds_task.delay(str(job.id))
    job.items = []
    return job


@router.get("/imports/{import_id}", response_model=FeedImportJobRead)
def get_feed_import(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_feed_import_job_for_user(db, current_user, import_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import not found") from exc
```

- [ ] **Step 5: Add temporary task stub**

In `apps/api/app/tasks.py`, add a stub so API tests can patch `.delay` before full task implementation:

```python
@celery_app.task(name="feeds.import")
def import_feeds_task(job_id: str) -> None:
    return None
```

- [ ] **Step 6: Run API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/feed_import_service.py apps/api/app/routers/feeds.py apps/api/app/tasks.py apps/api/tests/test_feeds_api.py
git commit -m "feat(api): add feed import endpoints"
```

---

### Task 4: Refactor Feed Add Logic for Import Outcomes

**Files:**
- Modify: `apps/api/app/services/feed_service.py`
- Modify: `apps/api/tests/test_feed_service.py`

- [ ] **Step 1: Add failing service tests**

In `apps/api/tests/test_feed_service.py`, add imports:

```python
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Feed, User, UserFeedSubscription
from app.services.feed_service import add_or_subscribe_feed_from_url
```

Add helpers and tests:

```python
def make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_local()


def make_user(db, email="user@example.com"):
    user = User(id=uuid4(), email=email, password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_add_or_subscribe_skips_existing_user_subscription():
    db = make_db()
    user = make_user(db)
    feed = Feed(title="Existing", url="https://example.com/feed.xml")
    db.add(feed)
    db.flush()
    db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))
    db.commit()

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "skipped"
    assert result.feed.id == feed.id


def test_add_or_subscribe_subscribes_existing_global_feed():
    db = make_db()
    user = make_user(db)
    feed = Feed(title="Existing", url="https://example.com/feed.xml")
    db.add(feed)
    db.commit()

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "subscribed"
    assert db.get(UserFeedSubscription, (user.id, feed.id)) is not None


def test_add_or_subscribe_creates_new_feed(mocker):
    db = make_db()
    user = make_user(db)
    mocker.patch(
        "app.services.feed_service.fetch_feed_xml",
        return_value="<rss><channel><title>Created</title><link>https://example.com</link></channel></rss>",
    )
    enqueue = mocker.patch("app.services.feed_service.enqueue_extraction")

    result = add_or_subscribe_feed_from_url(db, "https://example.com/feed.xml", user)

    assert result.status == "created"
    assert result.feed.title == "Created"
    assert db.execute(select(Feed)).scalar_one().url == "https://example.com/feed.xml"
    enqueue.assert_called_once()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_service.py -v
```

Expected: FAIL because `add_or_subscribe_feed_from_url` does not exist.

- [ ] **Step 3: Add result dataclass and lower-level service**

In `apps/api/app/services/feed_service.py`, add:

```python
@dataclass(frozen=True)
class FeedSubscriptionResult:
    status: str
    feed: Feed
```

Refactor `add_feed_from_url` by adding:

```python
def add_or_subscribe_feed_from_url(db: Session, url: str, user: User) -> FeedSubscriptionResult:
    feed = db.execute(select(Feed).where(Feed.url == url)).scalar_one_or_none()
    new_articles: list[Article] = []

    if feed is None:
        parsed = parse_feed_items(fetch_feed_xml(url))
        feed = Feed(url=url, title=parsed.feed_title)
        db.add(feed)
        feed.title = parsed.feed_title
        feed.site_url = parsed.site_url
        feed.favicon_url = f"{parsed.site_url.rstrip('/')}/favicon.ico" if parsed.site_url else None
        feed.last_fetched_at = datetime.now(UTC).replace(tzinfo=None)
        db.flush()
        new_articles = upsert_feed_articles(db, feed, parsed)
        db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))
        db.commit()
        enqueue_extraction(new_articles)
        return FeedSubscriptionResult(status="created", feed=feed)

    subscription = db.get(UserFeedSubscription, (user.id, feed.id))
    if subscription is not None:
        return FeedSubscriptionResult(status="skipped", feed=feed)

    db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))
    db.commit()
    return FeedSubscriptionResult(status="subscribed", feed=feed)
```

Then simplify `add_feed_from_url`:

```python
def add_feed_from_url(db: Session, url: str, user: User) -> Feed:
    return add_or_subscribe_feed_from_url(db, url, user).feed
```

- [ ] **Step 4: Run feed service tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Run existing feed API tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feeds_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/feed_service.py apps/api/tests/test_feed_service.py
git commit -m "refactor(api): report feed subscription outcomes"
```

---

### Task 5: Implement Import Processing and Celery Task

**Files:**
- Modify: `apps/api/app/services/feed_import_service.py`
- Modify: `apps/api/app/tasks.py`
- Modify: `apps/api/tests/test_feed_import_service.py`
- Modify: `apps/api/tests/test_tasks.py`

- [ ] **Step 1: Add failing import processing tests**

In `apps/api/tests/test_feed_import_service.py`, extend imports:

```python
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    FeedImportItem,
    FeedImportItemStatus,
    FeedImportJob,
    FeedImportJobStatus,
    FeedImportSourceType,
    User,
)
from app.services.feed_import_service import create_feed_import_job, process_feed_import_job
```

Add helpers and tests:

```python
def make_import_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def make_import_user(db):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_process_import_job_marks_duplicate_item_skipped(mocker):
    db = make_import_db()
    user = make_import_user(db)
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="A", raw_url="https://example.com/feed.xml"),
            FeedImportCandidate(source_title="A again", raw_url="https://example.com/feed.xml"),
        ]
    )
    job = create_feed_import_job(db, user, FeedImportSourceType.urls, prepared)
    add_or_subscribe = mocker.patch("app.services.feed_import_service.add_or_subscribe_feed_from_url")
    add_or_subscribe.return_value.status = "created"
    add_or_subscribe.return_value.feed.id = uuid4()

    process_feed_import_job(db, job.id)

    db.refresh(job)
    items = db.execute(select(FeedImportItem).order_by(FeedImportItem.created_at)).scalars().all()
    assert job.status == FeedImportJobStatus.completed
    assert job.processed_count == 2
    assert job.created_count == 1
    assert job.skipped_count == 1
    assert [item.status for item in items] == [
        FeedImportItemStatus.created,
        FeedImportItemStatus.skipped,
    ]
    add_or_subscribe.assert_called_once()


def test_process_import_job_records_item_failure_and_continues(mocker):
    db = make_import_db()
    user = make_import_user(db)
    prepared = prepare_import_candidates(
        [
            FeedImportCandidate(source_title="Broken", raw_url="https://broken.example.com/feed.xml"),
            FeedImportCandidate(source_title="Good", raw_url="https://good.example.com/feed.xml"),
        ]
    )
    job = create_feed_import_job(db, user, FeedImportSourceType.urls, prepared)

    good_feed_id = uuid4()

    def fake_add(db, url, user):
        if "broken" in url:
            raise TimeoutError("timed out while fetching private details")
        result = mocker.Mock()
        result.status = "subscribed"
        result.feed.id = good_feed_id
        return result

    mocker.patch("app.services.feed_import_service.add_or_subscribe_feed_from_url", side_effect=fake_add)

    process_feed_import_job(db, job.id)

    db.refresh(job)
    items = db.execute(select(FeedImportItem).order_by(FeedImportItem.created_at)).scalars().all()
    assert job.status == FeedImportJobStatus.completed
    assert job.failed_count == 1
    assert job.subscribed_count == 1
    assert items[0].status == FeedImportItemStatus.failed
    assert items[0].message == "Feed 导入失败"
    assert items[1].status == FeedImportItemStatus.subscribed
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_import_service.py -v
```

Expected: FAIL because processing is not implemented.

- [ ] **Step 3: Implement processing service**

In `apps/api/app/services/feed_import_service.py`, add imports:

```python
from datetime import UTC, datetime
from uuid import UUID

from app.models import (
    FeedImportItemStatus,
    FeedImportJobStatus,
)
from app.services.feed_service import add_or_subscribe_feed_from_url
```

Add helpers:

```python
def now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def safe_import_error_message(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    return "Feed 导入失败"


def recompute_job_counts(job: FeedImportJob) -> None:
    job.processed_count = sum(1 for item in job.items if item.status != FeedImportItemStatus.pending)
    job.created_count = sum(1 for item in job.items if item.status == FeedImportItemStatus.created)
    job.subscribed_count = sum(
        1 for item in job.items if item.status == FeedImportItemStatus.subscribed
    )
    job.skipped_count = sum(1 for item in job.items if item.status == FeedImportItemStatus.skipped)
    job.failed_count = sum(1 for item in job.items if item.status == FeedImportItemStatus.failed)
```

Add:

```python
def process_feed_import_job(db: Session, job_id: UUID) -> None:
    job = db.execute(
        select(FeedImportJob)
        .options(selectinload(FeedImportJob.items), selectinload(FeedImportJob.user))
        .where(FeedImportJob.id == job_id)
    ).scalar_one()

    job.status = FeedImportJobStatus.processing
    job.started_at = now_naive_utc()
    db.commit()

    seen_keys: set[str] = set()
    try:
        for item in sorted(job.items, key=lambda import_item: import_item.created_at):
            if item.status != FeedImportItemStatus.pending:
                seen_keys.add(item.dedupe_key)
                continue

            if item.dedupe_key in seen_keys:
                item.status = FeedImportItemStatus.skipped
                item.message = "同一批导入中已包含该 Feed"
                item.processed_at = now_naive_utc()
            else:
                seen_keys.add(item.dedupe_key)
                try:
                    result = add_or_subscribe_feed_from_url(db, item.normalized_url, job.user)
                    item.status = FeedImportItemStatus(result.status)
                    item.feed_id = result.feed.id
                    if item.status == FeedImportItemStatus.skipped:
                        item.message = "当前账号已订阅"
                    elif item.status == FeedImportItemStatus.subscribed:
                        item.message = "已订阅现有 Feed"
                    elif item.status == FeedImportItemStatus.created:
                        item.message = "已新建并订阅 Feed"
                    item.processed_at = now_naive_utc()
                except Exception as exc:
                    item.status = FeedImportItemStatus.failed
                    item.message = safe_import_error_message(exc)
                    item.processed_at = now_naive_utc()

            recompute_job_counts(job)
            db.commit()

        job.status = FeedImportJobStatus.completed
        job.finished_at = now_naive_utc()
        recompute_job_counts(job)
        db.commit()
    except Exception:
        job.status = FeedImportJobStatus.failed
        job.error_message = "导入任务失败"
        job.finished_at = now_naive_utc()
        recompute_job_counts(job)
        db.commit()
        raise
```

- [ ] **Step 4: Replace Celery task stub**

In `apps/api/app/tasks.py`, import the service:

```python
from app.services.feed_import_service import process_feed_import_job
```

Replace the stub:

```python
@celery_app.task(name="feeds.import")
def import_feeds_task(job_id: str) -> None:
    with SessionLocal() as db:
        process_feed_import_job(db, UUID(job_id))
```

- [ ] **Step 5: Add task test**

In `apps/api/tests/test_tasks.py`, extend model imports:

```python
    FeedImportJob,
    FeedImportSourceType,
    User,
```

Extend task imports:

```python
    import_feeds_task,
```

Add this test:

```python
def test_import_feeds_task_processes_job(
    session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    with session_local() as db:
        user = User(email="import-task@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        job = FeedImportJob(
            user_id=user.id,
            source_type=FeedImportSourceType.urls,
            total_count=0,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    calls: list[UUID] = []

    def fake_process(db: Session, received_job_id: UUID) -> None:
        calls.append(received_job_id)

    monkeypatch.setattr("app.tasks.process_feed_import_job", fake_process)

    import_feeds_task(str(job_id))

    assert calls == [job_id]
```

- [ ] **Step 6: Run service and task tests**

Run:

```bash
cd apps/api && uv run --no-sync pytest tests/test_feed_import_service.py tests/test_tasks.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/services/feed_import_service.py apps/api/app/tasks.py apps/api/tests/test_feed_import_service.py apps/api/tests/test_tasks.py
git commit -m "feat(api): process feed import jobs"
```

---

### Task 6: Add Frontend Types, Query Keys, and E2E Coverage

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/query-keys.ts`
- Modify: `apps/web/tests/e2e/feeds.spec.ts`

- [ ] **Step 1: Add frontend types**

In `apps/web/src/lib/api.ts`, add:

```ts
export type FeedImportSourceType = "opml" | "urls";
export type FeedImportJobStatus = "pending" | "processing" | "completed" | "failed";
export type FeedImportItemStatus = "pending" | "created" | "subscribed" | "skipped" | "failed";

export type FeedImportItem = {
  id: string;
  source_title: string | null;
  raw_url: string;
  normalized_url: string;
  dedupe_key: string;
  status: FeedImportItemStatus;
  feed_id: string | null;
  message: string | null;
  created_at: string;
  processed_at: string | null;
};

export type FeedImportJob = {
  id: string;
  source_type: FeedImportSourceType;
  status: FeedImportJobStatus;
  total_count: number;
  processed_count: number;
  created_count: number;
  subscribed_count: number;
  skipped_count: number;
  failed_count: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  items: FeedImportItem[];
};

export type FeedImportCreateRequest =
  | { source_type: "urls"; urls_text: string }
  | { source_type: "opml"; opml_xml: string };
```

- [ ] **Step 2: Add query keys**

In `apps/web/src/lib/query-keys.ts`, extend `queryKeys` with:

```ts
feedImports: {
  all: ["feedImports"] as const,
  detail: (id: string) => ["feedImports", id] as const,
},
```

- [ ] **Step 3: Add failing E2E tests**

In `apps/web/tests/e2e/feeds.spec.ts`, add a helper:

```ts
async function mockEmptyFeeds(page: Page) {
  await page.route("**/api/feeds", async (route) => {
    await route.fulfill({ json: [] });
  });
}
```

Update the first test to use `mockEmptyFeeds(page)`.

Add URL import test:

```ts
test("submits multi-line feed import and displays completed results", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockEmptyFeeds(page);

  await page.route("**/api/feeds/imports", async (route) => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({
        source_type: "urls",
        urls_text: "https://example.com/feed.xml\nhttps://example.com/feed.xml",
      });
      await route.fulfill({
        status: 201,
        json: {
          id: "99999999-9999-9999-9999-999999999999",
          source_type: "urls",
          status: "pending",
          total_count: 2,
          processed_count: 0,
          created_count: 0,
          subscribed_count: 0,
          skipped_count: 0,
          failed_count: 0,
          error_message: null,
          created_at: "2026-06-10T12:00:00",
          started_at: null,
          finished_at: null,
          items: [],
        },
      });
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/feeds/imports/99999999-9999-9999-9999-999999999999", async (route) => {
    await route.fulfill({
      json: {
        id: "99999999-9999-9999-9999-999999999999",
        source_type: "urls",
        status: "completed",
        total_count: 2,
        processed_count: 2,
        created_count: 1,
        subscribed_count: 0,
        skipped_count: 1,
        failed_count: 0,
        error_message: null,
        created_at: "2026-06-10T12:00:00",
        started_at: "2026-06-10T12:00:01",
        finished_at: "2026-06-10T12:00:03",
        items: [
          {
            id: "item-1",
            source_title: null,
            raw_url: "https://example.com/feed.xml",
            normalized_url: "https://example.com/feed.xml",
            dedupe_key: "https://example.com/feed.xml",
            status: "created",
            feed_id: "feed-1",
            message: "已新建并订阅 Feed",
            created_at: "2026-06-10T12:00:00",
            processed_at: "2026-06-10T12:00:02",
          },
          {
            id: "item-2",
            source_title: null,
            raw_url: "https://example.com/feed.xml",
            normalized_url: "https://example.com/feed.xml",
            dedupe_key: "https://example.com/feed.xml",
            status: "skipped",
            feed_id: null,
            message: "同一批导入中已包含该 Feed",
            created_at: "2026-06-10T12:00:00",
            processed_at: "2026-06-10T12:00:03",
          },
        ],
      },
    });
  });

  await page.goto("/feeds");
  await page.getByRole("button", { name: "批量导入" }).click();
  await page.getByLabel("Feed URL 列表").fill("https://example.com/feed.xml\nhttps://example.com/feed.xml");
  await page.getByRole("button", { name: "开始导入" }).click();

  await expect(page.getByText("已处理 2 / 2")).toBeVisible();
  await expect(page.getByText("新建 1")).toBeVisible();
  await expect(page.getByText("跳过 1")).toBeVisible();
  await expect(page.getByText("同一批导入中已包含该 Feed")).toBeVisible();
});
```

Add OPML test:

```ts
test("submits OPML file import", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockEmptyFeeds(page);

  await page.route("**/api/feeds/imports", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      source_type: "opml",
      opml_xml: "<opml><body><outline text=\"Example\" xmlUrl=\"https://example.com/feed.xml\" /></body></opml>",
    });
    await route.fulfill({
      status: 201,
      json: {
        id: "88888888-8888-8888-8888-888888888888",
        source_type: "opml",
        status: "completed",
        total_count: 1,
        processed_count: 1,
        created_count: 1,
        subscribed_count: 0,
        skipped_count: 0,
        failed_count: 0,
        error_message: null,
        created_at: "2026-06-10T12:00:00",
        started_at: "2026-06-10T12:00:01",
        finished_at: "2026-06-10T12:00:03",
        items: [],
      },
    });
  });

  await page.goto("/feeds");
  await page.getByRole("button", { name: "批量导入" }).click();
  await page.getByRole("tab", { name: "OPML 文件" }).click();
  await page.getByLabel("OPML 文件").setInputFiles({
    name: "feeds.opml",
    mimeType: "text/xml",
    buffer: Buffer.from("<opml><body><outline text=\"Example\" xmlUrl=\"https://example.com/feed.xml\" /></body></opml>"),
  });
  await page.getByRole("button", { name: "开始导入" }).click();

  await expect(page.getByText("已处理 1 / 1")).toBeVisible();
});
```

- [ ] **Step 4: Run E2E and verify failure**

Run:

```bash
pnpm --dir apps/web test:e2e -- feeds.spec.ts
```

Expected: FAIL because the UI does not include batch import.

- [ ] **Step 5: Commit tests and types**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/query-keys.ts apps/web/tests/e2e/feeds.spec.ts
git commit -m "test(web): cover feed import workflow"
```

---

### Task 7: Build Feed Import UI

**Files:**
- Modify: `apps/web/src/routes/feeds/list.tsx`

- [ ] **Step 1: Inspect available UI primitives**

Run:

```bash
rg -n "Dialog|Tabs|textarea|localStorage" apps/web/src/components apps/web/src/routes apps/web/src/lib
```

Expected: local dialog/tabs wrappers are identified. When no local dialog/tabs primitive exists, implement the import panel inline below the Feed URL form instead of adding a new dependency.

- [ ] **Step 2: Add imports and constants**

In `apps/web/src/routes/feeds/list.tsx`, extend imports:

```ts
import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react"
import {
  apiDelete,
  apiGet,
  apiPost,
  type Feed,
  type FeedImportCreateRequest,
  type FeedImportJob,
  type FeedImportItemStatus,
} from "@/lib/api"
```

Add constants:

```ts
const CURRENT_IMPORT_STORAGE_KEY = "rsswise.currentFeedImportId"

const itemStatusLabel: Record<FeedImportItemStatus, string> = {
  pending: "等待中",
  created: "新建",
  subscribed: "已订阅",
  skipped: "跳过",
  failed: "失败",
}
```

- [ ] **Step 3: Add import state and query**

Inside `FeedsPage`, add state:

```ts
const [isImportOpen, setIsImportOpen] = useState(false)
const [importMode, setImportMode] = useState<"urls" | "opml">("urls")
const [urlsText, setUrlsText] = useState("")
const [opmlXml, setOpmlXml] = useState("")
const [currentImportId, setCurrentImportId] = useState<string | null>(() =>
  window.localStorage.getItem(CURRENT_IMPORT_STORAGE_KEY),
)
```

Add query:

```ts
const importQuery = useQuery({
  queryKey: currentImportId
    ? queryKeys.feedImports.detail(currentImportId)
    : queryKeys.feedImports.all,
  queryFn: () => apiGet<FeedImportJob>(`/feeds/imports/${currentImportId}`),
  enabled: Boolean(currentImportId),
  refetchInterval: (query) => {
    const status = query.state.data?.status
    return status === "pending" || status === "processing" ? 2000 : false
  },
})
```

Add completion invalidation effect:

```ts
useEffect(() => {
  if (importQuery.data?.status === "completed" || importQuery.data?.status === "failed") {
    queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
    queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
  }
}, [importQuery.data?.status])
```

- [ ] **Step 4: Add create import mutation and file handler**

Add:

```ts
const createImportMutation = useMutation({
  mutationFn: (payload: FeedImportCreateRequest) =>
    apiPost<FeedImportJob>("/feeds/imports", payload),
  onSuccess: (job) => {
    setCurrentImportId(job.id)
    window.localStorage.setItem(CURRENT_IMPORT_STORAGE_KEY, job.id)
    queryClient.setQueryData(queryKeys.feedImports.detail(job.id), job)
  },
})

function handleOpmlFileChange(event: ChangeEvent<HTMLInputElement>) {
  const file = event.target.files?.[0]
  if (!file) return
  file.text().then(setOpmlXml).catch(() => setOpmlXml(""))
}

function handleCreateImport(event: FormEvent<HTMLFormElement>) {
  event.preventDefault()
  const payload: FeedImportCreateRequest =
    importMode === "urls"
      ? { source_type: "urls", urls_text: urlsText.trim() }
      : { source_type: "opml", opml_xml: opmlXml.trim() }
  createImportMutation.mutate(payload)
}

function dismissImportResult() {
  setCurrentImportId(null)
  window.localStorage.removeItem(CURRENT_IMPORT_STORAGE_KEY)
}
```

- [ ] **Step 5: Render the import entry point and panel**

Near the existing add-feed form, add a secondary button:

```tsx
<Button type="button" variant="outline" onClick={() => setIsImportOpen((open) => !open)}>
  批量导入
</Button>
```

Render a panel when `isImportOpen` is true:

```tsx
{isImportOpen ? (
  <form onSubmit={handleCreateImport} className="rounded-lg border bg-card p-4">
    <div className="mb-4 flex gap-2" role="tablist" aria-label="导入方式">
      <Button
        type="button"
        variant={importMode === "urls" ? "default" : "outline"}
        role="tab"
        aria-selected={importMode === "urls"}
        onClick={() => setImportMode("urls")}
      >
        多行 URL
      </Button>
      <Button
        type="button"
        variant={importMode === "opml" ? "default" : "outline"}
        role="tab"
        aria-selected={importMode === "opml"}
        onClick={() => setImportMode("opml")}
      >
        OPML 文件
      </Button>
    </div>

    {importMode === "urls" ? (
      <div className="space-y-2">
        <label className="block text-sm font-medium text-foreground" htmlFor="feed-import-urls">
          Feed URL 列表
        </label>
        <textarea
          id="feed-import-urls"
          className="min-h-36 w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={urlsText}
          onChange={(event) => setUrlsText(event.target.value)}
          placeholder="https://example.com/feed.xml"
        />
      </div>
    ) : (
      <div className="space-y-2">
        <label className="block text-sm font-medium text-foreground" htmlFor="feed-import-opml">
          OPML 文件
        </label>
        <Input
          id="feed-import-opml"
          type="file"
          accept=".opml,.xml,text/xml,application/xml"
          onChange={handleOpmlFileChange}
        />
      </div>
    )}

    <div className="mt-4 flex gap-2">
      <Button
        type="submit"
        loading={createImportMutation.isPending}
        disabled={
          createImportMutation.isPending ||
          (importMode === "urls" ? !urlsText.trim() : !opmlXml.trim())
        }
      >
        开始导入
      </Button>
    </div>
  </form>
) : null}
```

- [ ] **Step 6: Render import progress and item results**

Below mutation errors, add:

```tsx
{importQuery.data ? (
  <div className="rounded-lg border bg-card p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="font-medium text-foreground">导入结果</h2>
        <p className="text-sm text-muted-foreground">
          已处理 {importQuery.data.processed_count} / {importQuery.data.total_count}
        </p>
      </div>
      <Button type="button" variant="outline" size="sm" onClick={dismissImportResult}>
        关闭
      </Button>
    </div>
    <div className="mt-3 flex flex-wrap gap-2 text-sm text-muted-foreground">
      <span>新建 {importQuery.data.created_count}</span>
      <span>已订阅 {importQuery.data.subscribed_count}</span>
      <span>跳过 {importQuery.data.skipped_count}</span>
      <span>失败 {importQuery.data.failed_count}</span>
    </div>
    {importQuery.data.items.length > 0 ? (
      <div className="mt-4 divide-y rounded-md border">
        {importQuery.data.items.map((item) => (
          <div key={item.id} className="flex flex-col gap-1 p-3 text-sm sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="font-medium text-foreground">{item.source_title || item.normalized_url}</p>
              <p className="break-all text-muted-foreground">{item.normalized_url}</p>
              {item.message ? <p className="text-muted-foreground">{item.message}</p> : null}
            </div>
            <span className="shrink-0 rounded border px-2 py-0.5 text-xs text-muted-foreground">
              {itemStatusLabel[item.status]}
            </span>
          </div>
        ))}
      </div>
    ) : null}
  </div>
) : null}
```

- [ ] **Step 7: Surface import errors**

Include `createImportMutation.error` and `importQuery.error` in the existing `mutationError` calculation so API errors appear in the page error banner.

- [ ] **Step 8: Run E2E tests**

Run:

```bash
pnpm --dir apps/web test:e2e -- feeds.spec.ts
```

Expected: PASS.

- [ ] **Step 9: Run frontend build**

Run:

```bash
pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/web/src/routes/feeds/list.tsx
git commit -m "feat(web): add feed import workflow"
```

---

### Task 8: Final Verification and Polish

**Files:**
- Review: all changed files from previous tasks.

- [ ] **Step 1: Run backend tests**

Run:

```bash
make test
```

Expected: PASS.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd apps/api && uv run --no-sync ruff check app tests
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
make web-build
```

Expected: PASS.

- [ ] **Step 4: Run feed E2E**

Run:

```bash
pnpm --dir apps/web test:e2e -- feeds.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Run migration upgrade locally**

With local dev database running, run:

```bash
make db-migrate
```

Expected: Alembic upgrades through `0004_feed_import_jobs`.

- [ ] **Step 6: Inspect final diff**

Run:

```bash
git diff --stat HEAD
git status --short
```

Expected: only intentional RSS import files are changed after the last commit if additional polish was needed.

- [ ] **Step 7: Commit verification fixes when Step 6 shows intentional changes**

If Step 6 shows uncommitted intentional fixes, stage the RSS import implementation files that were part of this plan, then commit:

```bash
git add \
  apps/api/alembic/versions/0004_feed_import_jobs.py \
  apps/api/app/models.py \
  apps/api/app/schemas.py \
  apps/api/app/services/feed_import_service.py \
  apps/api/app/services/feed_service.py \
  apps/api/app/routers/feeds.py \
  apps/api/app/tasks.py \
  apps/api/tests/test_feed_import_service.py \
  apps/api/tests/test_feed_service.py \
  apps/api/tests/test_feeds_api.py \
  apps/api/tests/test_tasks.py \
  apps/web/src/lib/api.ts \
  apps/web/src/lib/query-keys.ts \
  apps/web/src/routes/feeds/list.tsx \
  apps/web/tests/e2e/feeds.spec.ts
git commit -m "fix: polish feed import workflow"
```

Expected: the working tree is clean except unrelated user changes.
