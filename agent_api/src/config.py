from pydantic import AliasChoices, Field
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import typing

load_dotenv()


class Settings(BaseSettings):
    EXOTEL_BASE_URL: str = Field(..., env="EXOTEL_BASE_URL")
    EXOTEL_ACCOUNT_SID: str = Field(..., env="EXOTEL_ACCOUNT_SID")
    EXOTEL_API_KEY: str = Field(..., env="EXOTEL_API_KEY")
    EXOTEL_API_TOKEN: str = Field(..., env="EXOTEL_API_TOKEN")
    EXOTEL_PHONE_NUMBER: str = Field(..., env="EXOTEL_PHONE_NUMBER")

    SARVAM_API_KEY: str = Field(..., env="SARVAM_API_KEY")
    SARVAM_BASE_URL: str = Field("https://api.sarvam.example", env="SARVAM_BASE_URL")

    META_WHATSAPP_TOKEN: typing.Optional[str] = Field(None)
    META_WHATSAPP_PHONE_ID: typing.Optional[str] = Field(None)
    VERIFY_TOKEN: typing.Optional[str] = Field(None)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()