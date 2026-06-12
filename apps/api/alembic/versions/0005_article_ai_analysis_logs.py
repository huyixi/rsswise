"""article ai analysis logs

Revision ID: 0005_article_ai_analysis_logs
Revises: 0004_feed_import_jobs
Create Date: 2026-06-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_article_ai_analysis_logs"
down_revision: str | None = "0004_feed_import_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_ai_analysis_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("input_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("input_content_length", sa.Integer(), nullable=False),
        sa.Column("prompt_messages", sa.JSON(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("parsed_output", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_ai_analysis_logs_article_id",
        "article_ai_analysis_logs",
        ["article_id"],
    )
    op.create_index(
        "ix_article_ai_analysis_logs_status",
        "article_ai_analysis_logs",
        ["status"],
    )
    op.create_index(
        "ix_article_ai_analysis_logs_created_at",
        "article_ai_analysis_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_article_ai_analysis_logs_created_at", table_name="article_ai_analysis_logs")
    op.drop_index("ix_article_ai_analysis_logs_status", table_name="article_ai_analysis_logs")
    op.drop_index("ix_article_ai_analysis_logs_article_id", table_name="article_ai_analysis_logs")
    op.drop_table("article_ai_analysis_logs")
