# External Link EPUB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a signed-in RSSWise user select one feed item, parse external article links from it, prepare extraction ahead of the configured send time, and deliver an EPUB that includes full text when available and fallback chapters when not.

**Architecture:** Add external-link collection and item tables that reference the selected source `Article` and normal linked `Article` rows. Keep parsing, collection orchestration, scheduling, EPUB rendering, and API serialization in focused backend services; Celery tasks only open a session and call service functions. On the web side, split article rows into a non-interactive row container with separate select and action controls, then open a coss dialog that previews links and creates the collection.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Celery, Redis broker, PostgreSQL/SQLite tests, lxml, markdown-it-py, ZIP-based EPUB packaging, SMTP email service, React, TanStack Query, React Router, coss/Base UI, Playwright.

**Source Spec:** `docs/superpowers/specs/2026-06-20-external-link-epub-design.md`

---

## File Map

- Modify: `apps/api/app/models.py`  
  Responsibility: add collection/item enums and tables; allow linked external `Article` records with `feed_id=None`.

- Create: `apps/api/alembic/versions/0006_external_link_collections.py`  
  Responsibility: migrate `articles.feed_id` to nullable and create external-link collection/item tables with indexes and unique constraints.

- Modify: `apps/api/tests/test_models.py`  
  Responsibility: assert the new ORM tables and enum values are declared.

- Create: `apps/api/app/services/external_link_parser.py`  
  Responsibility: parse HTML and Markdown links, normalize/filter/dedupe URLs, and report duplicate/filtered counts.

- Create: `apps/api/tests/test_external_link_parser.py`  
  Responsibility: cover source-mode behavior, HTML/Markdown extraction, relative URL resolution, tracking parameter removal, filtering, and stable ordering.

- Create: `apps/api/app/services/external_link_collection_service.py`  
  Responsibility: preview links, create collections, upsert linked articles, enqueue extraction idempotently, compute derived item status, select due collections, prepare due work, and send due collections.

- Create: `apps/api/tests/test_external_link_collection_service.py`  
  Responsibility: cover collection creation, article reuse, extraction enqueue rules, access scoping, preparation idempotency, generation due checks, and email failure status.

- Create: `apps/api/app/services/external_link_epub_service.py`  
  Responsibility: build external-link EPUB front matter and ordered chapters using full text or fallback chapter text.

- Create: `apps/api/tests/test_external_link_epub_service.py`  
  Responsibility: inspect generated EPUB ZIP entries and chapter XHTML for source metadata, counts, ordering, full text, and fallback text.

- Create: `apps/api/app/routers/external_links.py`  
  Responsibility: expose preview, create collection, get collection, retry prepare, and EPUB download endpoints with current-user scoping.

- Modify: `apps/api/app/main.py`  
  Responsibility: include the external-links router.

- Modify: `apps/api/app/schemas.py`  
  Responsibility: add request/response schemas for link preview, collection creation, collection read, and item read.

- Modify: `apps/api/app/tasks.py`  
  Responsibility: register `external_links.prepare_due` and `external_links.generate_due` Celery tasks.

- Modify: `apps/api/app/beat.py` and `apps/api/tests/test_beat.py`  
  Responsibility: schedule prepare and generate polling every five minutes.

- Modify: `apps/api/tests/test_tasks.py`  
  Responsibility: assert new Celery tasks call the service functions.

- Modify: `apps/api/tests/test_articles_api.py` or create `apps/api/tests/test_external_links_api.py`  
  Responsibility: cover authenticated API behavior and user scoping.

- Modify: `apps/web/src/lib/api.ts`  
  Responsibility: add external-link request/response types.

- Modify: `apps/web/src/lib/query-keys.ts`  
  Responsibility: add collection query keys.

- Create: `apps/web/src/components/ui/context-menu.tsx`  
  Responsibility: thin coss-style wrapper around Base UI context menu parts, reusing menu item and popup styling.

- Create: `apps/web/src/routes/articles/external-link-epub-dialog.tsx`  
  Responsibility: controlled dialog for settings, preview, error display, and collection creation.

- Modify: `apps/web/src/routes/articles/workbench.tsx`  
  Responsibility: expose visible row action menu, desktop context menu action, and dialog state without nesting controls inside row buttons.

- Modify: `apps/web/tests/e2e/articles.spec.ts`  
  Responsibility: verify visible row menu, right-click action, preview rendering, creation request, and row selection isolation.

## Locked Decisions

- Linked external pages use normal `Article`, `ArticleContent`, and `ArticleAIAnalysis` rows. New linked rows set `Article.feed_id = None` so they do not appear as feed entries or misrepresent the source feed.
- Existing articles are reused by exact normalized URL via the existing `uq_articles_url` uniqueness rule.
- API authorization for preview/create uses the selected source article's feed subscription. API authorization for collection read/retry/download uses `collection.source_article_id -> source_article.feed_id -> user_feed_subscriptions`.
- Link parsing does not perform network requests. Extraction remains the only network step for target pages.
- External-link delivery reuses `EmailDigestSetting.recipient_email` and SMTP settings. The `enabled` flag for normal digest scheduling does not block external-link delivery; missing recipient fails the collection with `last_error`.
- The first version does not store EPUB bytes. Scheduled send and download both build from the current collection item state.
- `generated_at` records that an EPUB build succeeded during an attempt. `sent_at` is the retry gate for scheduled delivery, because email failure after a successful build still needs a future retry.

---

### Task 1: Collection Schema And Migration

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/alembic/versions/0006_external_link_collections.py`
- Modify: `apps/api/tests/test_models.py`

- [ ] **Step 1: Confirm the working tree**

Run:

```bash
rtk git status --short
```

Expected: the spec and this plan may be untracked. Do not stage or revert unrelated files.

- [ ] **Step 2: Add failing model declarations test**

Append these imports and assertions to `apps/api/tests/test_models.py`:

```python
from app.models import (
    ExternalLinkCollection,
    ExternalLinkCollectionItem,
    ExternalLinkCollectionStatus,
    ExternalLinkItemStatus,
    ExternalLinkSourceMode,
)


def test_external_link_collection_tables_are_declared():
    assert ExternalLinkCollection.__tablename__ == "external_link_collections"
    assert ExternalLinkCollectionItem.__tablename__ == "external_link_collection_items"
    assert [status.value for status in ExternalLinkCollectionStatus] == [
        "collecting",
        "prepared",
        "generated",
        "sent",
        "failed",
    ]
    assert [status.value for status in ExternalLinkItemStatus] == [
        "pending",
        "extracting",
        "success",
        "failed",
        "timed_out",
    ]
    assert [mode.value for mode in ExternalLinkSourceMode] == [
        "auto",
        "summary_from_feed",
        "content_markdown",
    ]
```

- [ ] **Step 3: Run the model test and verify it fails**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_models.py -q
```

Expected: FAIL with an import error for the external-link models or enums.

- [ ] **Step 4: Add models and nullable article feed support**

In `apps/api/app/models.py`, add these enums after `FeedImportItemStatus`:

```python
class ExternalLinkSourceMode(str, enum.Enum):
    auto = "auto"
    summary_from_feed = "summary_from_feed"
    content_markdown = "content_markdown"


class ExternalLinkCollectionStatus(str, enum.Enum):
    collecting = "collecting"
    prepared = "prepared"
    generated = "generated"
    sent = "sent"
    failed = "failed"


class ExternalLinkItemStatus(str, enum.Enum):
    pending = "pending"
    extracting = "extracting"
    success = "success"
    failed = "failed"
    timed_out = "timed_out"
```

Change `Article.feed_id` and `Article.feed` to allow feedless linked articles, then add relationships for source collections and linked items:

```python
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    feed: Mapped[Feed | None] = relationship(back_populates="articles")
    external_link_collections: Mapped[list["ExternalLinkCollection"]] = relationship(
        back_populates="source_article",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ExternalLinkCollection.source_article_id",
    )
    external_link_items: Mapped[list["ExternalLinkCollectionItem"]] = relationship(
        back_populates="article",
        foreign_keys="ExternalLinkCollectionItem.article_id",
    )
```

Add these classes before `EmailDigestSetting`:

```python
class ExternalLinkCollection(Base):
    __tablename__ = "external_link_collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500))
    target_send_date: Mapped[date] = mapped_column(Date(), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    send_time: Mapped[time] = mapped_column(Time(), default=lambda: time(hour=8, minute=0))
    prepare_offset_hours: Mapped[int] = mapped_column(Integer, default=6)
    link_source_mode: Mapped[ExternalLinkSourceMode] = mapped_column(
        Enum(ExternalLinkSourceMode, name="external_link_source_mode"),
        default=ExternalLinkSourceMode.auto,
    )
    status: Mapped[ExternalLinkCollectionStatus] = mapped_column(
        Enum(ExternalLinkCollectionStatus, name="external_link_collection_status"),
        default=ExternalLinkCollectionStatus.collecting,
        index=True,
    )
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    source_article: Mapped[Article] = relationship(
        back_populates="external_link_collections",
        foreign_keys=[source_article_id],
    )
    items: Mapped[list["ExternalLinkCollectionItem"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExternalLinkCollectionItem.position",
    )


class ExternalLinkCollectionItem(Base):
    __tablename__ = "external_link_collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "normalized_url", name="uq_external_link_items_url"),
        UniqueConstraint("collection_id", "position", name="uq_external_link_items_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_link_collections.id", ondelete="CASCADE"),
        index=True,
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String(2000))
    normalized_url: Mapped[str] = mapped_column(String(2000), index=True)
    anchor_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title_hint: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ExternalLinkItemStatus] = mapped_column(
        Enum(ExternalLinkItemStatus, name="external_link_item_status"),
        default=ExternalLinkItemStatus.pending,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    collection: Mapped[ExternalLinkCollection] = relationship(back_populates="items")
    article: Mapped[Article | None] = relationship(
        back_populates="external_link_items",
        foreign_keys=[article_id],
    )
```

- [ ] **Step 5: Add Alembic migration**

Create `apps/api/alembic/versions/0006_external_link_collections.py`:

