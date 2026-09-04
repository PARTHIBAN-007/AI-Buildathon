from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


    # Database
    POSTGRES_DSN: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_api",
        alias="POSTGRES_DSN",
    )

    # Optional explicit Celery overrides (falls back to POSTGRES_DSN)
    CELERY_BROKER_URL: Optional[str] = Field(default=None, alias="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, alias="CELERY_RESULT_BACKEND")

    # Exotel
    EXOTEL_BASE_URL: Optional[str] = Field(default=None, alias="EXOTEL_BASE_URL")
    EXOTEL_ACCOUNT_SID: Optional[str] = Field(default=None, alias="EXOTEL_ACCOUNT_SID")
    EXOTEL_API_KEY: Optional[str] = Field(default=None, alias="EXOTEL_API_KEY")
    EXOTEL_API_TOKEN: Optional[str] = Field(default=None, alias="EXOTEL_API_TOKEN")
    EXOTEL_PHONE_NUMBER: Optional[str] = Field(default=None, alias="EXOTEL_PHONE_NUMBER")

    # Sarvam
    SARVAM_API_KEY: Optional[str] = Field(default=None, alias="SARVAM_API_KEY")
    ORG_ID: Optional[str] = Field(default=None, alias="ORG_ID")
    WORKSPACE_ID: Optional[str] = Field(default=None, alias="WORKSPACE_ID")

    # Razorpay
    RAZORPAY_API_KEY: Optional[str] = Field(default=None, alias="RAZORPAY_API_KEY")
    RAZORPAY_KEY_SECRET: Optional[str] = Field(default=None, alias="RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = Field(default=None, alias="RAZORPAY_WEBHOOK_SECRET")

    # OpenRouter
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    OPENROUTER_API_BASE: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_API_BASE")
    OPENROUTER_MODEL: str = Field(default="openai/gpt-5.6-luna", alias="OPENROUTER_MODEL")

    # Meta
    META_APP_ID: Optional[str] = Field(default=None, alias="META_APP_ID")
    META_ACCESS_TOKEN: Optional[str] = Field(default=None, alias="META_ACCESS_TOKEN")
    META_PHONE_NUMBER_ID: Optional[str] = Field(default=None, alias="META_PHONE_NUMBER_ID")
    META_VERIFY_TOKEN: Optional[str] = Field(default=None, alias="META_VERIFY_TOKEN")
    META_APP_SECRET: Optional[str] = Field(default=None, alias="META_APP_SECRET")
    META_BUSINESS_ID: Optional[str] = Field(default=None, alias="META_BUSINESS_ID")

    @property
    def SARVAM_BASE_URL(self) -> str:
        org = self.ORG_ID or ""
        ws = self.WORKSPACE_ID or ""
        return f"https://apps.sarvam.ai/api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds"

    def _get_base_postgres_url(self) -> str:
        """Strips driver prefixes like +psycopg2 or +asyncpg for Celery Kombu compatibility."""
        return (
            self.POSTGRES_DSN
            .replace("postgresql+psycopg2://", "postgresql://")
            .replace("postgresql+asyncpg://", "postgresql://")
        )

    @property
    def CELERY_BROKER(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return self._get_base_postgres_url().replace("postgresql://", "sqla+postgresql://")

    @property
    def CELERY_BACKEND(self) -> str:
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return self._get_base_postgres_url().replace("postgresql://", "db+postgresql://")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()