"""add_user_external_id

Revision ID: e1f1d7a7bf24
Revises: a2b3c4d5e6f7
Create Date: 2026-08-07 00:08:46.872860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f1d7a7bf24'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_external_id'), 'users', ['external_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_external_id'), table_name='users')
    op.drop_column('users', 'external_id')
