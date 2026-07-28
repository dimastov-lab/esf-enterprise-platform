"""Central application configuration.

Single source of truth for runtime settings. Values come from environment
variables with development-friendly defaults. PostgreSQL is the only active
database — there is no SQLite fallback.
"""
import os

DEFAULT_SECRET = "dev-only-secret-change-me"
# Substrings that mark an unedited placeholder secret (from the .env examples).
# Any SECRET_KEY containing one is rejected in production (fail-closed).
_PLACEHOLDER_SECRET_MARKERS = ("change-me", "change_me", "changeme")
_MIN_SECRET_LEN = 32


class Settings:
    PROJECT_NAME: str = "ESF Platform"
    VERSION: str = "1.0.0-rc1"

    # PostgreSQL only. Driver is psycopg2.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://esf:esf@localhost:5432/esf",
    )

    # Loaded from env in any real deployment. The default is for local dev only.
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_SECRET)

    # Safe-by-default: only the explicit value "development" enables dev
    # conveniences (admin seed, /docs, dev preview, non-secure cookies). A missing
    # or misspelt ENVIRONMENT is therefore treated as production, not dev.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # Set true only when the app sits behind a trusted reverse proxy (e.g. nginx)
    # that sets X-Real-IP. Controls whether forwarded client IPs are believed for
    # rate-limiting / audit. Never enable on a directly-exposed app.
    TRUST_PROXY: bool = os.getenv("TRUST_PROXY", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )

    # Public base URL used to build absolute QR / verification links. This MUST be
    # the deployment's OWN host. There is intentionally NO default and the official
    # government portal is explicitly rejected in production (see validate_for_runtime):
    # pointing QR / "verification" links at esf.salyk.kg would make locally-issued,
    # legally-invalid documents appear to verify against the real state system.
    # In dev (empty) the QR encodes a bare relative path.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")

    # Non-official DEMO marker. Documents are visual clones of the official ГНС form
    # but carry NO legal validity, so every render shows a DEMO watermark by default.
    # Disabling it requires a deliberate, explicit env override.
    SHOW_DEMO_WATERMARK: bool = os.getenv("SHOW_DEMO_WATERMARK", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )

    # Connection pool + a hard per-statement timeout (ms) so no single query can
    # hang a worker. Tunable per deployment.
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_STATEMENT_TIMEOUT_MS: int = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))
    # Cap how long a mutating request waits on a contended row lock (FOR UPDATE)
    # before failing fast with a clean 409 instead of hanging for statement_timeout.
    DB_LOCK_TIMEOUT_MS: int = int(os.getenv("DB_LOCK_TIMEOUT_MS", "5000"))

    @property
    def is_production(self) -> bool:
        """Anything other than the explicit string 'development' is production."""
        return self.ENVIRONMENT.strip().lower() != "development"

    def validate_for_runtime(self) -> None:
        """Fail-closed safety checks for production deployments."""
        if not self.is_production:
            return
        sk = (self.SECRET_KEY or "").strip()
        low = sk.lower()
        if (
            not sk
            or sk == DEFAULT_SECRET
            or len(sk) < _MIN_SECRET_LEN
            or any(marker in low for marker in _PLACEHOLDER_SECRET_MARKERS)
        ):
            raise RuntimeError(
                "SECRET_KEY must be a unique, non-placeholder value of at least "
                f"{_MIN_SECRET_LEN} characters when ENVIRONMENT is production "
                "(sessions are signed with it). Generate one with: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        # PUBLIC_BASE_URL must be this deployment's own host, never the official
        # government portal — otherwise QR / verification links impersonate the real
        # state system for documents that have no legal validity.
        base = (self.PUBLIC_BASE_URL or "").strip().lower()
        if not base:
            raise RuntimeError(
                "PUBLIC_BASE_URL must be set to this deployment's own base URL "
                "(e.g. https://esf.example.com) when ENVIRONMENT is production; it is "
                "used to build absolute QR / verification links."
            )
        if "salyk.kg" in base:
            raise RuntimeError(
                "PUBLIC_BASE_URL must NOT point at the official Kyrgyz tax portal "
                "(salyk.kg). Documents issued by this platform are non-official and "
                "must verify against this deployment's own host, not the state system."
            )


settings = Settings()
settings.validate_for_runtime()
