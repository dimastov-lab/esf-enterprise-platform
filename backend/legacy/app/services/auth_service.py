from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.repo.get_by_username(username)
        if not user:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        return user
