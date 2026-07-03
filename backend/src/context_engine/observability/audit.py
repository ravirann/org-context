"""Convenience re-export of the audit log writer."""

from __future__ import annotations

from context_engine.storage.repositories import write_audit

__all__ = ["write_audit"]
