"""Authentication + RBAC service.

Roles: ADMIN (full access, is_admin=True) and ISSUER (creates/edits own ESF).
Controller (router) -> this service -> repository -> DB.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.passwords import hash_password, needs_rehash, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository

ROLE_ADMIN = "ADMIN"
ROLE_ISSUER = "ISSUER"
ROLES = {
    ROLE_ADMIN: "Полный административный доступ",
    ROLE_ISSUER: "Создание и публикация ЭСФ",
}

# Minimum password length for human-created accounts (admin UI, bootstrap script).
# Internal dev/test seeds opt out via enforce_password_policy=False.
MIN_PASSWORD_LEN = 12


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.repo.get_by_username((username or "").strip())
        if user is None or not user.is_active:
            return None
        if not verify_password(password or "", user.hashed_password):
            return None
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)
            self.db.flush()
        return user

    def ensure_roles(self) -> dict:
        return {name: self.repo.ensure_role(name, desc) for name, desc in ROLES.items()}

    def list_users(self) -> List[User]:
        return self.repo.list_all()

    def create_user(self, username: str, password: str, role: str,
                    enforce_password_policy: bool = True) -> User:
        username = (username or "").strip()
        if not username or not password:
            raise ValueError("Имя пользователя и пароль обязательны.")
        if enforce_password_policy and len(password) < MIN_PASSWORD_LEN:
            raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов.")
        if self.repo.username_exists(username):
            raise ValueError("Пользователь с таким именем уже существует.")
        if role not in ROLES:
            raise ValueError("Неизвестная роль.")
        roles = self.ensure_roles()
        user = User(
            username=username,
            hashed_password=hash_password(password),
            is_admin=(role == ROLE_ADMIN),
            is_active=True,
        )
        user.roles.append(roles[role])
        return self.repo.add(user)

    def ensure_dev_admin(self) -> None:
        """Dev convenience: guarantee roles exist and at least one admin (admin/admin123)."""
        self.ensure_roles()
        if not self.repo.any_admin_exists():
            # Dev convenience credential — exempt from the production password policy.
            self.create_user("admin", "admin123", ROLE_ADMIN, enforce_password_policy=False)
