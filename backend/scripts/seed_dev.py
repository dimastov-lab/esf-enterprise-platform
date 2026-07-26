"""DEVELOPMENT-ONLY seed.

Ensures baseline roles (ADMIN, ISSUER) and a development admin user
`admin` / `admin123`, and adds a demo ISSUER `issuer` / `issuer123`.
Refuses to run when ENVIRONMENT=production.

Run from backend/:
    .venv/bin/python scripts/seed_dev.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.auth_service import ROLE_ISSUER, AuthService


def seed() -> None:
    if settings.ENVIRONMENT == "production":
        raise SystemExit("Refusing to run development seed in production.")

    db = SessionLocal()
    try:
        service = AuthService(db)
        service.ensure_dev_admin()  # roles + admin/admin123
        if not service.repo.username_exists("issuer"):
            service.create_user("issuer", "issuer123", ROLE_ISSUER)
            print("Created demo ISSUER (issuer / issuer123).")
        print("Seeded roles ADMIN/ISSUER and dev admin (admin / admin123).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
