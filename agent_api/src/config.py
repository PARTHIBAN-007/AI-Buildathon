from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server / Webhook Domain
    NGROK_URL: Optional[str] = Field(default=None, alias="NGROK_URL")

    # Database
    POSTGRES_DSN: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_api",
        alias="POSTGRES_DSN",
    )

    # Celery
    CELERY_BROKER_URL: Optional[str] = Field(default=None, alias="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, alias="CELERY_RESULT_BACKEND")

    # Sarvam Outbound Voice API
    SARVAM_API_KEY: Optional[str] = Field(default=None, alias="SARVAM_API_KEY")
    SARVAM_ORG_ID: Optional[str] = Field(default=None, alias="SARVAM_ORG_ID")
    SARVAM_WORKSPACE_ID: Optional[str] = Field(default=None, alias="SARVAM_WORKSPACE_ID")
    SARVAM_APP_ID: Optional[str] = Field(default=None, alias="SARVAM_APP_ID")
    SARVAM_APP_VERSION: str = Field(default="1", alias="SARVAM_APP_VERSION")
    SARVAM_CONNECTION_ID: Optional[str] = Field(default=None, alias="SARVAM_CONNECTION_ID")
    SARVAM_AGENT_PHONE_NUMBER: Optional[str] = Field(default=None, alias="SARVAM_AGENT_PHONE_NUMBER")

    # Razorpay
    RAZORPAY_API_KEY: Optional[str] = Field(default=None, alias="RAZORPAY_API_KEY")
    RAZORPAY_KEY_SECRET: Optional[str] = Field(default=None, alias="RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = Field(default=None, alias="RAZORPAY_WEBHOOK_SECRET")

    # OpenRouter
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    OPENROUTER_API_BASE: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_API_BASE")
    OPENROUTER_MODEL: str = Field(default="openai/gpt-5.6-luna", alias="OPENROUTER_MODEL")

    # Meta / WhatsApp
    META_APP_ID: Optional[str] = Field(default=None, alias="META_APP_ID")
    META_ACCESS_TOKEN: Optional[str] = Field(default=None, alias="META_ACCESS_TOKEN")
    META_PHONE_NUMBER_ID: Optional[str] = Field(default=None, alias="META_PHONE_NUMBER_ID")
    META_VERIFY_TOKEN: Optional[str] = Field(default=None, alias="META_VERIFY_TOKEN")
    META_APP_SECRET: Optional[str] = Field(default=None, alias="META_APP_SECRET")
    META_BUSINESS_ID: Optional[str] = Field(default=None, alias="META_BUSINESS_ID")

    @property
    def SARVAM_BASE_URL(self) -> str:
        org = self.SARVAM_ORG_ID 
        ws = self.SARVAM_WORKSPACE_ID 
        return f"https://apps.sarvam.ai/api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds"

    @property
    def SARVAM_WEBHOOK_URL(self) -> str:
        ngrok = self.NGROK_URL
        return f"{ngrok}/sarvam"

    def _get_base_postgres_url(self) -> str:
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