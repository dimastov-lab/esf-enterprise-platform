"""Central application configuration.

Single source of truth for runtime settings. Values come from environment
variables with development-friendly defaults. PostgreSQL is the only active
database — there is no SQLite fallback.
"""
import os

DEFAULT_SECRET = "dev-only-secret-change-me"


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

    # "development" | "production". Guards dev-only seeds.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Public base URL used to build absolute QR / verification links.
    # Matches the official Kyrgyz ESF portal so QR codes have the same format as the
    # reference form (https://esf.salyk.kg/esf/check-esf?documentUUID=...).
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "https://esf.salyk.kg")

    # Connection pool + a hard per-statement timeout (ms) so no single query can
    # hang a worker. Tunable per deployment.
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_STATEMENT_TIMEOUT_MS: int = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))

    def validate_for_runtime(self) -> None:
        """Fail-closed safety checks for production deployments."""
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == DEFAULT_SECRET:
                raise RuntimeError(
                    "SECRET_KEY must be set to a unique non-default value when "
                    "ENVIRONMENT=production (sessions are signed with it)."
                )


settings = Settings()
settings.validate_for_runtime()
