from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SYNTHARA_", env_file=".env", extra="ignore")

    provider_timeout_seconds: float = Field(default=15.0, gt=0)
    max_iterations: int = Field(default=2, ge=1, le=5)
    max_sources_per_provider: int = Field(default=4, ge=1, le=10)
    min_accepted_sources: int = Field(default=3, ge=1, le=30)
    provider_max_retries: int = Field(default=2, ge=0, le=5)
    provider_backoff_seconds: float = Field(default=0.25, ge=0)

    web_search_provider: Literal["tavily"] = Field(default="tavily")
    tavily_api_key: str | None = None
    tavily_search_endpoint: str = Field(default="https://api.tavily.com/search")
    tavily_search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = Field(default="advanced")

    alphaxiv_bridge_url: str = Field(default="http://127.0.0.1:4100")
    alphaxiv_bridge_timeout_seconds: float = Field(default=20.0, gt=0)

    gemini_api_key: str | None = None
    gemini_model: str = Field(default="gemini-2.5-flash")
    gemini_api_endpoint: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    gemini_temperature: float = Field(default=0.2, ge=0.0, le=2.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
