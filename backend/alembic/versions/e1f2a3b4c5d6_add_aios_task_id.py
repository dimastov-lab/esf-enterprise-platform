"""esf_documents.aios_task_id: AIOS Core task reference (Layer 1 integration)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "esf_documents",
        sa.Column("aios_task_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("esf_documents", "aios_task_id")