```python
"""external link collections

Revision ID: 0006_external_link_collections
Revises: 0005_article_ai_analysis_logs
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_external_link_collections"
down_revision: str | None = "0005_article_ai_analysis_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_mode = sa.Enum(
    "auto",
    "summary_from_feed",
    "content_markdown",
    name="external_link_source_mode",
)
collection_status = sa.Enum(
    "collecting",
    "prepared",
    "generated",
    "sent",
    "failed",
    name="external_link_collection_status",
)
item_status = sa.Enum(
    "pending",
    "extracting",
    "success",
    "failed",
    "timed_out",
    name="external_link_item_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    source_mode.create(bind, checkfirst=True)
    collection_status.create(bind, checkfirst=True)
    item_status.create(bind, checkfirst=True)

    op.alter_column("articles", "feed_id", existing_type=sa.Uuid(), nullable=True)

    op.create_table(
        "external_link_collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_article_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("target_send_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("send_time", sa.Time(), nullable=False),
        sa.Column("prepare_offset_hours", sa.Integer(), nullable=False),
        sa.Column("link_source_mode", source_mode, nullable=False),
        sa.Column("status", collection_status, nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_link_collections_source_article_id",
        "external_link_collections",
        ["source_article_id"],
    )
    op.create_index(
        "ix_external_link_collections_target_send_date",
        "external_link_collections",
        ["target_send_date"],
    )
    op.create_index(
        "ix_external_link_collections_status",
        "external_link_collections",
        ["status"],
    )

    op.create_table(
        "external_link_collection_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("normalized_url", sa.String(length=2000), nullable=False),
        sa.Column("anchor_text", sa.String(length=1000), nullable=True),
        sa.Column("title_hint", sa.String(length=1000), nullable=True),
        sa.Column("status", item_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["collection_id"], ["external_link_collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "normalized_url", name="uq_external_link_items_url"),
        sa.UniqueConstraint("collection_id", "position", name="uq_external_link_items_position"),
    )
    op.create_index(
        "ix_external_link_collection_items_collection_id",
        "external_link_collection_items",
        ["collection_id"],
    )
    op.create_index(
        "ix_external_link_collection_items_article_id",
        "external_link_collection_items",
        ["article_id"],
    )
    op.create_index(
        "ix_external_link_collection_items_normalized_url",
        "external_link_collection_items",
        ["normalized_url"],
    )
    op.create_index(
        "ix_external_link_collection_items_status",
        "external_link_collection_items",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_link_collection_items_status", table_name="external_link_collection_items")
    op.drop_index("ix_external_link_collection_items_normalized_url", table_name="external_link_collection_items")
    op.drop_index("ix_external_link_collection_items_article_id", table_name="external_link_collection_items")
    op.drop_index("ix_external_link_collection_items_collection_id", table_name="external_link_collection_items")
    op.drop_table("external_link_collection_items")
    op.drop_index("ix_external_link_collections_status", table_name="external_link_collections")
    op.drop_index("ix_external_link_collections_target_send_date", table_name="external_link_collections")
    op.drop_index("ix_external_link_collections_source_article_id", table_name="external_link_collections")
    op.drop_table("external_link_collections")
    op.alter_column("articles", "feed_id", existing_type=sa.Uuid(), nullable=False)
    item_status.drop(op.get_bind(), checkfirst=True)
    collection_status.drop(op.get_bind(), checkfirst=True)
    source_mode.drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 6: Verify schema tests pass**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit schema slice**

```bash
rtk git add apps/api/app/models.py apps/api/alembic/versions/0006_external_link_collections.py apps/api/tests/test_models.py
rtk git diff --staged
rtk git commit -m "feat(api): add external link collection schema"
```

Expected staged diff: only model, migration, and model test changes.

---

### Task 2: External Link Parser Service

**Files:**
- Create: `apps/api/tests/test_external_link_parser.py`
- Create: `apps/api/app/services/external_link_parser.py`

- [ ] **Step 1: Add parser tests**

Create `apps/api/tests/test_external_link_parser.py` with these tests:

```python
from app.models import ExternalLinkSourceMode
from app.services.external_link_parser import parse_external_links


def test_parse_html_links_prefers_feed_summary_and_dedupes_tracking_params():
    result = parse_external_links(
        source_url="https://newsletter.example.com/issues/42?utm_source=email#top",
        summary_from_feed="""
        <p>
          <a href="/posts/a?utm_source=newsletter&id=1#comments">First</a>
          <a href="https://example.com/posts/a?id=1&utm_medium=rss">Duplicate</a>
          <a href="mailto:editor@example.com">Mail</a>
          <a href="https://example.com/image.jpg">Image</a>
        </p>
        """,
        content_markdown="[Markdown only](https://example.com/markdown)",
        mode=ExternalLinkSourceMode.summary_from_feed,
    )

    assert [(link.position, link.anchor_text, link.normalized_url) for link in result.links] == [
        (1, "First", "https://newsletter.example.com/posts/a?id=1"),
        (2, "Duplicate", "https://example.com/posts/a?id=1"),
    ]
    assert result.filtered_count == 2
    assert result.duplicate_count == 0


def test_parse_auto_combines_summary_then_markdown_and_dedupes_by_normalized_url():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed='<a href="https://target.example.com/read?utm_campaign=x">HTML Target</a>',
        content_markdown="[Markdown Target](https://target.example.com/read)",
        mode=ExternalLinkSourceMode.auto,
    )

    assert len(result.links) == 1
    assert result.links[0].anchor_text == "HTML Target"
    assert result.links[0].normalized_url == "https://target.example.com/read"
    assert result.duplicate_count == 1


def test_parse_markdown_links_keeps_source_order_and_excludes_source_url():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed=None,
        content_markdown=(
            "[Self](https://example.com/source#part)\n\n"
            "[First](https://a.example.com/post)\n\n"
            "[Second `code`](https://b.example.com/post?utm_source=rss&x=1)"
        ),
        mode=ExternalLinkSourceMode.content_markdown,
    )

    assert [(link.position, link.anchor_text, link.normalized_url) for link in result.links] == [
        (1, "First", "https://a.example.com/post"),
        (2, "Second code", "https://b.example.com/post?x=1"),
    ]
    assert result.filtered_count == 1


def test_parse_ignores_feed_and_document_urls():
    result = parse_external_links(
        source_url="https://example.com/source",
        summary_from_feed="""
        <a href="https://example.com/feed.xml">Feed</a>
        <a href="https://example.com/atom">Atom</a>
        <a href="https://example.com/report.pdf">PDF</a>
        <a href="https://example.com/readable">Readable</a>
        """,
        content_markdown=None,
        mode=ExternalLinkSourceMode.auto,
    )

    assert [link.normalized_url for link in result.links] == ["https://example.com/readable"]
    assert result.filtered_count == 3
```

- [ ] **Step 2: Run parser tests and verify missing module failure**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_parser.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.external_link_parser'`.

- [ ] **Step 3: Implement parser**

Create `apps/api/app/services/external_link_parser.py`:

```python
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html
from markdown_it import MarkdownIt

from app.models import ExternalLinkSourceMode

MARKDOWN_LINK_PARSER = MarkdownIt("commonmark", {"html": False})
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"fbclid", "gclid", "mc_cid", "mc_eid"}
EXCLUDED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".doc",
    ".docx",
    ".epub",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".tar",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
FEED_PATH_HINTS = ("/feed", "/rss", "/atom")


@dataclass(frozen=True)
class ParsedExternalLink:
    url: str
    normalized_url: str
    anchor_text: str | None
    position: int


@dataclass(frozen=True)
class ExternalLinkParseResult:
    links: list[ParsedExternalLink]
    filtered_count: int
    duplicate_count: int


@dataclass(frozen=True)
class CandidateLink:
    url: str
    anchor_text: str | None


def normalize_external_url(url: str, *, base_url: str) -> str | None:
    raw = url.strip()
    if not raw:
        return None

    absolute = urljoin(base_url, raw)
    parsed = urlsplit(absolute)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None

    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
        return None
    if path_lower in FEED_PATH_HINTS or any(path_lower.endswith(f"{hint}.xml") for hint in FEED_PATH_HINTS):
        return None
    if path_lower.endswith(("/rss.xml", "/atom.xml", "/feed.xml")):
        return None

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_NAMES
        and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    query = urlencode(query_pairs, doseq=True)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=query,
        fragment="",
    )
    return urlunsplit(normalized)


def _text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def extract_html_links(html: str | None) -> list[CandidateLink]:
    if not html:
        return []
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return []
    links: list[CandidateLink] = []
    for node in root.xpath("//a[@href]"):
        href = node.get("href")
        if not href:
            continue
        links.append(CandidateLink(url=href, anchor_text=_text_or_none(node.text_content())))
    return links


def _inline_link_text(children: list, start_index: int) -> str | None:
    parts: list[str] = []
    for child in children[start_index + 1 :]:
        if child.type == "link_close":
            break
        if child.type in {"text", "code_inline"} and child.content:
            parts.append(child.content)
        elif child.children:
            nested = _inline_link_text(child.children, -1)
            if nested:
                parts.append(nested)
    return _text_or_none(" ".join(parts))


def extract_markdown_links(markdown: str | None) -> list[CandidateLink]:
    if not markdown:
        return []
    links: list[CandidateLink] = []
    for token in MARKDOWN_LINK_PARSER.parse(markdown):
        children = token.children or []
        for index, child in enumerate(children):
            if child.type != "link_open":
                continue
            href = child.attrGet("href")
            if not href:
                continue
            links.append(
                CandidateLink(
                    url=href,
                    anchor_text=_inline_link_text(children, index),
                )
            )
    return links


def parse_external_links(
    *,
    source_url: str,
    summary_from_feed: str | None,
    content_markdown: str | None,
    mode: ExternalLinkSourceMode,
) -> ExternalLinkParseResult:
    candidates: list[CandidateLink] = []
    if mode in {ExternalLinkSourceMode.auto, ExternalLinkSourceMode.summary_from_feed}:
        candidates.extend(extract_html_links(summary_from_feed))
    if mode in {ExternalLinkSourceMode.auto, ExternalLinkSourceMode.content_markdown}:
        candidates.extend(extract_markdown_links(content_markdown))

    source_normalized = normalize_external_url(source_url, base_url=source_url)
    seen: set[str] = set()
    links: list[ParsedExternalLink] = []
    filtered_count = 0
    duplicate_count = 0

    for candidate in candidates:
        normalized_url = normalize_external_url(candidate.url, base_url=source_url)
        if normalized_url is None or normalized_url == source_normalized:
            filtered_count += 1
            continue
        if normalized_url in seen:
            duplicate_count += 1
            continue
        seen.add(normalized_url)
        links.append(
            ParsedExternalLink(
                url=urljoin(source_url, candidate.url.strip()),
                normalized_url=normalized_url,
                anchor_text=candidate.anchor_text,
                position=len(links) + 1,
            )
        )

    return ExternalLinkParseResult(
        links=links,
        filtered_count=filtered_count,
        duplicate_count=duplicate_count,
    )
```

