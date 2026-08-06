"""Narrow esf_snapshots immutability trigger to payload fields only (TD-026)

The original trigger blocks every UPDATE on esf_snapshots. This is too strict:
TD-026 requires setting aios_memory_id in a post-commit UPDATE (after the row
lock is released), which is a safe operation on a non-payload field.

This migration replaces the trigger function so that only changes to the
business-critical payload fields (payload_json, sha256, immutable) are
blocked. Non-payload link fields (aios_memory_id, etc.) may be written once
via a post-commit UPDATE.

Revision ID: a2b3c4d5e6f7
Revises: 8d5e97b2590b
Create Date: 2026-08-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '8d5e97b2590b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION esf_snapshots_immutable() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'esf_snapshots is immutable (write-once): DELETE is not allowed';
            END IF;
            -- Only the business-payload fields are frozen. Non-payload link fields
            -- (e.g. aios_memory_id) may be written once in a post-commit UPDATE.
            IF (NEW.payload_json IS DISTINCT FROM OLD.payload_json
                OR NEW.sha256    IS DISTINCT FROM OLD.sha256
                OR NEW.immutable IS DISTINCT FROM OLD.immutable) THEN
                RAISE EXCEPTION
                    'esf_snapshots is immutable (write-once): payload fields cannot change';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION esf_snapshots_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'esf_snapshots is immutable (write-once): % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
