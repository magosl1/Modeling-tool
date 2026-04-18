from typing import Optional

from pydantic_settings import BaseSettings

INSECURE_SECRETS = {
    "change-me-in-production",
    "change-me-in-production-use-a-long-random-string",
    "dev-secret-key-change-in-production",
}


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

    class Config:
        env_file = ".env"

    def validate_runtime(self) -> None:
        if not self.DEBUG and self.SECRET_KEY in INSECURE_SECRETS:
            raise RuntimeError(
                "SECRET_KEY is set to an insecure default. "
                "Set a strong SECRET_KEY in the environment before running with DEBUG=false."
            )


settings = Settings()
settings.validate_runtime()
