from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Phase 0 application settings."""

    service_name: str = "axiom-ops"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="AXIOMOPS_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
