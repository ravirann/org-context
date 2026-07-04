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

    # --- Authentication (dual mode, see docs/HARDENING_CONTRACT.md §1) -----------------
    auth_mode: Literal["demo", "oidc"] = "demo"
    secret_key: str = "dev-secret-change-me"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_url: str = "http://localhost:8000/v1/auth/callback"
    session_ttl_hours: int = 12
    allowed_email_domains: list[str] = []
    cookie_secure: bool = False

    embedding_dim: int = 384

    # --- Embeddings (see docs/PHASE3_CONTRACT.md §A, docs/EMBEDDINGS.md) --------------
    embedding_provider: str = "deterministic"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_batch_size: int = 64

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
