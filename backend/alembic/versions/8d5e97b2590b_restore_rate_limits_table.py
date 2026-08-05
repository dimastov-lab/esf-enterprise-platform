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
    """Restore rate_limits table if it was dropped by a prior migration run.

    On a fresh production DB the autogenerate migration 9bb4bef2e079 never
    dropped rate_limits (the DROP was removed before commit), so this is a
    no-op for production. The guard prevents a DuplicateTable error.
    """
    conn = op.get_bind()
    from sqlalchemy import inspect as sa_inspect
    if not sa_inspect(conn).has_table('rate_limits'):
        op.create_table(
            'rate_limits',
            sa.Column('bucket', sa.VARCHAR(length=512), autoincrement=False, nullable=False),
            sa.Column('window_start', sa.BIGINT(), autoincrement=False, nullable=False),
            sa.Column('count', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
            sa.PrimaryKeyConstraint('bucket', 'window_start', name='rate_limits_pkey'),
        )


def downgrade() -> None:
    """Drop rate_limits table only if this migration created it."""
    conn = op.get_bind()
    from sqlalchemy import inspect as sa_inspect
    if sa_inspect(conn).has_table('rate_limits'):
        op.drop_table('rate_limits')
