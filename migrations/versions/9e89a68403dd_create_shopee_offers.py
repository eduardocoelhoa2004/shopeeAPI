"""create shopee_offers

Revision ID: 9e89a68403dd
Revises: 
Create Date: 2026-05-13 23:59:29.807050

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e89a68403dd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shopee_offers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('offer_id', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('commission_rate', sa.Float(), nullable=False),
        sa.Column('original_url', sa.String(length=2048), nullable=False),
        sa.Column('short_url', sa.String(length=2048), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shopee_offers_offer_id'), 'shopee_offers', ['offer_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_shopee_offers_offer_id'), table_name='shopee_offers')
    op.drop_table('shopee_offers')