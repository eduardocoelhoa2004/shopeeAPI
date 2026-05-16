"""add is_published_facebook to shopee_offers

Revision ID: 7c4e9d1b2a34
Revises: 2fb3f7a8a123
Create Date: 2026-05-16 01:20:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7c4e9d1b2a34"
down_revision = "2fb3f7a8a123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shopee_offers",
        sa.Column(
            "is_published_facebook",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.alter_column("shopee_offers", "is_published_facebook", server_default=None)


def downgrade() -> None:
    op.drop_column("shopee_offers", "is_published_facebook")
