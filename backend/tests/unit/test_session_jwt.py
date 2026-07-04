"""Unit tests for the HS256 session and OIDC-state JWT helpers."""

from __future__ import annotations

import time

import pytest

from context_engine.api.oidc import (
    SessionError,
    issue_session_token,
    issue_state_token,
    verify_session_token,
    verify_state_token,
)
from context_engine.config.settings import Settings

SETTINGS = Settings(secret_key="unit-test-secret", session_ttl_hours=12)


def test_session_round_trip() -> None:
    token = issue_session_token(SETTINGS, user_id="u-1", email="a@demo.dev")
    claims = verify_session_token(SETTINGS, token)
    assert claims.sub == "u-1"
    assert claims.email == "a@demo.dev"


def test_session_expired_rejected() -> None:
    past = int(time.time()) - 13 * 3600  # issued 13h ago, ttl 12h
    token = issue_session_token(SETTINGS, user_id="u-1", email="a@demo.dev", now=past)
    with pytest.raises(SessionError):
        verify_session_token(SETTINGS, token)


def test_session_tampered_signature_rejected() -> None:
    token = issue_session_token(SETTINGS, user_id="u-1", email="a@demo.dev")
    other = Settings(secret_key="a-different-secret")
    with pytest.raises(SessionError):
        verify_session_token(other, token)


def test_session_garbage_rejected() -> None:
    with pytest.raises(SessionError):
        verify_session_token(SETTINGS, "not.a.jwt")


def test_state_round_trip() -> None:
    token = issue_state_token(SETTINGS, redirect_after="/sources")
    payload = verify_state_token(SETTINGS, token)
    assert payload["redirect_after"] == "/sources"
    assert "nonce" in payload


def test_state_expired_rejected() -> None:
    past = int(time.time()) - 601  # state ttl is 600s
    token = issue_state_token(SETTINGS, now=past)
    with pytest.raises(SessionError):
        verify_state_token(SETTINGS, token)
