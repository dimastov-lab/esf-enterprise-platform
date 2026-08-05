"""JWT access-token lifecycle for the REST /auth/token endpoint.

Tokens are short-lived (default 60 min, configurable via JWT_ACCESS_TOKEN_EXPIRE_MINUTES).
The signing secret is `settings.effective_jwt_secret` — defaults to SECRET_KEY so
no extra configuration is required; set JWT_SECRET_KEY independently when separate
rotation is needed.

Only HS256 is accepted on decode; the algorithm list is a single-element set to
prevent algorithm-confusion attacks (RS256/none downgrade).
"""
import datetime

import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_LEEWAY = datetime.timedelta(seconds=30)


def create_access_token(user_id: int) -> str:
    now = datetime.datetime.utcnow()
    expire = now + datetime.timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expire},
        settings.effective_jwt_secret,
        algorithm=_ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """Validate token and return user_id. Raises jwt.PyJWTError on any failure."""
    payload = jwt.decode(
        token,
        settings.effective_jwt_secret,
        algorithms=[_ALGORITHM],
        leeway=_LEEWAY,
    )
    return int(payload["sub"])