- [ ] **Step 4: Verify parser tests pass**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_parser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit parser slice**

```bash
rtk git add apps/api/app/services/external_link_parser.py apps/api/tests/test_external_link_parser.py
rtk git diff --staged
rtk git commit -m "feat(api): parse external links from articles"
```

Expected staged diff: only parser service and parser tests.

---

### Task 3: Collection Service

**Files:**
- Create: `apps/api/tests/test_external_link_collection_service.py`
- Create: `apps/api/app/services/external_link_collection_service.py`

- [ ] **Step 1: Add collection service tests**

Create `apps/api/tests/test_external_link_collection_service.py` with focused tests for creation, article reuse, extraction enqueue, and prepare idempotency:

```python
from collections.abc import Iterator
from datetime import date, datetime, time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    Base,
    ExternalLinkCollection,
    ExternalLinkCollectionStatus,
    ExternalLinkItemStatus,
    ExternalLinkSourceMode,
    ExtractionStatus,
    Feed,
    User,
    UserFeedSubscription,
)
from app.services.external_link_collection_service import (
    create_external_link_collection,
    external_link_collection_for_user,
    preview_external_links,
    prepare_external_link_collection,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with session_local() as db:
        yield db
    Base.metadata.drop_all(bind=engine)


def seed_user_source_article(db: Session) -> tuple[User, Article]:
    user = User(id=uuid4(), email="reader@example.com", password_hash="hash")
    feed = Feed(title="Weekly Feed", url="https://example.com/feed.xml")
    source = Article(
        feed=feed,
        title="Weekly Picks",
        url="https://example.com/issues/1",
        summary_from_feed=(
            '<a href="https://target.example.com/a?utm_source=rss">Target A</a>'
            '<a href="https://target.example.com/b">Target B</a>'
        ),
    )
    db.add_all([user, feed, source])
    db.flush()
    db.add(UserFeedSubscription(user_id=user.id, feed_id=feed.id))
    db.add(ArticleContent(article_id=source.id, extraction_status=ExtractionStatus.success))
    db.add(ArticleAIAnalysis(article_id=source.id))
    db.commit()
    return user, source


def test_preview_external_links_requires_subscribed_source_article(db_session: Session):
    user, source = seed_user_source_article(db_session)

    result = preview_external_links(
        db_session,
        user,
        source.id,
        ExternalLinkSourceMode.auto,
    )

    assert result.source_article.id == source.id
    assert [link.normalized_url for link in result.parse_result.links] == [
        "https://target.example.com/a",
        "https://target.example.com/b",
    ]


def test_create_collection_creates_items_and_feedless_articles(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    user, source = seed_user_source_article(db_session)
    queued: list[str] = []
    monkeypatch.setattr(
        "app.services.external_link_collection_service.enqueue_article_extraction",
        lambda article_id: queued.append(str(article_id)),
    )

    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks EPUB",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )

    assert collection.status == ExternalLinkCollectionStatus.collecting
    assert collection.source_article_id == source.id
    assert [item.position for item in collection.items] == [1, 2]
    assert [item.status for item in collection.items] == [
        ExternalLinkItemStatus.extracting,
        ExternalLinkItemStatus.extracting,
    ]
    linked_articles = [item.article for item in collection.items]
    assert all(article is not None and article.feed_id is None for article in linked_articles)
    assert len(queued) == 2


def test_create_collection_reuses_existing_article_and_skips_successful_extraction(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    user, source = seed_user_source_article(db_session)
    existing = Article(
        feed_id=None,
        title="Existing Target",
        url="https://target.example.com/a",
    )
    db_session.add(existing)
    db_session.flush()
    db_session.add(
        ArticleContent(
            article_id=existing.id,
            content_markdown="Already extracted",
            extraction_status=ExtractionStatus.success,
        )
    )
    db_session.add(ArticleAIAnalysis(article_id=existing.id))
    db_session.commit()
    queued: list[str] = []
    monkeypatch.setattr(
        "app.services.external_link_collection_service.enqueue_article_extraction",
        lambda article_id: queued.append(str(article_id)),
    )

    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks EPUB",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )

    assert collection.items[0].article_id == existing.id
    assert collection.items[0].status == ExternalLinkItemStatus.success
    assert str(existing.id) not in queued
    assert len(queued) == 1


def test_prepare_collection_is_idempotent(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    user, source = seed_user_source_article(db_session)
    queued: list[str] = []
    monkeypatch.setattr(
        "app.services.external_link_collection_service.enqueue_article_extraction",
        lambda article_id: queued.append(str(article_id)),
    )
    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks EPUB",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )
    queued.clear()

    prepare_external_link_collection(db_session, collection.id, now=datetime(2026, 6, 21, 2, 0))
    prepare_external_link_collection(db_session, collection.id, now=datetime(2026, 6, 21, 2, 1))

    refreshed = db_session.execute(select(ExternalLinkCollection)).scalar_one()
    assert refreshed.status == ExternalLinkCollectionStatus.prepared
    assert len(refreshed.items) == 2
    assert queued == [str(item.article_id) for item in refreshed.items]


def test_collection_lookup_is_scoped_to_source_feed_subscription(db_session: Session):
    user, source = seed_user_source_article(db_session)
    other_user = User(id=UUID("99999999-9999-9999-9999-999999999999"), email="other@example.com", password_hash="hash")
    db_session.add(other_user)
    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks EPUB",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )

    assert external_link_collection_for_user(db_session, user, collection.id).id == collection.id
    with pytest.raises(ValueError, match="collection not found"):
        external_link_collection_for_user(db_session, other_user, collection.id)
```

- [ ] **Step 2: Run collection service tests and verify missing module failure**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_collection_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.external_link_collection_service'`.

- [ ] **Step 3: Implement collection service public interfaces**

Create `apps/api/app/services/external_link_collection_service.py` with these public dataclasses and functions. Keep the helper names exactly as shown so later router and task steps can import them:

```python
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    ExternalLinkCollection,
    ExternalLinkCollectionItem,
    ExternalLinkCollectionStatus,
    ExternalLinkItemStatus,
    ExternalLinkSourceMode,
    ExtractionStatus,
    User,
    UserFeedSubscription,
    utcnow,
)
from app.services.email_digest_settings_service import EMAIL_DIGEST_TIMEZONE
from app.services.external_link_parser import ExternalLinkParseResult, ParsedExternalLink, parse_external_links


@dataclass(frozen=True)
class ExternalLinkPreview:
    source_article: Article
    parse_result: ExternalLinkParseResult


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def source_article_for_user(db: Session, user: User, article_id: UUID) -> Article:
    article = db.execute(
        select(Article)
        .join(UserFeedSubscription, UserFeedSubscription.feed_id == Article.feed_id)
        .where(Article.id == article_id, UserFeedSubscription.user_id == user.id)
        .options(joinedload(Article.content), joinedload(Article.feed))
    ).scalar_one_or_none()
    if article is None:
        raise ValueError("article not found")
    return article


def external_link_collection_for_user(
    db: Session,
    user: User,
    collection_id: UUID,
) -> ExternalLinkCollection:
    collection = db.execute(
        select(ExternalLinkCollection)
        .join(Article, Article.id == ExternalLinkCollection.source_article_id)
        .join(UserFeedSubscription, UserFeedSubscription.feed_id == Article.feed_id)
        .where(
            ExternalLinkCollection.id == collection_id,
            UserFeedSubscription.user_id == user.id,
        )
        .options(
            joinedload(ExternalLinkCollection.source_article).joinedload(Article.feed),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.content),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.ai_analysis),
        )
    ).scalar_one_or_none()
    if collection is None:
        raise ValueError("collection not found")
    return collection


def preview_external_links(
    db: Session,
    user: User,
    source_article_id: UUID,
    mode: ExternalLinkSourceMode,
) -> ExternalLinkPreview:
    source_article = source_article_for_user(db, user, source_article_id)
    parse_result = parse_external_links(
        source_url=source_article.url,
        summary_from_feed=source_article.summary_from_feed,
        content_markdown=source_article.content.content_markdown if source_article.content else None,
        mode=mode,
    )
    return ExternalLinkPreview(source_article=source_article, parse_result=parse_result)


def enqueue_article_extraction(article_id: UUID) -> None:
    from app.tasks import extract_article_task

    extract_article_task.delay(str(article_id))


def derived_item_status(item: ExternalLinkCollectionItem) -> ExternalLinkItemStatus:
    article = item.article
    if article is None or article.content is None:
        return item.status
    if article.content.extraction_status == ExtractionStatus.success and article.content.content_markdown:
        return ExternalLinkItemStatus.success
    if article.content.extraction_status == ExtractionStatus.failed:
        return ExternalLinkItemStatus.failed
    if article.content.extraction_status == ExtractionStatus.processing:
        return ExternalLinkItemStatus.extracting
    return ExternalLinkItemStatus.pending


def should_enqueue_extraction(article: Article) -> bool:
    content = article.content
    if content is None:
        return True
    if content.extraction_status == ExtractionStatus.success and content.content_markdown:
        return False
    return content.extraction_status in {
        ExtractionStatus.pending,
        ExtractionStatus.failed,
    }


def upsert_external_article(db: Session, link: ParsedExternalLink) -> Article:
    article = db.execute(select(Article).where(Article.url == link.normalized_url)).scalar_one_or_none()
    if article is None:
        article = Article(
            feed_id=None,
            title=link.anchor_text or link.normalized_url,
            url=link.normalized_url,
            summary_from_feed=None,
        )
        db.add(article)
        db.flush()
    if article.content is None:
        article.content = ArticleContent(article_id=article.id)
    if article.ai_analysis is None:
        article.ai_analysis = ArticleAIAnalysis(article_id=article.id)
    return article
```

Add creation and preparation functions below the helpers:

