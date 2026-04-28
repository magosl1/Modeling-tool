from typing import List, Optional

from pydantic_settings import BaseSettings

INSECURE_SECRETS = {
    "change-me-in-production",
    "change-me-in-production-use-a-long-random-string",
    "dev-secret-key-change-in-production",
    "dev-secret-key",
    "secret",
    "changeme",
    "default",
}

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Financial Modeler"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/financial_modeler"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None

    # AI Ingestion
    AI_KEYS_ENCRYPTION_KEY: Optional[str] = None  # Fernet key for encrypting user API keys
    ENABLE_AI_INGESTION: bool = True

    # Master admin bootstrap. When set, the user with this email is promoted
    # to role="master_admin" on register/login. Leave empty in environments
    # that do not need a master admin.
    MASTER_ADMIN_EMAIL: Optional[str] = None

    # CORS — comma-separated list of allowed origins.
    # In DEBUG, defaults to common local dev ports; in production, MUST be set
    # explicitly to your frontend origin(s).
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate_runtime(self) -> None:
        # SECRET_KEY checks apply ALWAYS (DEBUG or not). DEBUG only relaxes the
        # CORS production-origin requirement, never the secret strength.
        if self.SECRET_KEY in INSECURE_SECRETS:
            raise RuntimeError(
                "SECRET_KEY is set to an insecure default. "
                "Set a strong SECRET_KEY (>= 32 chars, random) in the environment."
            )
        if len(self.SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
            raise RuntimeError(
                f"SECRET_KEY is too short ({len(self.SECRET_KEY)} chars). "
                f"Minimum length is {MIN_SECRET_KEY_LENGTH} characters. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )

        if not self.DEBUG:
            origins = self.cors_origins_list
            insecure_origins = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
            if not origins:
                raise RuntimeError(
                    "CORS_ORIGINS must be set when running with DEBUG=false."
                )
            if insecure_origins:
                raise RuntimeError(
                    f"CORS_ORIGINS contains localhost entries {insecure_origins} but "
                    "DEBUG=false. Set CORS_ORIGINS to your production frontend origin(s)."
                )
            if "*" in origins:
                raise RuntimeError(
                    "CORS_ORIGINS=* is not allowed (allow_credentials=True). "
                    "List explicit origins."
                )


settings = Settings()
settings.validate_runtime()
