from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://localhost/sungano"
    JWT_SECRET: str = "sungano-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    MAILJET_API_KEY: str = ""
    MAILJET_SECRET_KEY: str = ""
    MAILJET_FROM_EMAIL: str = "hello@sungano.app"
    MAILJET_FROM_NAME: str = "Sungano"

    FRONTEND_URL: str = "https://sungano.app"
    APP_DEEP_LINK: str = "sungano://"

    SENTRY_DSN: Optional[str] = None
    POSTHOG_KEY: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
