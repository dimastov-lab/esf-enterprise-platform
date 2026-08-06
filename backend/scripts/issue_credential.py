"""Issue a long-lived API credential for an existing ESF user.

Usage (inside the app container or dev environment):
    python scripts/issue_credential.py <username> [--label LABEL] [--expires-in-days N]

The raw ``esf_`` token is printed to stdout exactly once and never stored —
pipe it to a secrets manager immediately.  Diagnostic info (id, expiry) goes
to stderr so the token can be captured cleanly:

    TOKEN=$(python scripts/issue_credential.py alice --expires-in-days 30)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402
from app.services.credential_service import MAX_TTL_DAYS, CredentialService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue a long-lived ESF API credential for a user.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Max TTL is {MAX_TTL_DAYS} days. Omit --expires-in-days for a non-expiring credential.",
    )
    parser.add_argument("username", help="ESF username to issue the credential for")
    parser.add_argument("--label", default=None, metavar="TEXT",
                        help="Human-readable label, e.g. 'CI pipeline'")
    parser.add_argument("--expires-in-days", type=int, default=None, metavar="N",
                        help=f"TTL in days (1–{MAX_TTL_DAYS}). Omit for no expiry.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_username(args.username)
        if user is None:
            sys.exit(f"error: user '{args.username}' not found")
        if not user.is_active:
            sys.exit(f"error: user '{args.username}' is deactivated")

        try:
            cred, raw_token = CredentialService(db).issue(
                user,
                label=args.label,
                expires_in_days=args.expires_in_days,
            )
        except ValueError as exc:
            sys.exit(f"error: {exc}")

        expiry = cred.expires_at.isoformat() if cred.expires_at else "never"
        print(raw_token)
        print(
            f"# id={cred.id}  label={cred.label or '—'}  expires={expiry}",
            file=sys.stderr,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
