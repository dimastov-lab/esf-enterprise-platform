from passlib.context import CryptContext
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    from app.db.session import SessionLocal
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            admin = User(
                username="admin",
                hashed_password=pwd_context.hash("admin123"),
                is_admin=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
