"""Central application configuration.

Single source of truth for runtime settings. Values come from environment
variables with development-friendly defaults. PostgreSQL is the only active
database — there is no SQLite fallback.
"""
import os


def env_or_file(name: str, default: str) -> str:
    """Read a setting from env, or from the file named by ``{name}_FILE``.

    Docker/Compose secrets are mounted as files; ``SECRET_KEY_FILE=/run/secrets/x``
    lets production supply secrets without putting the value itself into the
    container environment (visible in `docker inspect`, crash dumps, /proc).
    A plain env var, when set, wins — explicit beats indirection.
    """
    value = os.getenv(name)
    if value is not None:
        return value
    path = os.getenv(f"{name}_FILE")
    if path:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


DEFAULT_SECRET = "dev-only-secret-change-me-for-prod-use"  # 38 chars; "change-me" triggers prod rejection
# Substrings that mark an unedited placeholder secret (from the .env examples).
# Any SECRET_KEY containing one is rejected in production (fail-closed).
_PLACEHOLDER_SECRET_MARKERS = ("change-me", "change_me", "changeme")
_MIN_SECRET_LEN = 32


class Settings:
    PROJECT_NAME: str = "ESF Platform"
    VERSION: str = "1.1.6"

    # PostgreSQL only. Driver is psycopg2. DATABASE_URL_FILE (Docker secret) is
    # honoured when the plain env var is absent.
    DATABASE_URL: str = env_or_file(
        "DATABASE_URL",
        "postgresql+psycopg2://esf:esf@localhost:5432/esf",
    )

    # Loaded from env — or a mounted secret file via SECRET_KEY_FILE — in any
    # real deployment. The default is for local dev only.
    SECRET_KEY: str = env_or_file("SECRET_KEY", DEFAULT_SECRET)

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

    # Where published QR PNGs are persisted. Empty = the repo default
    # backend/storage/qr. Tests point this at a tmp dir (TD-016) so publishing
    # in the suite never litters the working tree.
    QR_STORAGE_DIR: str = os.getenv("QR_STORAGE_DIR", "")

    # JWT tokens for the REST /auth/token endpoint. JWT_SECRET_KEY defaults to
    # SECRET_KEY so no extra configuration is required; set it independently when
    # you need separate rotation schedules for session vs. API tokens.
    JWT_SECRET_KEY: str = env_or_file("JWT_SECRET_KEY", "")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    @property
    def effective_jwt_secret(self) -> str:
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    # ── AIOS Core integration (Layer 1 — Tasks) ──────────────────────────
    # Safe default: disabled. Set AIOS_ENABLED=true only when an AIOS instance
    # is reachable and AIOS_TOKEN / AIOS_TOKEN_FILE is provisioned.
    AIOS_ENABLED: bool = os.getenv("AIOS_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    AIOS_BASE_URL: str = os.getenv("AIOS_BASE_URL", "http://localhost:8100")
    # Service-account token ESF uses to authenticate against AIOS.
    # Supply via AIOS_TOKEN (env) or AIOS_TOKEN_FILE (Docker secret mount).
    AIOS_TOKEN: str = env_or_file("AIOS_TOKEN", "")
    AIOS_WORKSPACE_ID: str = os.getenv("AIOS_WORKSPACE_ID", "")
    # When set, AIOS identity claims are rejected unless their `tenant_id` field
    # matches this value. Prevents cross-tenant privilege escalation on a shared
    # AIOS instance. Unset (the default) means any AIOS tenant is accepted — only
    # safe in single-tenant deployments where AIOS has no other tenants.
    AIOS_EXPECTED_TENANT_ID: str = os.getenv("AIOS_EXPECTED_TENANT_ID", "")

    @property
    def effective_aios_token(self) -> str:
        return self.AIOS_TOKEN

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
