"""Create the first admin user (production first-run tooling).

Uses the existing AuthService — no new business logic. In production no admin is
auto-seeded, so run this once after the first deployment.

Usage (inside the app container):
    python scripts/create_admin.py <username> <password>
or via env:
    ADMIN_USERNAME=... ADMIN_PASSWORD=... python scripts/create_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.auth_service import ROLE_ADMIN, AuthService


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ADMIN_USERNAME")
    password = sys.argv[2] if len(sys.argv) > 2 else os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        sys.exit("usage: create_admin.py <username> <password>  "
                 "(or set ADMIN_USERNAME / ADMIN_PASSWORD)")

    db = SessionLocal()
    try:
        service = AuthService(db)
        service.ensure_roles()
        if service.repo.username_exists(username):
            print(f"User '{username}' already exists — nothing to do.")
            return
        service.create_user(username, password, ROLE_ADMIN)
        print(f"Admin user '{username}' created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
