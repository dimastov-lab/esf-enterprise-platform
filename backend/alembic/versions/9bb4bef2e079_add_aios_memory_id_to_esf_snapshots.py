"""add_aios_memory_id_to_esf_snapshots

Revision ID: 9bb4bef2e079
Revises: e1f2a3b4c5d6
Create Date: 2026-08-05 17:43:12.496532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bb4bef2e079'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add aios_memory_id nullable column to esf_snapshots table."""
    op.add_column('esf_snapshots', sa.Column('aios_memory_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove aios_memory_id column from esf_snapshots table."""
    op.drop_column('esf_snapshots', 'aios_memory_id')
