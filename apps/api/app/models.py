import enum
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000), unique=True, index=True)
    site_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    articles: Mapped[list["Article"]] = relationship(
        back_populates="feed",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_articles_url"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(2000), index=True)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    summary_from_feed: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    guid: Mapped[str | None] = mapped_column(String(2000), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

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
    content: Mapped["ArticleContent"] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
    ai_analysis: Mapped["ArticleAIAnalysis"] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
    ai_analysis_logs: Mapped[list["ArticleAIAnalysisLog"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleAIAnalysisLog.created_at",
    )


class ArticleContent(Base):
    __tablename__ = "article_contents"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status"),
        default=ExtractionStatus.pending,
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    article: Mapped[Article] = relationship(back_populates="content")


class ArticleAIAnalysis(Base):
    __tablename__ = "article_ai_analyses"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    one_sentence_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reading_recommendation: Mapped[ReadingRecommendation | None] = mapped_column(
        Enum(ReadingRecommendation, name="reading_recommendation"),
        nullable=True,
    )
    reading_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_blocks: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status"),
        default=AnalysisStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    article: Mapped[Article] = relationship(back_populates="ai_analysis")


class ArticleAIAnalysisLog(Base):
    __tablename__ = "article_ai_analysis_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
    )
    model: Mapped[str] = mapped_column(String(200))
    input_content_sha256: Mapped[str] = mapped_column(String(64))
    input_content_length: Mapped[int] = mapped_column(Integer)
    prompt_messages: Mapped[list[dict]] = mapped_column(JSON)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_output: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    article: Mapped[Article] = relationship(back_populates="ai_analysis_logs")


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


class EmailDigestSetting(Base):
    __tablename__ = "email_digest_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    send_interval_days: Mapped[int] = mapped_column(Integer, default=1)
    send_time: Mapped[time] = mapped_column(Time(), default=lambda: time(hour=8, minute=0))
    last_run_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_send_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sent_article_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    feed_subscriptions: Mapped[list["UserFeedSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    article_states: Mapped[list["UserArticleState"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class UserFeedSubscription(Base):
    __tablename__ = "user_feed_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="feed_subscriptions")
    feed: Mapped[Feed] = relationship()


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


class UserArticleState(Base):
    __tablename__ = "user_article_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped[User] = relationship(back_populates="article_states")
    article: Mapped[Article] = relationship()
