
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Digital Wallet API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Transaction limits; can be overridden through environment variables.
    MAX_SINGLE_DEPOSIT: Decimal = Decimal("50000.00")
    MAX_SINGLE_WITHDRAWAL: Decimal = Decimal("25000.00")
    MAX_SINGLE_TRANSFER: Decimal = Decimal("25000.00")
    DAILY_OUTGOING_LIMIT: Decimal = Decimal("50000.00")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
