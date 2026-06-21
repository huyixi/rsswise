"""external link collections

Revision ID: 0006_external_link_collections
Revises: 0005_article_ai_analysis_logs
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_external_link_collections"
down_revision: str | None = "0005_article_ai_analysis_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_mode = postgresql.ENUM(
    "auto",
    "summary_from_feed",
    "content_markdown",
    name="external_link_source_mode",
    create_type=False,
)
collection_status = postgresql.ENUM(
    "collecting",
    "prepared",
    "generated",
    "sent",
    "failed",
    name="external_link_collection_status",
    create_type=False,
)
item_status = postgresql.ENUM(
    "pending",
    "extracting",
    "success",
    "failed",
    "timed_out",
    name="external_link_item_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    source_mode.create(bind, checkfirst=True)
    collection_status.create(bind, checkfirst=True)
    item_status.create(bind, checkfirst=True)

    op.alter_column(
        "articles",
        "feed_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

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
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["external_link_collections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection_id",
            "normalized_url",
            name="uq_external_link_items_url",
        ),
        sa.UniqueConstraint(
            "collection_id",
            "position",
            name="uq_external_link_items_position",
        ),
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
    op.drop_index(
        "ix_external_link_collection_items_status",
        table_name="external_link_collection_items",
    )
    op.drop_index(
        "ix_external_link_collection_items_normalized_url",
        table_name="external_link_collection_items",
    )
    op.drop_index(
        "ix_external_link_collection_items_article_id",
        table_name="external_link_collection_items",
    )
    op.drop_index(
        "ix_external_link_collection_items_collection_id",
        table_name="external_link_collection_items",
    )
    op.drop_table("external_link_collection_items")

    op.drop_index("ix_external_link_collections_status", table_name="external_link_collections")
    op.drop_index(
        "ix_external_link_collections_target_send_date",
        table_name="external_link_collections",
    )
    op.drop_index(
        "ix_external_link_collections_source_article_id",
        table_name="external_link_collections",
    )
    op.drop_table("external_link_collections")

    # Downgrade cleanup for feedless external-link articles before restoring NOT NULL.
    op.execute(sa.text("DELETE FROM articles WHERE feed_id IS NULL"))

    op.alter_column(
        "articles",
        "feed_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    item_status.drop(op.get_bind(), checkfirst=True)
    collection_status.drop(op.get_bind(), checkfirst=True)
    source_mode.drop(op.get_bind(), checkfirst=True)
