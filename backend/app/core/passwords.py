"""Password hashing — Argon2id (primary) with progressive bcrypt migration.

Legacy bcrypt hashes are detected by their $2b$/$2a$ prefix and verified with
the bcrypt library. A successful login with a legacy hash triggers a transparent
rehash to Argon2id (handled in AuthService.authenticate). bcrypt stays as a
runtime dependency until all existing users have logged in at least once.

Argon2id parameters follow OWASP 2023 guidance:
  memory_cost=65536 (64 MB), time_cost=2, parallelism=1
"""
import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith(("$2b$", "$2a$")):
        try:
            return bcrypt.checkpw(raw.encode("utf-8")[:72], hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    try:
        return _ph.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash is legacy bcrypt or has outdated Argon2 params."""
    if hashed.startswith(("$2b$", "$2a$")):
        return True
    try:
        return _ph.check_needs_rehash(hashed)
    except InvalidHashError:
        return True
