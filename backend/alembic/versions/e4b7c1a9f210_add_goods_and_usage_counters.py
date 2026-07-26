"""add goods catalog + usage/favorite counters (Module 34)

Revision ID: e4b7c1a9f210
Revises: d2389f930148
Create Date: 2026-06-27 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b7c1a9f210'
down_revision: Union[str, None] = 'd2389f930148'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('price', sa.Numeric(18, 5), nullable=True),
        sa.Column('vat_rate', sa.String(length=20), nullable=True),
        sa.Column('use_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_favorite', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goods_code'), 'goods', ['code'], unique=False)
    op.create_index(op.f('ix_goods_name'), 'goods', ['name'], unique=False)

    # usage counter + favorites on the existing counterparty directory
    op.add_column('counterparties', sa.Column('use_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('counterparties', sa.Column('is_favorite', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('counterparties', 'is_favorite')
    op.drop_column('counterparties', 'use_count')
    op.drop_index(op.f('ix_goods_name'), table_name='goods')
    op.drop_index(op.f('ix_goods_code'), table_name='goods')
    op.drop_table('goods')
