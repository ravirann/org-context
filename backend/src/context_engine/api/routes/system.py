"""System info endpoint [admin]: embedding provider, auth mode, queue depth, version."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from context_engine.api.deps import UserDep, require_roles
from context_engine.config.settings import get_settings
from context_engine.indexing.embeddings import get_embedding_provider
from context_engine.observability.logging import get_logger
from context_engine.storage.models import UserRole

logger = get_logger(__name__)

router = APIRouter(tags=["system"], dependencies=[Depends(require_roles(UserRole.admin))])

API_VERSION = "0.3.0"
_QUEUE = "dramatiq:default"


class EmbeddingInfo(BaseModel):
    provider: str
    model: str
    dim: int


class SystemInfo(BaseModel):
    embedding: EmbeddingInfo
    auth_mode: str
    queue_depth: int | None
    version: str


async def _queue_depth() -> int | None:
    """Return the dramatiq default-queue length, or ``None`` on any redis error."""
    settings = get_settings()
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        try:
            return int(await client.llen(_QUEUE))
        finally:
            await client.aclose()
    except Exception as exc:  # redis down / not installed / any error → null
        logger.debug("system_queue_depth_unavailable", error=str(exc))
        return None


@router.get("/system/info", response_model=SystemInfo)
async def system_info(user: UserDep) -> SystemInfo:
    """Report the active embedding provider, auth mode, queue depth, and API version."""
    provider = get_embedding_provider()
    return SystemInfo(
        embedding=EmbeddingInfo(provider=provider.name, model=provider.model, dim=provider.dim),
        auth_mode=get_settings().auth_mode,
        queue_depth=await _queue_depth(),
        version=API_VERSION,
    )
