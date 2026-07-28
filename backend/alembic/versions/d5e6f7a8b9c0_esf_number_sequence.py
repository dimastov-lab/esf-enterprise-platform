"""atomic ESF number allocation via a DB sequence (H2)

Replaces the count()+1 "find the next number" logic (a TOCTOU that let two
concurrent publishes compute the same number → IntegrityError/500) with a
Postgres SEQUENCE. The sequence is seeded past the highest numeric suffix already
assigned so generated numbers never collide with existing ones.

Revision ID: d5e6f7a8b9c0
Revises: c1a2b3d4e5f6
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS esf_number_seq")
    # Seed the sequence so the next value is (max existing suffix + 1). The
    # 3-arg setval's is_called flag is TRUE when any numbered doc exists (next =
    # max+1) and FALSE otherwise (next = 1, the very first number).
    op.execute(
        """
        SELECT setval(
            'esf_number_seq',
            GREATEST(
                (SELECT COALESCE(MAX(CAST(split_part(esf_number, '-', 3) AS BIGINT)), 0)
                   FROM esf_documents
                  WHERE esf_number ~ '^[0-9]+-004-[0-9]+$'
                    AND length(split_part(esf_number, '-', 3)) <= 18),
                1
            ),
            (SELECT EXISTS (
                SELECT 1 FROM esf_documents
                 WHERE esf_number ~ '^[0-9]+-004-[0-9]+$'
                   AND length(split_part(esf_number, '-', 3)) <= 18
            ))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS esf_number_seq")
