"""Data access for users and roles."""
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models import Role, User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).one_or_none()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).one_or_none()

    def username_exists(self, username: str) -> bool:
        return (
            self.db.query(User.id).filter(User.username == username).first() is not None
        )

    def list_all(self) -> List[User]:
        return (
            self.db.query(User)
            .options(selectinload(User.roles))
            .order_by(User.id.asc())
            .all()
        )

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_role(self, name: str) -> Optional[Role]:
        return self.db.query(Role).filter(Role.name == name).one_or_none()

    def ensure_role(self, name: str, description: str) -> Role:
        role = self.get_role(name)
        if role is None:
            role = Role(name=name, description=description)
            self.db.add(role)
            self.db.commit()
            self.db.refresh(role)
        return role

    def any_admin_exists(self) -> bool:
        return (
            self.db.query(User.id).filter(User.is_admin.is_(True)).first() is not None
        )
