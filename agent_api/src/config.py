from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    MODEL_NAME: str = "agent-api"

    POSTGRES_DSN: str = Field( alias="POSTGRES_DSN")

    EXOTEL_BASE_URL: str | None = Field(default=None, alias="EXOTEL_BASE_URL")
    EXOTEL_ACCOUNT_SID: str | None = Field(default=None, alias="EXOTEL_ACCOUNT_SID")
    EXOTEL_API_KEY: str | None = Field(default=None, alias="EXOTEL_API_KEY")
    EXOTEL_API_TOKEN: str | None = Field(default=None, alias="EXOTEL_API_TOKEN")
    EXOTEL_PHONE_NUMBER: str | None = Field(default=None, alias="EXOTEL_PHONE_NUMBER")

    SARVAM_API_KEY: str | None = Field(default=None, alias="SARVAM_API_KEY")
    ORG_ID: str = Field(default=None, alias="ORG_ID")
    WORKSPACE_ID: str = Field(default=None, alias="WORKSPACE_ID")
    SARVAM_BASE_URL: str = f"https://apps.sarvam.ai/api/outbounds/v1/orgs/{ORG_ID}/workspaces/{WORKSPACE_ID}/outbounds"

    RAZORPAY_API_KEY: str | None = Field(default=None, alias="RAZORPAY_API_KEY")
    RAZORPAY_KEY_SECRET: str | None = Field(default=None, alias="RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: str | None = Field(default=None, alias="RAZORPAY_WEBHOOK_SECRET")
    OPENROUTER_API_KEY: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    OPENROUTER_API_BASE: str | None = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_API_BASE")
    OPENROUTER_MODEL: str = Field(default="google/gemma-4-31b-it:free", alias="OPENROUTER_MODEL")
    POSTGRES_DSN: str = Field(default="postgresql://postgres:postgres@localhost:5432/agent_api", alias="POSTGRES_DSN")

    META_APP_ID: str | None = Field(default=None, alias="META_APP_ID")
    META_ACCESS_TOKEN: str | None = Field(default=None, alias="META_ACCESS_TOKEN")
    META_PHONE_NUMBER_ID: str | None = Field(default=None, alias="META_PHONE_NUMBER_ID")
    META_VERIFY_TOKEN: str | None = Field(default=None, alias="META_VERIFY_TOKEN")
    META_APP_SECRET: str | None = Field(default=None, alias="META_APP_SECRET")
    META_BUSINESS_ID: str | None = Field(default=None, alias="META_BUSINESS_ID")

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()