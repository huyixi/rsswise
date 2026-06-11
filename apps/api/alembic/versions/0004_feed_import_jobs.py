"""feed import jobs

Revision ID: 0004_feed_import_jobs
Revises: 0003_article_ai_blocks
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_feed_import_jobs"
down_revision: str | None = "0003_article_ai_blocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_type = postgresql.ENUM(
        "opml", "urls", name="feed_import_source_type"
    )
    job_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="feed_import_job_status",
    )
    item_status = postgresql.ENUM(
        "pending",
        "created",
        "subscribed",
        "skipped",
        "failed",
        name="feed_import_item_status",
    )

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