```python
def create_external_link_collection(
    db: Session,
    user: User,
    source_article_id: UUID,
    *,
    title: str,
    target_send_date: date,
    send_time: time,
    prepare_offset_hours: int,
    link_source_mode: ExternalLinkSourceMode,
) -> ExternalLinkCollection:
    preview = preview_external_links(db, user, source_article_id, link_source_mode)
    if not preview.parse_result.links:
        raise ValueError("no external links found")

    collection = ExternalLinkCollection(
        source_article_id=preview.source_article.id,
        title=title.strip() or preview.source_article.title,
        target_send_date=target_send_date,
        timezone=EMAIL_DIGEST_TIMEZONE,
        send_time=send_time,
        prepare_offset_hours=prepare_offset_hours,
        link_source_mode=link_source_mode,
        status=ExternalLinkCollectionStatus.collecting,
    )
    db.add(collection)
    db.flush()

    queued_article_ids: list[UUID] = []
    for link in preview.parse_result.links:
        article = upsert_external_article(db, link)
        item = ExternalLinkCollectionItem(
            collection_id=collection.id,
            article_id=article.id,
            position=link.position,
            source_url=link.url,
            normalized_url=link.normalized_url,
            anchor_text=link.anchor_text,
            title_hint=link.anchor_text,
        )
        item.article = article
        if should_enqueue_extraction(article):
            item.status = ExternalLinkItemStatus.extracting
            queued_article_ids.append(article.id)
        else:
            item.status = ExternalLinkItemStatus.success
        db.add(item)

    db.commit()
    db.refresh(collection)
    for article_id in queued_article_ids:
        enqueue_article_extraction(article_id)
    return external_link_collection_by_id(db, collection.id)


def external_link_collection_by_id(db: Session, collection_id: UUID) -> ExternalLinkCollection:
    return db.execute(
        select(ExternalLinkCollection)
        .where(ExternalLinkCollection.id == collection_id)
        .options(
            joinedload(ExternalLinkCollection.source_article).joinedload(Article.feed),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.content),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.ai_analysis),
        )
    ).scalar_one()


def prepare_external_link_collection(
    db: Session,
    collection_id: UUID,
    *,
    now: datetime | None = None,
) -> ExternalLinkCollection:
    collection = external_link_collection_by_id(db, collection_id)
    source = collection.source_article
    parse_result = parse_external_links(
        source_url=source.url,
        summary_from_feed=source.summary_from_feed,
        content_markdown=source.content.content_markdown if source.content else None,
        mode=collection.link_source_mode,
    )
    if not parse_result.links:
        collection.status = ExternalLinkCollectionStatus.failed
        collection.last_error = "no external links found"
        db.commit()
        return external_link_collection_by_id(db, collection.id)

    existing_by_url = {item.normalized_url: item for item in collection.items}
    queued_article_ids: list[UUID] = []

    for link in parse_result.links:
        item = existing_by_url.get(link.normalized_url)
        article = item.article if item and item.article else upsert_external_article(db, link)
        if item is None:
            item = ExternalLinkCollectionItem(
                collection_id=collection.id,
                article_id=article.id,
                position=link.position,
                source_url=link.url,
                normalized_url=link.normalized_url,
                anchor_text=link.anchor_text,
                title_hint=link.anchor_text,
            )
            db.add(item)
        item.article = article
        item.position = link.position
        item.source_url = link.url
        item.anchor_text = link.anchor_text
        item.title_hint = link.anchor_text
        if should_enqueue_extraction(article):
            item.status = ExternalLinkItemStatus.extracting
            queued_article_ids.append(article.id)
        else:
            item.status = ExternalLinkItemStatus.success

    collection.status = ExternalLinkCollectionStatus.prepared
    collection.prepared_at = now or now_utc_naive()
    collection.last_error = None
    db.commit()

    for article_id in dict.fromkeys(queued_article_ids):
        enqueue_article_extraction(article_id)
    return external_link_collection_by_id(db, collection.id)
```

Add due-selection helpers:

```python
def collection_local_now(collection: ExternalLinkCollection, now: datetime | None = None) -> datetime:
    tz = ZoneInfo(collection.timezone or EMAIL_DIGEST_TIMEZONE)
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        return current.replace(tzinfo=tz)
    return current.astimezone(tz)


def prepare_due_at(collection: ExternalLinkCollection) -> datetime:
    tz = ZoneInfo(collection.timezone or EMAIL_DIGEST_TIMEZONE)
    send_at = datetime.combine(collection.target_send_date, collection.send_time, tzinfo=tz)
    return send_at - timedelta(hours=collection.prepare_offset_hours)


def should_prepare_collection(collection: ExternalLinkCollection, *, now: datetime | None = None) -> bool:
    if collection.sent_at is not None or collection.generated_at is not None:
        return False
    current = collection_local_now(collection, now)
    if collection.target_send_date > current.date():
        return False
    if current < prepare_due_at(collection):
        return False
    if collection.prepared_at is not None:
        prepared_local = collection.prepared_at.replace(tzinfo=UTC).astimezone(current.tzinfo)
        if prepared_local.date() == collection.target_send_date:
            return False
    return collection.status != ExternalLinkCollectionStatus.failed


def list_prepare_due_collections(db: Session, *, now: datetime | None = None) -> list[ExternalLinkCollection]:
    candidates = db.execute(
        select(ExternalLinkCollection)
        .where(
            ExternalLinkCollection.sent_at.is_(None),
            ExternalLinkCollection.generated_at.is_(None),
        )
        .options(joinedload(ExternalLinkCollection.source_article).joinedload(Article.content))
    ).unique().scalars().all()
    return [collection for collection in candidates if should_prepare_collection(collection, now=now)]
```

- [ ] **Step 4: Verify collection service tests**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_collection_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit collection slice**

```bash
rtk git add apps/api/app/services/external_link_collection_service.py apps/api/tests/test_external_link_collection_service.py
rtk git diff --staged
rtk git commit -m "feat(api): create external link collections"
```

Expected staged diff: only collection service and collection service tests.

---

### Task 4: External Link EPUB Rendering And Delivery

**Files:**
- Create: `apps/api/tests/test_external_link_epub_service.py`
- Create: `apps/api/app/services/external_link_epub_service.py`
- Modify: `apps/api/tests/test_external_link_collection_service.py`
- Modify: `apps/api/app/services/external_link_collection_service.py`

- [ ] **Step 1: Add EPUB rendering tests**

Create `apps/api/tests/test_external_link_epub_service.py`:

```python
from datetime import date, datetime, time
from io import BytesIO
from uuid import uuid4
import zipfile

from app.models import (
    Article,
    ArticleAIAnalysis,
    ArticleContent,
    ExternalLinkCollection,
    ExternalLinkCollectionItem,
    ExternalLinkCollectionStatus,
    ExternalLinkItemStatus,
    ExtractionStatus,
    Feed,
)
from app.services.external_link_epub_service import build_external_link_epub


def make_collection() -> ExternalLinkCollection:
    feed = Feed(id=uuid4(), title="Weekly Feed", url="https://example.com/feed.xml")
    source = Article(
        id=uuid4(),
        feed=feed,
        title="Weekly Picks",
        url="https://example.com/issues/1",
        created_at=datetime(2026, 6, 20, 1, 0),
    )
    success_article = Article(
        id=uuid4(),
        feed_id=None,
        title="Target A",
        url="https://target.example.com/a",
        created_at=datetime(2026, 6, 20, 1, 1),
    )
    success_article.content = ArticleContent(
        article_id=success_article.id,
        content_markdown="正文 A",
        extraction_status=ExtractionStatus.success,
    )
    success_article.ai_analysis = ArticleAIAnalysis(article_id=success_article.id)
    failed_article = Article(
        id=uuid4(),
        feed_id=None,
        title="Target B",
        url="https://target.example.com/b",
        created_at=datetime(2026, 6, 20, 1, 2),
    )
    failed_article.content = ArticleContent(
        article_id=failed_article.id,
        extraction_status=ExtractionStatus.failed,
    )
    processing_article = Article(
        id=uuid4(),
        feed_id=None,
        title="Target C",
        url="https://target.example.com/c",
        created_at=datetime(2026, 6, 20, 1, 3),
    )
    processing_article.content = ArticleContent(
        article_id=processing_article.id,
        extraction_status=ExtractionStatus.processing,
    )
    collection = ExternalLinkCollection(
        id=uuid4(),
        source_article=source,
        title="Weekly Picks EPUB",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        status=ExternalLinkCollectionStatus.prepared,
    )
    collection.items = [
        ExternalLinkCollectionItem(
            id=uuid4(),
            collection=collection,
            article=success_article,
            position=1,
            source_url=success_article.url,
            normalized_url=success_article.url,
            anchor_text="Target A",
            status=ExternalLinkItemStatus.success,
        ),
        ExternalLinkCollectionItem(
            id=uuid4(),
            collection=collection,
            article=failed_article,
            position=2,
            source_url=failed_article.url,
            normalized_url=failed_article.url,
            anchor_text="Target B",
            status=ExternalLinkItemStatus.failed,
            error_message="article extraction returned no markdown",
        ),
        ExternalLinkCollectionItem(
            id=uuid4(),
            collection=collection,
            article=processing_article,
            position=3,
            source_url=processing_article.url,
            normalized_url=processing_article.url,
            anchor_text="Target C",
            status=ExternalLinkItemStatus.extracting,
        ),
    ]
    return collection


def test_external_link_epub_has_front_matter_counts_and_ordered_chapters():
    epub = build_external_link_epub(make_collection())

    with zipfile.ZipFile(BytesIO(epub)) as archive:
        front = archive.read("OEBPS/front-matter.xhtml").decode()
        first = archive.read("OEBPS/chapters/article-001.xhtml").decode()
        second = archive.read("OEBPS/chapters/article-002.xhtml").decode()
        third = archive.read("OEBPS/chapters/article-003.xhtml").decode()
        nav = archive.read("OEBPS/nav.xhtml").decode()

    assert "Weekly Picks" in front
    assert "https://example.com/issues/1" in front
    assert "2026-06-21" in front
    assert "链接总数：3" in front
    assert "收入全文：1" in front
    assert "占位章节：2" in front
    assert "正文 A" in first
    assert "正文抓取失败，未收入全文。" in second
    assert "失败原因：article extraction returned no markdown" in second
    assert "到生成时间时正文仍未抓取完成，未收入全文。" in third
    assert nav.index("Target A") < nav.index("Target B") < nav.index("Target C")
```

- [ ] **Step 2: Run EPUB tests and verify missing module failure**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_epub_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.external_link_epub_service'`.

- [ ] **Step 3: Implement external-link EPUB service**

Create `apps/api/app/services/external_link_epub_service.py`. Reuse packaging constants and helpers from `epub_service.py`; keep collection-specific front matter and fallback chapters here:

