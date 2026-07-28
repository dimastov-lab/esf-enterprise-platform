"""scope counterparty & goods directories to their owner (H1)

Adds `owner_id` to `counterparties` and `goods` so each user's autocomplete
directory is isolated. The global UNIQUE on `counterparties.inn` is replaced by a
per-owner composite UNIQUE `(owner_id, inn)` so two users can each keep their own
entry for the same INN.

Pre-existing rows keep `owner_id = NULL` (legacy/global); they are invisible to
the owner-scoped queries and are simply repopulated per-user on the next save.

Revision ID: c1a2b3d4e5f6
Revises: a7d4e91c25f8
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = 'a7d4e91c25f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- counterparties -------------------------------------------------
    op.add_column('counterparties', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_counterparties_owner_id'), 'counterparties', ['owner_id'], unique=False)
    op.create_foreign_key(
        'fk_counterparties_owner_id', 'counterparties', 'users',
        ['owner_id'], ['id'], ondelete='CASCADE',
    )
    # INN is no longer globally unique — it is unique per owner instead.
    op.drop_index(op.f('ix_counterparties_inn'), table_name='counterparties')
    op.create_index(op.f('ix_counterparties_inn'), 'counterparties', ['inn'], unique=False)
    op.create_unique_constraint(
        'uq_counterparties_owner_inn', 'counterparties', ['owner_id', 'inn'],
    )

    # --- goods ----------------------------------------------------------
    op.add_column('goods', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_goods_owner_id'), 'goods', ['owner_id'], unique=False)
    op.create_foreign_key(
        'fk_goods_owner_id', 'goods', 'users',
        ['owner_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    # --- goods ----------------------------------------------------------
    op.drop_constraint('fk_goods_owner_id', 'goods', type_='foreignkey')
    op.drop_index(op.f('ix_goods_owner_id'), table_name='goods')
    op.drop_column('goods', 'owner_id')

    # --- counterparties -------------------------------------------------
    # NOTE: restoring the global UNIQUE on inn will fail if per-owner duplicate
    # INNs exist by the time of downgrade (expected trade-off of the isolation
    # change; deduplicate before downgrading in that case).
    op.drop_constraint('uq_counterparties_owner_inn', 'counterparties', type_='unique')
    op.drop_index(op.f('ix_counterparties_inn'), table_name='counterparties')
    op.create_index(op.f('ix_counterparties_inn'), 'counterparties', ['inn'], unique=True)
    op.drop_constraint('fk_counterparties_owner_id', 'counterparties', type_='foreignkey')
    op.drop_index(op.f('ix_counterparties_owner_id'), table_name='counterparties')
    op.drop_column('counterparties', 'owner_id')
