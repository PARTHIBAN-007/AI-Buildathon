from pydantic import Field
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


@lru_cache(maxsize=1)
def get_settings():
    return Settings()