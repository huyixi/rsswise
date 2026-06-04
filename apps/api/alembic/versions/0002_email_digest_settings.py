"""email digest settings

Revision ID: 0002_email_digest_settings
Revises: 0002_multi_user_auth
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_email_digest_settings"
down_revision: str | None = "0002_multi_user_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_digest_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("send_interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("send_time", sa.Time(), nullable=False, server_default="08:00:00"),
        sa.Column("last_run_date", sa.Date(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_send_status", sa.String(length=50), nullable=True),
        sa.Column("last_send_error", sa.Text(), nullable=True),
        sa.Column("last_sent_article_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_digest_settings")
