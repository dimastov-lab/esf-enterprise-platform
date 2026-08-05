"""Long-lived API credential lifecycle.

Credentials are opaque bearer strings, issued once and stored as SHA-256
hashes in the api_credentials table. The raw token is returned to the caller
exactly once (at creation) and never persisted anywhere — the design mirrors
how password hashing works.

Token format: ``esf_<base64url(32 random bytes)>``
The ``esf_`` prefix makes leaked credentials machine-detectable by secret
scanners (e.g. GitHub secret scanning, truffleHog).
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.api_credential import ApiCredential
from app.models.user import User
from app.repositories.credential_repository import CredentialRepository

_PREFIX = "esf_"
# Default TTL for credentials issued without an explicit expiry.
# NULL in the DB means no expiry; callers may override via expires_in_days.
DEFAULT_TTL_DAYS: Optional[int] = None  # no-expiry default
# Hard server-side ceiling on credential lifetime. Callers that omit
# expires_in_days (→ None) receive a non-expiring credential; callers that
# supply a value must stay within this bound.
MAX_TTL_DAYS: int = 90


def _generate_token() -> str:
    raw = secrets.token_bytes(32)
    return _PREFIX + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CredentialService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CredentialRepository(db)

    def issue(
        self,
        user: User,
        label: Optional[str] = None,
        expires_in_days: Optional[int] = DEFAULT_TTL_DAYS,
    ) -> tuple[ApiCredential, str]:
        """Create a new credential. Returns (credential, raw_token).

        The raw_token is returned ONCE and must be shown to the user immediately;
        it cannot be recovered later.
        """
        if expires_in_days is not None and expires_in_days > MAX_TTL_DAYS:
            raise ValueError(
                f"expires_in_days must not exceed {MAX_TTL_DAYS} days. "
                f"Got {expires_in_days}."
            )
        raw_token = _generate_token()
        token_hash = _hash_token(raw_token)
        expires_at: Optional[datetime] = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        cred = self.repo.create(
            user_id=user.id,
            token_hash=token_hash,
            label=label or None,
            expires_at=expires_at,
        )
        return cred, raw_token

    def validate(self, raw_token: str) -> Optional[ApiCredential]:
        """Return the active credential for raw_token, or None if invalid/expired/revoked."""
        if not raw_token.startswith(_PREFIX):
            return None
        token_hash = _hash_token(raw_token)
        cred = self.repo.get_by_hash(token_hash)
        if cred is None or not cred.is_active:
            return None
        self.repo.touch(cred)
        return cred

    def list_for_user(self, user: User) -> List[ApiCredential]:
        return self.repo.list_for_user(user.id)

    def revoke(self, credential_id: int, user: User) -> bool:
        """Revoke a credential owned by user. Returns False when not found or already revoked."""
        cred = self.repo.get_for_user(credential_id, user.id)
        if cred is None or cred.revoked_at is not None:
            return False
        self.repo.revoke(cred)
        return True

    def revoke_all_for_user(self, user: User) -> int:
        """Revoke every active credential for user (e.g. on password change). Returns count."""
        creds = self.repo.list_for_user(user.id)
        count = 0
        for cred in creds:
            if cred.revoked_at is None:
                self.repo.revoke(cred)
                count += 1
        return count
