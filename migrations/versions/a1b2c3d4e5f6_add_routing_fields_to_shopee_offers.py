"""add_routing_fields_to_shopee_offers

Revision ID: a1b2c3d4e5f6
Revises: 079cb5631e9c
Create Date: 2026-05-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '079cb5631e9c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('shopee_offers', sa.Column('price_discount_rate', sa.Float(), nullable=True))
    op.add_column('shopee_offers', sa.Column('period_end_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('shopee_offers', 'period_end_time')
    op.drop_column('shopee_offers', 'price_discount_rate')
