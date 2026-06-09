"""article ai blocks

Revision ID: 0003_article_ai_blocks
Revises: 0002_email_digest_settings
Create Date: 2026-06-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_article_ai_blocks"
down_revision: str | None = "0002_email_digest_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("article_ai_analyses", sa.Column("ai_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("article_ai_analyses", "ai_blocks")
