"""add is_published_x to shopee_offers

Revision ID: 2fb3f7a8a123
Revises: 9e89a68403dd
Create Date: 2026-05-15 23:50:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2fb3f7a8a123"
down_revision = "9e89a68403dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shopee_offers",
        sa.Column(
            "is_published_x", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.alter_column("shopee_offers", "is_published_x", server_default=None)


def downgrade() -> None:
    op.drop_column("shopee_offers", "is_published_x")