```python
from html import escape
from textwrap import dedent
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile
from io import BytesIO

from app.models import ExternalLinkCollection, ExternalLinkCollectionItem, ExtractionStatus
from app.services.epub_service import (
    _write_file,
    ai_summary_xhtml,
    article_chapter_xhtml,
    markdown_to_xhtml,
)


def _ordered_items(collection: ExternalLinkCollection) -> list[ExternalLinkCollectionItem]:
    return sorted(collection.items, key=lambda item: item.position)


def item_has_full_text(item: ExternalLinkCollectionItem) -> bool:
    article = item.article
    if article is None or article.content is None:
        return False
    return (
        article.content.extraction_status == ExtractionStatus.success
        and bool(article.content.content_markdown and article.content.content_markdown.strip())
    )


def item_title(item: ExternalLinkCollectionItem) -> str:
    if item.article is not None and item.article.title:
        return item.article.title
    return item.title_hint or item.anchor_text or item.normalized_url


def placeholder_reason(item: ExternalLinkCollectionItem) -> str:
    article = item.article
    if article is not None and article.content is not None:
        if article.content.extraction_status == ExtractionStatus.failed:
            base = "正文抓取失败，未收入全文。"
            if item.error_message:
                return f"{base}\n\n失败原因：{item.error_message}"
            return base
    return "到生成时间时正文仍未抓取完成，未收入全文。"


def placeholder_chapter_xhtml(item: ExternalLinkCollectionItem, index: int) -> str:
    title = item_title(item)
    url = item.normalized_url
    body = markdown_to_xhtml(f"{placeholder_reason(item)}\n\n原文链接：{url}")
    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>{escape(title)}</title>
            <meta charset="utf-8" />
          </head>
          <body>
            <h1>{escape(title)}</h1>
            <p><strong>链接：</strong><a href="{escape(url)}">{escape(url)}</a></p>
            {body}
          </body>
        </html>
        """
    )


def external_link_chapter_xhtml(item: ExternalLinkCollectionItem, index: int) -> str:
    if item_has_full_text(item) and item.article is not None:
        return article_chapter_xhtml(item.article, index)
    return placeholder_chapter_xhtml(item, index)


def front_matter_xhtml(collection: ExternalLinkCollection) -> str:
    items = _ordered_items(collection)
    full_text_count = sum(1 for item in items if item_has_full_text(item))
    placeholder_count = len(items) - full_text_count
    source = collection.source_article
    return dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head>
            <title>{escape(collection.title)}</title>
            <meta charset="utf-8" />
          </head>
          <body>
            <h1>{escape(collection.title)}</h1>
            <p><strong>来源条目：</strong>{escape(source.title)}</p>
            <p><strong>来源链接：</strong><a href="{escape(source.url)}">{escape(source.url)}</a></p>
            <p><strong>发送日期：</strong>{collection.target_send_date.isoformat()}</p>
            <ul>
              <li>链接总数：{len(items)}</li>
              <li>收入全文：{full_text_count}</li>
              <li>占位章节：{placeholder_count}</li>
            </ul>
          </body>
        </html>
        """
    )


def _identifier(collection: ExternalLinkCollection) -> str:
    keys = "|".join(item.normalized_url for item in _ordered_items(collection))
    source = f"rsswise:external-links:{collection.id}:{collection.target_send_date}:{keys}"
    return f"urn:uuid:{uuid5(NAMESPACE_URL, source)}"


def build_external_link_epub(collection: ExternalLinkCollection) -> bytes:
    items = _ordered_items(collection)
    identifier = _identifier(collection)
    title = f"RSSWise External Links - {collection.target_send_date.isoformat()}"
    chapter_manifest = "\n".join(
        f'<item id="article-{index:03d}" href="chapters/article-{index:03d}.xhtml" media-type="application/xhtml+xml" />'
        for index, _ in enumerate(items, start=1)
    )
    spine_items = "\n".join(
        f'<itemref idref="article-{index:03d}" />'
        for index, _ in enumerate(items, start=1)
    )
    nav_items = "\n".join(
        f'<li><a href="chapters/article-{index:03d}.xhtml">{escape(item_title(item))}</a></li>'
        for index, item in enumerate(items, start=1)
    )
    content_opf = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:identifier id="book-id">{identifier}</dc:identifier>
            <dc:title>{escape(title)}</dc:title>
            <dc:language>zh-CN</dc:language>
            <dc:creator>RSSWise</dc:creator>
          </metadata>
          <manifest>
            <item id="front-matter" href="front-matter.xhtml" media-type="application/xhtml+xml" />
            <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
            {chapter_manifest}
          </manifest>
          <spine>
            <itemref idref="front-matter" />
            {spine_items}
          </spine>
        </package>
        """
    )
    nav_xhtml = dedent(
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">
          <head><title>{escape(title)}</title></head>
          <body>
            <nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">
              <h1>{escape(collection.title)}</h1>
              <ol>{nav_items}</ol>
            </nav>
          </body>
        </html>
        """
    )

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        _write_file(archive, "mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        _write_file(
            archive,
            "META-INF/container.xml",
            dedent(
                """\
                <?xml version="1.0" encoding="utf-8"?>
                <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
                  </rootfiles>
                </container>
                """
            ),
            compress_type=ZIP_DEFLATED,
        )
        _write_file(archive, "OEBPS/content.opf", content_opf, compress_type=ZIP_DEFLATED)
        _write_file(archive, "OEBPS/front-matter.xhtml", front_matter_xhtml(collection), compress_type=ZIP_DEFLATED)
        _write_file(archive, "OEBPS/nav.xhtml", nav_xhtml, compress_type=ZIP_DEFLATED)
        for index, item in enumerate(items, start=1):
            _write_file(
                archive,
                f"OEBPS/chapters/article-{index:03d}.xhtml",
                external_link_chapter_xhtml(item, index),
                compress_type=ZIP_DEFLATED,
            )
    return output.getvalue()
```

- [ ] **Step 4: Add generation and email tests**

Append tests to `apps/api/tests/test_external_link_collection_service.py` for due generation:

```python
from app.models import EmailDigestSetting
from app.services.external_link_collection_service import (
    external_link_epub_filename,
    run_due_external_link_generation,
)


def test_external_link_epub_filename_includes_date_and_slug():
    assert external_link_epub_filename("Weekly Reading Picks", date(2026, 6, 21)) == (
        "RSSWise-External-Links-2026-06-21-weekly-reading-picks.epub"
    )


def test_run_due_generation_sends_epub_and_marks_sent(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    user, source = seed_user_source_article(db_session)
    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )
    db_session.add(
        EmailDigestSetting(
            id=1,
            recipient_email="reader@example.com",
            enabled=False,
            send_time=time(hour=8),
        )
    )
    db_session.commit()
    sent: list[dict] = []
    monkeypatch.setattr(
        "app.services.external_link_collection_service.build_external_link_epub",
        lambda collection: b"epub-bytes",
    )
    monkeypatch.setattr(
        "app.services.external_link_collection_service.send_email",
        lambda **kwargs: sent.append(kwargs),
    )

    result = run_due_external_link_generation(
        db_session,
        now=datetime(2026, 6, 21, 8, 0),
    )

    db_session.refresh(collection)
    assert result == "sent:1"
    assert collection.status == ExternalLinkCollectionStatus.sent
    assert collection.generated_at is not None
    assert collection.sent_at is not None
    assert sent[0]["subject"] == "RSSWise 外链文章合集 - 2026-06-21"
    assert sent[0]["to_email"] == "reader@example.com"


def test_run_due_generation_fails_without_recipient(db_session: Session):
    user, source = seed_user_source_article(db_session)
    collection = create_external_link_collection(
        db_session,
        user,
        source.id,
        title="Weekly Picks",
        target_send_date=date(2026, 6, 21),
        send_time=time(hour=8),
        prepare_offset_hours=6,
        link_source_mode=ExternalLinkSourceMode.auto,
    )

    result = run_due_external_link_generation(
        db_session,
        now=datetime(2026, 6, 21, 8, 0),
    )

    db_session.refresh(collection)
    assert result == "failed:1"
    assert collection.status == ExternalLinkCollectionStatus.failed
    assert collection.last_error == "email digest recipient is not configured"
```

- [ ] **Step 5: Implement generation helpers in collection service**

Add these imports to `external_link_collection_service.py`:

```python
import re
from app.models import EmailDigestSetting
from app.services.email_digest_settings_service import get_or_create_email_digest_setting
from app.services.email_service import EmailAttachment, send_email
from app.services.external_link_epub_service import build_external_link_epub
```

Add generation functions:

```python
SLUG_RE = re.compile(r"[^a-z0-9]+")


def external_link_epub_filename(title: str, target_send_date: date) -> str:
    slug = SLUG_RE.sub("-", title.lower()).strip("-")[:80]
    suffix = f"-{slug}" if slug else ""
    return f"RSSWise-External-Links-{target_send_date.isoformat()}{suffix}.epub"


def should_generate_collection(collection: ExternalLinkCollection, *, now: datetime | None = None) -> bool:
    if collection.sent_at is not None:
        return False
    current = collection_local_now(collection, now)
    if collection.target_send_date > current.date():
        return False
    if current.time().replace(second=0, microsecond=0) < collection.send_time:
        return False
    return len(collection.items) > 0


def list_generate_due_collections(db: Session, *, now: datetime | None = None) -> list[ExternalLinkCollection]:
    candidates = db.execute(
        select(ExternalLinkCollection)
        .where(ExternalLinkCollection.sent_at.is_(None))
        .options(
            joinedload(ExternalLinkCollection.source_article).joinedload(Article.feed),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.content),
            selectinload(ExternalLinkCollection.items)
            .joinedload(ExternalLinkCollectionItem.article)
            .joinedload(Article.ai_analysis),
        )
    ).unique().scalars().all()
    return [collection for collection in candidates if should_generate_collection(collection, now=now)]


def send_external_link_collection(
    db: Session,
    collection: ExternalLinkCollection,
    setting: EmailDigestSetting,
) -> None:
    if not setting.recipient_email:
        raise ValueError("email digest recipient is not configured")

    epub = build_external_link_epub(collection)
    collection.generated_at = now_utc_naive()
    collection.status = ExternalLinkCollectionStatus.generated
    db.commit()

    send_email(
        subject=f"RSSWise 外链文章合集 - {collection.target_send_date.isoformat()}",
        to_email=setting.recipient_email,
        text_body=f"{collection.title} 已生成，见附件 EPUB。",
        attachments=[
            EmailAttachment(
                filename=external_link_epub_filename(collection.title, collection.target_send_date),
                content=epub,
                content_type="application/epub+zip",
            )
        ],
    )
    collection.sent_at = now_utc_naive()
    collection.status = ExternalLinkCollectionStatus.sent
    collection.last_error = None
    db.commit()


def run_due_external_link_generation(db: Session, *, now: datetime | None = None) -> str:
    setting = get_or_create_email_digest_setting(db)
    due = list_generate_due_collections(db, now=now)
    sent_count = 0
    failed_count = 0
    for collection in due:
        try:
            send_external_link_collection(db, collection, setting)
            sent_count += 1
        except Exception as exc:
            collection.status = ExternalLinkCollectionStatus.failed
            collection.last_error = str(exc)[:1000]
            db.commit()
            failed_count += 1
    if failed_count:
        return f"failed:{failed_count}"
    return f"sent:{sent_count}"
```

