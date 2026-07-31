"""rate_limits: shared fixed-window counters for multi-worker rate limiting

The login lockout (TD-019) and the public verification throttle (TD-013) were
in-process sliding windows — per worker, so production (uvicorn --workers 2)
effectively multiplied every limit by the worker count and lost all state on
restart. This table backs the shared store: one row per (bucket, window_start)
incremented atomically via INSERT .. ON CONFLICT .. RETURNING, visible to every
worker/replica that shares the database.

`window_start` is the epoch second the fixed window began (bigint — no timezone
semantics needed). Rows are self-expiring garbage: the store deletes a bucket's
stale windows on each increment.

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("bucket", sa.String(length=512), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("bucket", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("rate_limits")
