"""api_credentials: long-lived PG-backed credentials with expiry

Each row stores the SHA-256 hash of a bearer token (never the plaintext).
NULL expires_at means no expiry. revoked_at records explicit invalidation.

Revision ID: d0e1f2a3b4c5
Revises: c7d8e9f0a1b2
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_api_credentials_user_id", "api_credentials", ["user_id"])
    op.create_index("ix_api_credentials_token_hash", "api_credentials", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_api_credentials_token_hash", table_name="api_credentials")
    op.drop_index("ix_api_credentials_user_id", table_name="api_credentials")
    op.drop_table("api_credentials")