- [ ] **Step 6: Verify EPUB and generation tests**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_link_epub_service.py tests/test_external_link_collection_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit EPUB and delivery slice**

```bash
rtk git add apps/api/app/services/external_link_epub_service.py apps/api/app/services/external_link_collection_service.py apps/api/tests/test_external_link_epub_service.py apps/api/tests/test_external_link_collection_service.py
rtk git diff --staged
rtk git commit -m "feat(api): build and send external link epubs"
```

Expected staged diff: EPUB service, collection generation additions, and related tests.

---

### Task 5: Backend API And Celery Scheduling

**Files:**
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/routers/external_links.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/tasks.py`
- Modify: `apps/api/app/beat.py`
- Create: `apps/api/tests/test_external_links_api.py`
- Modify: `apps/api/tests/test_tasks.py`
- Modify: `apps/api/tests/test_beat.py`

- [ ] **Step 1: Add API and task tests**

Create `apps/api/tests/test_external_links_api.py` using the same `TestClient` fixture shape as `test_articles_api.py`. Cover these exact cases:

```python
def test_preview_external_links_returns_links_for_subscribed_source_article(client: TestClient):
    user = register(client)
    source_id = seed_source_article_with_links(client, user_id=user["id"])

    response = client.post(
        f"/articles/{source_id}/external-links/preview",
        json={"link_source_mode": "auto"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_article_id"] == str(source_id)
    assert body["links"][0]["anchor_text"] == "Target A"
    assert body["links"][0]["normalized_url"] == "https://target.example.com/a"


def test_create_external_link_collection_returns_collection_items(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    user = register(client)
    source_id = seed_source_article_with_links(client, user_id=user["id"])
    monkeypatch.setattr(
        "app.services.external_link_collection_service.enqueue_article_extraction",
        lambda article_id: None,
    )

    response = client.post(
        f"/articles/{source_id}/external-links/collections",
        json={
            "title": "Weekly Picks",
            "target_send_date": "2026-06-21",
            "send_time": "08:00",
            "prepare_offset_hours": 6,
            "link_source_mode": "auto",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Weekly Picks"
    assert body["source_article"]["id"] == str(source_id)
    assert body["items"][0]["position"] == 1


def test_external_link_collection_access_requires_source_feed_subscription(client: TestClient):
    first_user = register(client, "first@example.com")
    source_id = seed_source_article_with_links(client, user_id=first_user["id"])
    created = client.post(
        f"/articles/{source_id}/external-links/collections",
        json={
            "title": "Weekly Picks",
            "target_send_date": "2026-06-21",
            "send_time": "08:00",
            "prepare_offset_hours": 6,
            "link_source_mode": "auto",
        },
    ).json()

    second_client = TestClient(app)
    register(second_client, "second@example.com")

    assert second_client.get(f"/external-link-collections/{created['id']}").status_code == 404
```

Append task and beat tests:

```python
def test_external_link_tasks_call_services(session_local, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("app.tasks.run_due_external_link_preparation", lambda db: calls.append("prepare") or "prepared:0")
    monkeypatch.setattr("app.tasks.run_due_external_link_generation", lambda db: calls.append("generate") or "sent:0")

    prepare_due_external_links_task()
    generate_due_external_links_task()

    assert calls == ["prepare", "generate"]
```

```python
def test_external_link_schedules_registered() -> None:
    assert beat_schedule["external-links-prepare-due-every-five-minutes"]["task"] == "external_links.prepare_due"
    assert beat_schedule["external-links-prepare-due-every-five-minutes"]["schedule"] == 300.0
    assert beat_schedule["external-links-generate-due-every-five-minutes"]["task"] == "external_links.generate_due"
    assert beat_schedule["external-links-generate-due-every-five-minutes"]["schedule"] == 300.0
```

- [ ] **Step 2: Run API/task tests and verify failures**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_links_api.py tests/test_tasks.py tests/test_beat.py -q
```

Expected: FAIL for missing schemas/router/tasks/beat entries.

- [ ] **Step 3: Add schemas**

In `apps/api/app/schemas.py`, import the new enums and add:

```python
class ExternalLinkPreviewRequest(BaseModel):
    link_source_mode: ExternalLinkSourceMode = ExternalLinkSourceMode.auto


class ExternalLinkCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    target_send_date: date
    send_time: str
    prepare_offset_hours: int = Field(ge=1, le=48)
    link_source_mode: ExternalLinkSourceMode = ExternalLinkSourceMode.auto

    @field_validator("send_time")
    @classmethod
    def validate_send_time(cls, value: str) -> str:
        if not SEND_TIME_RE.match(value):
            raise ValueError("send_time must use HH:MM format")
        return value


class ExternalLinkPreviewItem(BaseModel):
    url: str
    normalized_url: str
    anchor_text: str | None
    position: int


class ExternalLinkPreviewResponse(BaseModel):
    source_article_id: UUID
    links: list[ExternalLinkPreviewItem]
    filtered_count: int
    duplicate_count: int


class ExternalLinkSourceArticleRead(BaseModel):
    id: UUID
    title: str
    url: str


class ExternalLinkCollectionItemRead(BaseModel):
    id: UUID
    article_id: UUID | None
    position: int
    source_url: str
    normalized_url: str
    anchor_text: str | None
    title: str
    status: ExternalLinkItemStatus
    error_message: str | None


class ExternalLinkCollectionRead(BaseModel):
    id: UUID
    title: str
    source_article: ExternalLinkSourceArticleRead
    target_send_date: date
    timezone: str
    send_time: str
    prepare_offset_hours: int
    link_source_mode: ExternalLinkSourceMode
    status: ExternalLinkCollectionStatus
    prepared_at: datetime | None
    generated_at: datetime | None
    sent_at: datetime | None
    last_error: str | None
    full_text_count: int
    placeholder_count: int
    items: list[ExternalLinkCollectionItemRead]
```

- [ ] **Step 4: Add router**

Create `apps/api/app/routers/external_links.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import ExternalLinkCollection, ExternalLinkCollectionItem, ExternalLinkItemStatus, User
from app.schemas import (
    ExternalLinkCollectionRead,
    ExternalLinkCollectionItemRead,
    ExternalLinkCreateRequest,
    ExternalLinkPreviewRequest,
    ExternalLinkPreviewResponse,
    ExternalLinkPreviewItem,
    ExternalLinkSourceArticleRead,
)
from app.services.email_digest_settings_service import format_send_time, parse_send_time
from app.services.external_link_collection_service import (
    create_external_link_collection,
    derived_item_status,
    external_link_collection_for_user,
    prepare_external_link_collection,
    preview_external_links,
)
from app.services.external_link_epub_service import build_external_link_epub

router = APIRouter(tags=["external-links"])


def serialize_collection(collection: ExternalLinkCollection) -> ExternalLinkCollectionRead:
    items = sorted(collection.items, key=lambda item: item.position)
    serialized_items: list[ExternalLinkCollectionItemRead] = []
    full_text_count = 0
    for item in items:
        status_value = derived_item_status(item)
        if status_value == ExternalLinkItemStatus.success:
            full_text_count += 1
        title = item.article.title if item.article is not None else item.title_hint or item.normalized_url
        serialized_items.append(
            ExternalLinkCollectionItemRead(
                id=item.id,
                article_id=item.article_id,
                position=item.position,
                source_url=item.source_url,
                normalized_url=item.normalized_url,
                anchor_text=item.anchor_text,
                title=title,
                status=status_value,
                error_message=item.error_message,
            )
        )
    return ExternalLinkCollectionRead(
        id=collection.id,
        title=collection.title,
        source_article=ExternalLinkSourceArticleRead(
            id=collection.source_article.id,
            title=collection.source_article.title,
            url=collection.source_article.url,
        ),
        target_send_date=collection.target_send_date,
        timezone=collection.timezone,
        send_time=format_send_time(collection.send_time),
        prepare_offset_hours=collection.prepare_offset_hours,
        link_source_mode=collection.link_source_mode,
        status=collection.status,
        prepared_at=collection.prepared_at,
        generated_at=collection.generated_at,
        sent_at=collection.sent_at,
        last_error=collection.last_error,
        full_text_count=full_text_count,
        placeholder_count=len(items) - full_text_count,
        items=serialized_items,
    )


@router.post("/articles/{article_id}/external-links/preview", response_model=ExternalLinkPreviewResponse)
def preview_article_external_links(
    article_id: UUID,
    payload: ExternalLinkPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        preview = preview_external_links(db, current_user, article_id, payload.link_source_mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ExternalLinkPreviewResponse(
        source_article_id=preview.source_article.id,
        links=[
            ExternalLinkPreviewItem(
                url=link.url,
                normalized_url=link.normalized_url,
                anchor_text=link.anchor_text,
                position=link.position,
            )
            for link in preview.parse_result.links
        ],
        filtered_count=preview.parse_result.filtered_count,
        duplicate_count=preview.parse_result.duplicate_count,
    )


@router.post(
    "/articles/{article_id}/external-links/collections",
    response_model=ExternalLinkCollectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_article_external_link_collection(
    article_id: UUID,
    payload: ExternalLinkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        collection = create_external_link_collection(
            db,
            current_user,
            article_id,
            title=payload.title,
            target_send_date=payload.target_send_date,
            send_time=parse_send_time(payload.send_time),
            prepare_offset_hours=payload.prepare_offset_hours,
            link_source_mode=payload.link_source_mode,
        )
    except ValueError as exc:
        status_code = status.HTTP_400_BAD_REQUEST if str(exc) == "no external links found" else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return serialize_collection(collection)


@router.get("/external-link-collections/{collection_id}", response_model=ExternalLinkCollectionRead)
def get_external_link_collection(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return serialize_collection(external_link_collection_for_user(db, current_user, collection_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection not found") from exc


@router.post("/external-link-collections/{collection_id}/prepare", response_model=ExternalLinkCollectionRead)
def retry_external_link_collection_prepare(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    external_link_collection_for_user(db, current_user, collection_id)
    collection = prepare_external_link_collection(db, collection_id)
    return serialize_collection(collection)


@router.get("/external-link-collections/{collection_id}/epub")
def download_external_link_collection_epub(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        collection = external_link_collection_for_user(db, current_user, collection_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection not found") from exc
    return Response(
        content=build_external_link_epub(collection),
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="RSSWise-External-Links-{collection.target_send_date.isoformat()}.epub"'},
    )
```

Update `apps/api/app/main.py`:

```python
from app.routers import articles, auth, external_links, feeds, settings as settings_router

app.include_router(external_links.router)
```

- [ ] **Step 5: Add Celery service wrappers and tasks**

Add this to `external_link_collection_service.py`:

```python
def run_due_external_link_preparation(db: Session, *, now: datetime | None = None) -> str:
    due = list_prepare_due_collections(db, now=now)
    for collection in due:
        prepare_external_link_collection(db, collection.id, now=now)
    return f"prepared:{len(due)}"
```

Add imports and tasks to `apps/api/app/tasks.py`:

```python
from app.services.external_link_collection_service import (
    run_due_external_link_generation,
    run_due_external_link_preparation,
)


@celery_app.task(name="external_links.prepare_due")
def prepare_due_external_links_task() -> str:
    with SessionLocal() as db:
        return run_due_external_link_preparation(db)


@celery_app.task(name="external_links.generate_due")
def generate_due_external_links_task() -> str:
    with SessionLocal() as db:
        return run_due_external_link_generation(db)
```

Update `apps/api/app/beat.py`:

```python
    "external-links-prepare-due-every-five-minutes": {
        "task": "external_links.prepare_due",
        "schedule": 300.0,
    },
    "external-links-generate-due-every-five-minutes": {
        "task": "external_links.generate_due",
        "schedule": 300.0,
    },
```

- [ ] **Step 6: Verify backend API and scheduling tests**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest tests/test_external_links_api.py tests/test_tasks.py tests/test_beat.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit API and scheduling slice**

```bash
rtk git add apps/api/app/schemas.py apps/api/app/routers/external_links.py apps/api/app/main.py apps/api/app/tasks.py apps/api/app/beat.py apps/api/tests/test_external_links_api.py apps/api/tests/test_tasks.py apps/api/tests/test_beat.py
rtk git diff --staged
rtk git commit -m "feat(api): expose external link collection endpoints"
```

Expected staged diff: schemas, router, main include, Celery task/beat changes, and API/task tests.

---

### Task 6: Frontend Dialog And API Types

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/query-keys.ts`
- Create: `apps/web/src/routes/articles/external-link-epub-dialog.tsx`

- [ ] **Step 1: Add API types**

In `apps/web/src/lib/api.ts`, add:

```ts
export type ExternalLinkSourceMode = "auto" | "summary_from_feed" | "content_markdown";
export type ExternalLinkCollectionStatus = "collecting" | "prepared" | "generated" | "sent" | "failed";
export type ExternalLinkItemStatus = "pending" | "extracting" | "success" | "failed" | "timed_out";

export type ExternalLinkPreviewItem = {
  url: string;
  normalized_url: string;
  anchor_text: string | null;
  position: number;
};

export type ExternalLinkPreviewResponse = {
  source_article_id: string;
  links: ExternalLinkPreviewItem[];
  filtered_count: number;
  duplicate_count: number;
};

export type ExternalLinkCreateRequest = {
  title: string;
  target_send_date: string;
  send_time: string;
  prepare_offset_hours: number;
  link_source_mode: ExternalLinkSourceMode;
};

export type ExternalLinkCollection = {
  id: string;
  title: string;
  source_article: {
    id: string;
    title: string;
    url: string;
  };
  target_send_date: string;
  timezone: string;
  send_time: string;
  prepare_offset_hours: number;
  link_source_mode: ExternalLinkSourceMode;
  status: ExternalLinkCollectionStatus;
  prepared_at: string | null;
  generated_at: string | null;
  sent_at: string | null;
  last_error: string | null;
  full_text_count: number;
  placeholder_count: number;
  items: Array<{
    id: string;
    article_id: string | null;
    position: number;
    source_url: string;
    normalized_url: string;
    anchor_text: string | null;
    title: string;
    status: ExternalLinkItemStatus;
    error_message: string | null;
  }>;
};
```

In `apps/web/src/lib/query-keys.ts`, add:

```ts
  externalLinkCollections: {
    all: ["externalLinkCollections"] as const,
    detail: (id: string) => ["externalLinkCollections", id] as const,
  },
```

- [ ] **Step 2: Create dialog component**

Create `apps/web/src/routes/articles/external-link-epub-dialog.tsx`. Use coss `Dialog`, `Field`, `Input`, `Select`, `Button`, and `toastManager`; default the date with Asia/Shanghai formatting:

```tsx
import { useEffect, useMemo, useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toastManager } from "@/components/ui/toast"
import {
  apiPost,
  type ArticleListItem,
  type ExternalLinkCollection,
  type ExternalLinkCreateRequest,
  type ExternalLinkPreviewResponse,
  type ExternalLinkSourceMode,
} from "@/lib/api"

const SOURCE_MODE_ITEMS: Array<{ value: ExternalLinkSourceMode; label: string }> = [
  { value: "auto", label: "自动" },
  { value: "summary_from_feed", label: "Feed 摘要" },
  { value: "content_markdown", label: "已抓取正文" },
]

function shanghaiDateForSendTime(sendTime: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date())
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "00"
  const today = `${get("year")}-${get("month")}-${get("day")}`
  if (`${get("hour")}:${get("minute")}` < sendTime) return today
  const next = new Date(Date.UTC(Number(get("year")), Number(get("month")) - 1, Number(get("day")) + 1))
  return [
    next.getUTCFullYear(),
    String(next.getUTCMonth() + 1).padStart(2, "0"),
    String(next.getUTCDate()).padStart(2, "0"),
  ].join("-")
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求失败"
}

export function ExternalLinkEpubDialog({
  article,
  open,
  onOpenChange,
}: {
  article: ArticleListItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [title, setTitle] = useState("")
  const [targetSendDate, setTargetSendDate] = useState("")
  const [sendTime, setSendTime] = useState("08:00")
  const [prepareOffsetHours, setPrepareOffsetHours] = useState("6")
  const [linkSourceMode, setLinkSourceMode] = useState<ExternalLinkSourceMode>("auto")
  const [preview, setPreview] = useState<ExternalLinkPreviewResponse | null>(null)

  useEffect(() => {
    if (!open || !article) return
    setTitle(article.title)
    setSendTime("08:00")
    setTargetSendDate(shanghaiDateForSendTime("08:00"))
    setPrepareOffsetHours("6")
    setLinkSourceMode("auto")
    setPreview(null)
  }, [open, article])

  const previewMutation = useMutation({
    mutationFn: () =>
      apiPost<ExternalLinkPreviewResponse>(
        `/articles/${article?.id}/external-links/preview`,
        { link_source_mode: linkSourceMode },
      ),
    onSuccess: (data) => setPreview(data),
  })

  const createMutation = useMutation({
    mutationFn: () => {
      if (!article) throw new Error("文章无效")
      const payload: ExternalLinkCreateRequest = {
        title: title.trim() || article.title,
        target_send_date: targetSendDate,
        send_time: sendTime,
        prepare_offset_hours: Number(prepareOffsetHours),
        link_source_mode: linkSourceMode,
      }
      return apiPost<ExternalLinkCollection>(
        `/articles/${article.id}/external-links/collections`,
        payload,
      )
    },
    onSuccess: () => {
      toastManager.add({ type: "success", title: "外链 EPUB 已创建" })
      onOpenChange(false)
    },
  })

  const canCreate = Boolean(article && title.trim() && targetSendDate && sendTime && Number(prepareOffsetHours) > 0)
  const error = previewMutation.error ?? createMutation.error

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>创建外链 EPUB</DialogTitle>
        </DialogHeader>
        <DialogPanel className="flex flex-col gap-4">
          {article ? (
            <div className="rounded-lg border bg-card p-3">
              <p className="line-clamp-2 text-sm font-medium text-foreground">{article.title}</p>
            </div>
          ) : null}
          <Field>
            <FieldLabel htmlFor="external-link-title">合集标题</FieldLabel>
            <Input id="external-link-title" type="text" value={title} onChange={(event) => setTitle(event.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="external-link-date">发送日期</FieldLabel>
              <Input id="external-link-date" type="date" value={targetSendDate} onChange={(event) => setTargetSendDate(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel htmlFor="external-link-time">发送时间</FieldLabel>
              <Input id="external-link-time" type="time" value={sendTime} onChange={(event) => {
                setSendTime(event.target.value)
                setTargetSendDate(shanghaiDateForSendTime(event.target.value))
              }} />
              <FieldDescription>Asia/Shanghai</FieldDescription>
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="external-link-offset">提前准备小时数</FieldLabel>
              <Input id="external-link-offset" type="number" min={1} max={48} value={prepareOffsetHours} onChange={(event) => setPrepareOffsetHours(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>链接来源</FieldLabel>
              <Select items={SOURCE_MODE_ITEMS} value={linkSourceMode} onValueChange={(value) => setLinkSourceMode(value as ExternalLinkSourceMode)}>
                <SelectTrigger>
                  <SelectValue placeholder="选择链接来源" />
                </SelectTrigger>
                <SelectPopup>
                  {SOURCE_MODE_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>
          </div>
          <Button type="button" variant="outline" loading={previewMutation.isPending} onClick={() => previewMutation.mutate()}>
            预览链接
          </Button>
          {preview ? (
            <div className="rounded-lg border bg-card p-3">
              <p className="text-sm font-medium text-foreground">共 {preview.links.length} 个链接</p>
              <p className="mt-1 text-xs text-muted-foreground">过滤 {preview.filtered_count} 个，重复 {preview.duplicate_count} 个</p>
              <div className="mt-3 flex max-h-44 flex-col gap-2 overflow-y-auto">
                {preview.links.length === 0 ? (
                  <p className="text-sm text-destructive-foreground">未找到可用链接</p>
                ) : (
                  preview.links.map((link) => (
                    <div key={link.normalized_url} className="min-w-0 rounded border bg-background p-2">
                      <p className="truncate text-sm text-foreground">{link.anchor_text || link.normalized_url}</p>
                      <p className="truncate text-xs text-muted-foreground">{link.normalized_url}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}
          {error ? <p className="text-sm text-destructive-foreground">{errorMessage(error)}</p> : null}
        </DialogPanel>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" disabled={!canCreate} loading={createMutation.isPending} onClick={() => createMutation.mutate()}>
            创建合集
          </Button>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}
```

- [ ] **Step 3: Build the frontend dialog slice**

Run:

```bash
rtk pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 4: Commit dialog slice**

```bash
rtk git add apps/web/src/lib/api.ts apps/web/src/lib/query-keys.ts apps/web/src/routes/articles/external-link-epub-dialog.tsx
rtk git diff --staged
rtk git commit -m "feat(web): add external link epub dialog"
```

Expected staged diff: frontend API types, query keys, and the dialog component only.

---

### Task 7: Article Row Actions And Context Menu

**Files:**
- Create: `apps/web/src/components/ui/context-menu.tsx`
- Modify: `apps/web/src/routes/articles/workbench.tsx`
- Modify: `apps/web/tests/e2e/articles.spec.ts`

- [ ] **Step 1: Add row action tests**

Add Playwright tests for visible menu preview/create and right-click selection isolation:

```ts
test("article row action previews and creates external-link epub", async ({ page }) => {
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.route(
    `**/api/articles/${firstArticleId}/external-links/preview`,
    async (route) => {
      expect(route.request().method()).toBe("POST")
      expect(route.request().postDataJSON()).toEqual({ link_source_mode: "auto" })
      await route.fulfill({
        json: {
          source_article_id: firstArticleId,
          filtered_count: 1,
          duplicate_count: 1,
          links: [
            {
              url: "https://target.example.com/a",
              normalized_url: "https://target.example.com/a",
              anchor_text: "Target A",
              position: 1,
            },
          ],
        },
      })
    },
  )
  await page.route(
    `**/api/articles/${firstArticleId}/external-links/collections`,
    async (route) => {
      expect(route.request().method()).toBe("POST")
      expect(route.request().postDataJSON()).toMatchObject({
        title: "移动端文章详情测试",
        send_time: "08:00",
        prepare_offset_hours: 6,
        link_source_mode: "auto",
      })
      await route.fulfill({
        status: 201,
        json: {
          id: "44444444-4444-4444-4444-444444444444",
          title: "移动端文章详情测试",
          source_article: {
            id: firstArticleId,
            title: "移动端文章详情测试",
            url: "https://example.com/mobile-article",
          },
          target_send_date: "2026-06-21",
          timezone: "Asia/Shanghai",
          send_time: "08:00",
          prepare_offset_hours: 6,
          link_source_mode: "auto",
          status: "collecting",
          prepared_at: null,
          generated_at: null,
          sent_at: null,
          last_error: null,
          full_text_count: 0,
          placeholder_count: 1,
          items: [],
        },
      })
    },
  )

  await page.goto("/articles")
  await page.getByRole("button", { name: /移动端文章详情测试 更多操作/ }).click()
  await page.getByRole("menuitem", { name: "创建外链 EPUB" }).click()
  await expect(page.getByRole("dialog", { name: "创建外链 EPUB" })).toBeVisible()
  await page.getByRole("button", { name: "预览链接" }).click()
  await expect(page.getByText("Target A")).toBeVisible()
  await expect(page.getByText("https://target.example.com/a")).toBeVisible()
  await page.getByRole("button", { name: "创建合集" }).click()
  await expect(page.getByText("外链 EPUB 已创建")).toBeVisible()
})
```

```ts
test("article row external-link action is available through right click without selecting row", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await mockAuthenticatedUser(page)
  await mockArticleRoutes(page)
  await mockReadRoute(page)

  await page.goto(`/articles?id=${secondArticleId}`)
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()

  await page.getByRole("button", { name: /移动端文章详情测试/ }).click({ button: "right" })
  await page.getByRole("menuitem", { name: "创建外链 EPUB" }).click()

  await expect(page.getByRole("dialog", { name: "创建外链 EPUB" })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/articles\\?id=${secondArticleId}$`))
  await expect(page.getByRole("heading", { name: "第二篇桌面键盘测试" })).toBeVisible()
})
```

- [ ] **Step 2: Create coss-style context menu wrapper**

Create `apps/web/src/components/ui/context-menu.tsx`:

```tsx
"use client"

import { ContextMenu as ContextMenuPrimitive } from "@base-ui/react/context-menu"
import type * as React from "react"

import {
  MenuItem,
  MenuPopup,
  MenuSeparator,
} from "@/components/ui/menu"

export const ContextMenu = ContextMenuPrimitive.Root
export const ContextMenuTrigger = ContextMenuPrimitive.Trigger
export const ContextMenuPortal = ContextMenuPrimitive.Portal
export const ContextMenuPositioner = ContextMenuPrimitive.Positioner

export function ContextMenuPopup(
  props: React.ComponentProps<typeof MenuPopup>,
): React.ReactElement {
  return <MenuPopup {...props} />
}

export const ContextMenuItem = MenuItem
export const ContextMenuSeparator = MenuSeparator
export { ContextMenuPrimitive }
```

- [ ] **Step 3: Refactor article rows**

In `apps/web/src/routes/articles/workbench.tsx`:

1. Import `MoreHorizontalIcon`, `ExternalLinkEpubDialog`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuTrigger`, and the new context menu wrapper.
2. Add state in `ArticleWorkbenchPage`:

```tsx
const [externalLinkArticle, setExternalLinkArticle] = useState<ArticleListItem | null>(null)
```

3. Pass `onCreateExternalLinkEpub={setExternalLinkArticle}` into `ArticleListPanel` in both mobile and desktop render paths.
4. Render the dialog once near the root of each mobile/desktop branch:

```tsx
<ExternalLinkEpubDialog
  article={externalLinkArticle}
  open={externalLinkArticle !== null}
  onOpenChange={(open) => {
    if (!open) setExternalLinkArticle(null)
  }}
/>
```

5. Update `ArticleListPanel` props:

```tsx
  onCreateExternalLinkEpub: (article: ArticleListItem) => void
```

6. Replace each row `<button>` wrapper with this non-interactive row structure:

```tsx
<ContextMenu key={article.id}>
  <ContextMenuTrigger
    render={
      <div
        className={cn(
          "flex items-start gap-1 px-3 py-2 transition-colors",
          isSelected ? "bg-accent" : "hover:bg-accent/60",
        )}
      />
    }
  >
    <button
      type="button"
      className="flex min-w-0 flex-1 items-start gap-2 rounded-sm px-1 py-1 text-left"
      onClick={() => onSelect(article.id)}
    >
      {!article.is_read ? (
        <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground" />
      ) : (
        <span className="mt-1.5 size-1.5 shrink-0" />
      )}
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            "line-clamp-2 text-sm leading-snug",
            article.is_read ? "font-normal text-muted-foreground" : "font-medium text-foreground",
            isSelected && "text-foreground",
          )}
        >
          {article.title}
        </span>
        {article.one_sentence_summary ? (
          <span className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {article.one_sentence_summary}
          </span>
        ) : null}
      </span>
    </button>
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`${article.title} 更多操作`}
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
      >
        <MoreHorizontalIcon aria-hidden="true" className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={4}>
        <DropdownMenuItem closeOnClick onClick={() => onCreateExternalLinkEpub(article)}>
          创建外链 EPUB
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  </ContextMenuTrigger>
  <ContextMenuPopup>
    <ContextMenuItem closeOnClick onClick={() => onCreateExternalLinkEpub(article)}>
      创建外链 EPUB
    </ContextMenuItem>
  </ContextMenuPopup>
</ContextMenu>
```

Keep the article title select button as the only element that calls `onSelect`. Opening either menu must not call `onSelect`.

- [ ] **Step 4: Verify frontend tests**

Run:

```bash
rtk pnpm --dir apps/web test:e2e -- articles.spec.ts -g "external-link|right click"
```

Expected: PASS for the new external-link tests.

- [ ] **Step 5: Run frontend build**

Run:

```bash
rtk pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 6: Commit frontend slice**

```bash
rtk git add apps/web/src/lib/api.ts apps/web/src/lib/query-keys.ts apps/web/src/components/ui/context-menu.tsx apps/web/src/routes/articles/external-link-epub-dialog.tsx apps/web/src/routes/articles/workbench.tsx apps/web/tests/e2e/articles.spec.ts
rtk git diff --staged
rtk git commit -m "feat(web): expose external link epub row actions"
```

Expected staged diff: frontend API types, context menu wrapper, dialog, workbench row actions, and Playwright tests.

---

### Task 8: Full Verification

**Files:**
- No source edits unless a verification command exposes a concrete failure.

- [ ] **Step 1: Run backend unit tests**

Run:

```bash
rtk uv run --directory apps/api --no-sync pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run backend lint**

Run:

```bash
rtk uv run --directory apps/api --no-sync ruff check app tests
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
rtk pnpm --dir apps/web build
```

Expected: PASS.

- [ ] **Step 4: Run targeted frontend E2E**

Run:

```bash
rtk pnpm --dir apps/web test:e2e -- articles.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Inspect final status**

Run:

```bash
rtk git status --short
```

Expected: only intentional files are changed. If this plan and the source spec are still uncommitted, they should be staged together in a docs commit when the user asks for commits.

---

## Commit Sequence

Use these commit messages if executing the plan:

```text
feat(api): add external link collection schema
feat(api): parse external links from articles
feat(api): create external link collections
feat(api): build and send external link epubs
feat(api): expose external link collection endpoints
feat(web): add external link epub dialog
feat(web): expose external link epub row actions
```

If committing the spec and plan before implementation, use:

```text
docs: plan external link epub workflow
```

## Self-Review

- Spec coverage: source selection, dialog settings, preview, parser modes, URL normalization/filtering, linked article reuse, preparation, fixed-deadline generation, placeholder chapters, front matter counts, email delivery, API endpoints, scheduling, and frontend access paths are mapped to tasks.
- No separate crawler store is introduced; linked targets are normal `Article` rows with `feed_id=None`.
- The row menu structure avoids nesting the overflow trigger inside the select button.
- AI analysis is not used as a generation gate; EPUB rendering only includes AI sections when the existing article chapter renderer can render them.
- The plan uses focused tests before implementation code and has one conventional commit per coherent slice.
