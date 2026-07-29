"""enforce NOT NULL on counterparties.owner_id and goods.owner_id (audit A-7)

The counterparty/goods directories are per-owner caches, rebuilt automatically
from ESF saves. A NULL `owner_id` can only originate from rows created before the
owner-scoping migration c1a2b3d4e5f6: such rows match no per-owner query (they are
invisible to every user) and are exactly the scope-bypass vector the audit flags.

They are therefore purged before the column is made NOT NULL. This is
non-destructive in practice — the caches repopulate per-user on the next save.

Revision ID: b1c2d3e4f5a6
Revises: f7a8b9c0d1e2
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop dead pre-scoping rows (invisible under the per-owner filter) so the
    # NOT NULL constraint can be enforced without losing addressable data.
    op.execute("DELETE FROM counterparties WHERE owner_id IS NULL")
    op.execute("DELETE FROM goods WHERE owner_id IS NULL")
    op.alter_column('counterparties', 'owner_id',
                    existing_type=sa.Integer(), nullable=False)
    op.alter_column('goods', 'owner_id',
                    existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column('goods', 'owner_id',
                    existing_type=sa.Integer(), nullable=True)
    op.alter_column('counterparties', 'owner_id',
                    existing_type=sa.Integer(), nullable=True)
