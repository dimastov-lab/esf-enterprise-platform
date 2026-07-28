"""block TRUNCATE on the immutable snapshot & audit tables (H3 completeness)

The row-level BEFORE UPDATE/DELETE triggers do not fire for TRUNCATE, which would
otherwise wipe the "write-once" / "append-only" tables in one statement. Add
statement-level BEFORE TRUNCATE triggers so the protection is complete. (Both
still require table-owner privilege, which could also DROP the triggers — this
closes the accidental/bulk path, not a privileged operator.)

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION esf_block_truncate() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is protected: TRUNCATE is not allowed', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER esf_snapshots_no_truncate BEFORE TRUNCATE ON esf_snapshots "
        "FOR EACH STATEMENT EXECUTE FUNCTION esf_block_truncate();"
    )
    op.execute(
        "CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs "
        "FOR EACH STATEMENT EXECUTE FUNCTION esf_block_truncate();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS esf_snapshots_no_truncate ON esf_snapshots")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS esf_block_truncate()")
