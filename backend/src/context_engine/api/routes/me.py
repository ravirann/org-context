"""GET /v1/me — the current authenticated user (drives frontend RBAC states)."""

from __future__ import annotations

from fastapi import APIRouter

from context_engine.api.deps import UserDep
from context_engine.api.schemas import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(user: UserDep) -> MeOut:
    return MeOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        team_name=user.team.name if user.team is not None else None,
    )
