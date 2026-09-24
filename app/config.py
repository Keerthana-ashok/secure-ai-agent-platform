from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    llm_api_key: Optional[str] = None
    model_name: str = "gpt-default"
    temperature: float = 0.7
    max_tokens: int = 256
    provider_url: str = "https://api.example.com/v1/generate"
    timeout: int = 10

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
