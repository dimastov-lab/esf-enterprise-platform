"""Verify the ESF schema exists in the configured PostgreSQL database.

Proves Sprint 3R Definition of Done: all tables + enum types present, the
lifecycle enum has the required values, and `users.is_admin` does NOT default
to true. Exit code 0 = PASS, 1 = FAIL.

Run from backend/:
    DATABASE_URL=postgresql+psycopg2://esf:esf@localhost:5432/esf \
        .venv/bin/python scripts/verify_schema.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

import app.models  # noqa: F401
from app.core.config import settings
from app.db.session import engine

EXPECTED_TABLES = {
    "users", "roles", "user_roles", "organizations", "esf_documents",
    "esf_parties", "esf_supply_info", "esf_items", "esf_totals",
    "esf_signatures", "esf_snapshots", "audit_logs", "alembic_version",
}
EXPECTED_ENUMS = {"document_status", "party_type"}
EXPECTED_STATUS_VALUES = ["DRAFT", "VALIDATED", "SNAPSHOT_CREATED", "PUBLISHED", "CANCELLED"]


def main() -> None:
    ok = True
    print(f"DB URL    : {engine.url}")

    if not settings.DATABASE_URL.startswith("postgresql"):
        ok = False
        print("FAIL: active database is not PostgreSQL")

    insp = inspect(engine)
    actual_tables = set(insp.get_table_names())
    print(f"Tables    : {sorted(actual_tables)}")
    missing = EXPECTED_TABLES - actual_tables
    if missing:
        ok = False
        print(f"FAIL: missing tables: {sorted(missing)}")

    with engine.connect() as conn:
        enums = {r[0] for r in conn.execute(
            text("SELECT typname FROM pg_type WHERE typtype = 'e'")
        )}
        status_values = [r[0] for r in conn.execute(text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'document_status' ORDER BY e.enumsortorder"
        ))]

    missing_enums = EXPECTED_ENUMS - enums
    if missing_enums:
        ok = False
        print(f"FAIL: missing enum types: {sorted(missing_enums)}")

    print(f"Status enum: {status_values}")
    if status_values != EXPECTED_STATUS_VALUES:
        ok = False
        print(f"FAIL: document_status values != {EXPECTED_STATUS_VALUES}")

    is_admin = {c["name"]: c for c in insp.get_columns("users")}["is_admin"]
    default = str(is_admin.get("default"))
    print(f"users.is_admin default: {default}")
    if "true" in default.lower():
        ok = False
        print("FAIL (security): users.is_admin defaults to true")

    print("\nRESULT:", "PASS ✅" if ok else "FAIL ❌")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
