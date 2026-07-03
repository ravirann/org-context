"""Application settings, loaded from environment variables with the ``CE_`` prefix."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the context engine."""

    model_config = SettingsConfigDict(env_prefix="CE_", extra="ignore")

    database_url: str = "postgresql+asyncpg://ce:ce@localhost:5433/context_engine"
    test_database_url: str = "postgresql+asyncpg://ce:ce@localhost:5433/context_engine_test"
    redis_url: str = "redis://localhost:6380/0"

    env: Literal["dev", "docker", "test"] = "dev"

    embedding_dim: int = 384

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
