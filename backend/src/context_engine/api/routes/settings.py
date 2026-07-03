"""Settings endpoints [admin]: read and patch the app_settings document."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from context_engine.api.deps import SessionDep, UserDep, require_roles
from context_engine.api.schemas import SettingsOut
from context_engine.config.constants import (
    SETTINGS_AUTHORITY_RULES,
    SETTINGS_EVAL_THRESHOLDS,
    SETTINGS_FEATURE_FLAGS,
    SETTINGS_FRESHNESS_WINDOW_DAYS,
    SETTINGS_PII_REDACTION,
    SETTINGS_RETENTION,
    SETTINGS_RETRIEVAL_WEIGHTS,
    SETTINGS_TOKEN_BUDGET,
)
from context_engine.storage.models import UserRole
from context_engine.storage.repositories import get_setting, set_setting, write_audit

router = APIRouter(tags=["settings"], dependencies=[Depends(require_roles(UserRole.admin))])

_KEYS = [
    SETTINGS_RETRIEVAL_WEIGHTS,
    SETTINGS_FRESHNESS_WINDOW_DAYS,
    SETTINGS_AUTHORITY_RULES,
    SETTINGS_EVAL_THRESHOLDS,
    SETTINGS_RETENTION,
    SETTINGS_PII_REDACTION,
    SETTINGS_FEATURE_FLAGS,
    SETTINGS_TOKEN_BUDGET,
]


async def _read_settings(session: SessionDep) -> SettingsOut:
    values: dict[str, Any] = {}
    for key in _KEYS:
        values[key] = await get_setting(session, key, default={})
    return SettingsOut(**values)


@router.get("/settings", response_model=SettingsOut)
async def get_settings_doc(session: SessionDep, user: UserDep) -> SettingsOut:
    return await _read_settings(session)


@router.patch("/settings", response_model=SettingsOut)
async def patch_settings(body: dict[str, Any], session: SessionDep, user: UserDep) -> SettingsOut:
    changed: list[str] = []
    for key, value in body.items():
        if key in _KEYS:
            await set_setting(session, key, value)
            changed.append(key)
    await write_audit(session, user.id, "settings.update", "app_settings", None, {"keys": changed})
    await session.flush()
    return await _read_settings(session)
