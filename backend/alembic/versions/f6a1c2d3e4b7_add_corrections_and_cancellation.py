"""add corrections and cancellation

Adds the columns needed for v6.0 #1 (corrections + cancellation):
- esf_documents.cancelled_at  — when a published ESF was annulled
- esf_documents.corrects_id   — self-reference: this doc corrects an original ESF
- esf_supply_info.correction_number / correction_date — field 406 reference

Additive only. Existing rows get NULLs; snapshots are untouched.

Revision ID: f6a1c2d3e4b7
Revises: e4b7c1a9f210
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1c2d3e4b7"
down_revision = "e4b7c1a9f210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("esf_documents", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("esf_documents", sa.Column("corrects_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_esf_documents_corrects_id", "esf_documents", "esf_documents",
        ["corrects_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("esf_supply_info", sa.Column("correction_number", sa.String(length=100), nullable=True))
    op.add_column("esf_supply_info", sa.Column("correction_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("esf_supply_info", "correction_date")
    op.drop_column("esf_supply_info", "correction_number")
    op.drop_constraint("fk_esf_documents_corrects_id", "esf_documents", type_="foreignkey")
    op.drop_column("esf_documents", "corrects_id")
    op.drop_column("esf_documents", "cancelled_at")
