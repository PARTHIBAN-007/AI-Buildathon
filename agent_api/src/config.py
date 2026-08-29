from pydantic import AliasChoices, Field
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    EXOTEL_BASE_URL: str = Field(..., env="EXOTEL_BASE_URL")
    EXOTEL_ACCOUNT_SID: str = Field(..., env="EXOTEL_ACCOUNT_SID")
    EXOTEL_API_KEY: str = Field(..., env="EXOTEL_API_KEY")
    EXOTEL_API_TOKEN: str = Field(..., env="EXOTEL_API_TOKEN")
    EXOTEL_PHONE_NUMBER: str = Field(..., env="EXOTEL_PHONE_NUMBER")

    SARVAM_API_KEY: str = Field(..., env="SARVAM_API_KEY")

    RAZORPAY_API_KEY: str = Field(..., env = "RAZORPAY_API_KEY")
    RAZORPAY_KEY_SECRET: str = Field(..., env = "RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: str = Field(..., env = "RAZORPAY_WEBHOOK_SECRET")

    META_APP_ID: str = Field(..., env = "META_APP_ID")
    META_ACCESS_TOKEN: str = Field(..., env = "META_ACCESS_TOKEN")
    META_VERIFY_TOKEN: str = Field(..., env = "META_VERIFY_TOKEN")
    META_APP_SECRET: str = Field(..., env = "META_APP_SECRET")
    META_BUSINESS_ID: str = Field(..., env = "META_BUSINESS_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()