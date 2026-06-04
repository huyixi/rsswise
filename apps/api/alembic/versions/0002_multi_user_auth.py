"""multi user auth

Revision ID: 0002_multi_user_auth
Revises: 0001_initial
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime
import os
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.security import hash_password

revision: str = "0002_multi_user_auth"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "user_feed_subscriptions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "feed_id"),
    )

    op.create_table(
        "user_article_states",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "article_id"),
    )
    op.create_index("ix_user_article_states_is_read", "user_article_states", ["is_read"])

    _migrate_existing_data()

    op.drop_index("ix_articles_is_read", table_name="articles")
    op.drop_column("articles", "is_read")


def _migrate_existing_data() -> None:
    bind = op.get_bind()
    feed_count = bind.execute(sa.text("select count(*) from feeds")).scalar_one()
    if feed_count == 0:
        return

    email = os.environ.get("INITIAL_USER_EMAIL", "").strip().lower()
    password = os.environ.get("INITIAL_USER_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "INITIAL_USER_EMAIL and INITIAL_USER_PASSWORD are required "
            "when migrating existing RSSWise data"
        )

    user_id = uuid.uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    bind.execute(
        sa.text(
            """
            insert into users (id, email, password_hash, created_at)
            values (:id, :email, :password_hash, :created_at)
            """
        ),
        {
            "id": user_id,
            "email": email,
            "password_hash": hash_password(password),
            "created_at": now,
        },
    )
    bind.execute(
        sa.text(
            """
            insert into user_feed_subscriptions (user_id, feed_id, created_at)
            select :user_id, id, :created_at
            from feeds
            """
        ),
        {"user_id": user_id, "created_at": now},
    )
    bind.execute(
        sa.text(
            """
            insert into user_article_states (user_id, article_id, is_read, updated_at)
            select :user_id, id, is_read, :updated_at
            from articles
            """
        ),
        {"user_id": user_id, "updated_at": now},
    )


def downgrade() -> None:
    op.add_column("articles", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_articles_is_read", "articles", ["is_read"])
    op.drop_index("ix_user_article_states_is_read", table_name="user_article_states")
    op.drop_table("user_article_states")
    op.drop_table("user_feed_subscriptions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
