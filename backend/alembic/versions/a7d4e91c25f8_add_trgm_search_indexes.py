"""add pg_trgm GIN indexes for fast substring search

Server-side dashboard search uses ILIKE '%term%' on party name/INN, ESF number
and supply note. Plain b-tree indexes can't accelerate leading-wildcard ILIKE, so
at large volumes this becomes a sequential scan. pg_trgm GIN indexes make these
searches fast and stay flat as the table grows.

pg_trgm is a "trusted" extension on PostgreSQL 13+, so a non-superuser with CREATE
on the database can install it (no elevated privileges needed in prod).

Revision ID: a7d4e91c25f8
Revises: f6a1c2d3e4b7
Create Date: 2026-06-28
"""
from alembic import op

revision = "a7d4e91c25f8"
down_revision = "f6a1c2d3e4b7"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_esf_parties_name_trgm", "esf_parties", "name"),
    ("ix_esf_parties_inn_trgm", "esf_parties", "inn"),
    ("ix_esf_documents_number_trgm", "esf_documents", "esf_number"),
    ("ix_esf_supply_info_note_trgm", "esf_supply_info", "note"),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, col in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({col} gin_trgm_ops)")


def downgrade() -> None:
    for name, _table, _col in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    # leave the pg_trgm extension installed (harmless, may be used elsewhere)
