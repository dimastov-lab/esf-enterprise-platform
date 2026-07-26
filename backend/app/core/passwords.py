"""Password hashing — bcrypt directly.

passlib 1.7.4 is incompatible with bcrypt 5.x in this environment, so we use the
bcrypt library directly. bcrypt limits inputs to 72 bytes; we truncate explicitly.
"""
import bcrypt


def hash_password(raw: str) -> str:
    pw = raw.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(raw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
