"""DB-level immutability triggers for snapshots & audit log (H3)

The "immutable legal source of truth" guarantee previously lived only in ORM
event listeners, which are bypassed by bulk ORM ops (query().update()/delete())
and any raw SQL. This adds a database backstop:

- esf_snapshots: write-once — every UPDATE/DELETE is rejected.
- audit_logs: append-only — DELETE is rejected and content columns (action,
  ip_address, user_agent, meta_json, created_at) cannot change; the FK-cascade
  SET NULL of user_id/document_id (a legitimate system operation) is still allowed.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION esf_snapshots_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'esf_snapshots is immutable (write-once): % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER esf_snapshots_no_update_delete
        BEFORE UPDATE OR DELETE ON esf_snapshots
        FOR EACH ROW EXECUTE FUNCTION esf_snapshots_immutable();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'audit_logs is append-only: DELETE is not allowed';
            END IF;
            IF (NEW.action     IS DISTINCT FROM OLD.action
                OR NEW.ip_address IS DISTINCT FROM OLD.ip_address
                OR NEW.user_agent IS DISTINCT FROM OLD.user_agent
                OR NEW.meta_json  IS DISTINCT FROM OLD.meta_json
                OR NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
                RAISE EXCEPTION 'audit_logs is append-only: content columns are immutable';
            END IF;
            RETURN NEW;  -- allow the FK-cascade SET NULL of user_id / document_id
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_tamper
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS esf_snapshots_no_update_delete ON esf_snapshots")
    op.execute("DROP FUNCTION IF EXISTS esf_snapshots_immutable()")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_tamper ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only()")
