"""restore_rate_limits_table

Revision ID: 8d5e97b2590b
Revises: 9bb4bef2e079
Create Date: 2026-08-05 17:46:39.366476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d5e97b2590b'
down_revision: Union[str, None] = '9bb4bef2e079'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Restore rate_limits table used by app/core/ratelimit.py."""
    op.create_table(
        'rate_limits',
        sa.Column('bucket', sa.VARCHAR(length=512), autoincrement=False, nullable=False),
        sa.Column('window_start', sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column('count', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('bucket', 'window_start', name='rate_limits_pkey')
    )


def downgrade() -> None:
    """Drop rate_limits table."""
    op.drop_table('rate_limits')
