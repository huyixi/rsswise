"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

extraction_status = postgresql.ENUM(
    "pending",
    "processing",
    "success",
    "failed",
    name="extraction_status",
    create_type=False,
)
analysis_status = postgresql.ENUM(
    "pending",
    "processing",
    "success",
    "failed",
    name="analysis_status",
    create_type=False,
)
reading_recommendation = postgresql.ENUM(
    "deep_read",
    "skim",
    "skip",
    name="reading_recommendation",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    extraction_status.create(bind, checkfirst=True)
    analysis_status.create(bind, checkfirst=True)
    reading_recommendation.create(bind, checkfirst=True)

    op.create_table(
        "feeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("site_url", sa.String(length=2000), nullable=True),
        sa.Column("favicon_url", sa.String(length=2000), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url", name="uq_feeds_url"),
    )
    op.create_index("ix_feeds_url", "feeds", ["url"])

    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("author", sa.String(length=500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_from_feed", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2000), nullable=True),
        sa.Column("guid", sa.String(length=2000), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("url", name="uq_articles_url"),
    )
    op.create_index("ix_articles_feed_id", "articles", ["feed_id"])
    op.create_index("ix_articles_guid", "articles", ["guid"])
    op.create_index("ix_articles_is_read", "articles", ["is_read"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_url", "articles", ["url"])

    op.create_table(
        "article_contents",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column(
            "extraction_status",
            extraction_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "article_ai_analyses",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("one_sentence_summary", sa.String(length=200), nullable=True),
        sa.Column("reading_recommendation", reading_recommendation, nullable=True),
        sa.Column("reading_reason", sa.Text(), nullable=True),
        sa.Column(
            "analysis_status",
            analysis_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("article_ai_analyses")
    op.drop_table("article_contents")
    op.drop_index("ix_articles_url", table_name="articles")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_is_read", table_name="articles")
    op.drop_index("ix_articles_guid", table_name="articles")
    op.drop_index("ix_articles_feed_id", table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_feeds_url", table_name="feeds")
    op.drop_table("feeds")

    reading_recommendation.drop(op.get_bind(), checkfirst=True)
    analysis_status.drop(op.get_bind(), checkfirst=True)
    extraction_status.drop(op.get_bind(), checkfirst=True)
