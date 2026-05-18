"""add_old_price_and_discount

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-18 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('shopee_offers', sa.Column('old_price', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('shopee_offers', sa.Column('discount', sa.Integer(), nullable=False, server_default='0'))
    op.drop_column('shopee_offers', 'price_discount_rate')


def downgrade() -> None:
    op.add_column('shopee_offers', sa.Column('price_discount_rate', sa.Float(), nullable=True))
    op.drop_column('shopee_offers', 'discount')
    op.drop_column('shopee_offers', 'old_price')
