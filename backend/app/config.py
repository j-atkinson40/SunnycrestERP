import json

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CONSOLE_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for production/delivery
    CORS_ORIGINS: str = "http://localhost:5173"
    CORS_ORIGIN_REGEX: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Google Places (optional — only needed for funeral home directory discovery)
    GOOGLE_PLACES_API_KEY: str = ""

    # Branding / identity
    APP_NAME: str = "Bridgeable"
    SUPPORT_EMAIL: str = "support@getbridgeable.com"

    # Environment: dev | staging | production
    ENVIRONMENT: str = "dev"

    # Domain configuration
    FRONTEND_URL: str = "http://localhost:5173"
    PLATFORM_DOMAIN: str = "getbridgeable.com"

    # Redis (optional — job queue degrades to DB polling without it)
    REDIS_URL: str = ""

    # Stripe (optional — only needed if billing is configured)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # QuickBooks Online OAuth (optional — only needed if QBO integration is used)
    QBO_CLIENT_ID: str = ""
    QBO_CLIENT_SECRET: str = ""
    QBO_REDIRECT_URI: str = ""

    # Email (optional — falls back to console logging when not set)
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@getbridgeable.com"
    FROM_NAME: str = "Bridgeable"

    # Twilio (optional — only needed for SMS notifications)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Platform admin seed (optional — creates initial super admin on startup)
    PLATFORM_ADMIN_EMAIL: str = ""
    PLATFORM_ADMIN_PASSWORD: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def strip_database_url(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        v = self.CORS_ORIGINS.strip()
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    model_config = {"env_file": ".env"}


settings = Settings()
