"""Offline demo CI connector: build and pipeline run records."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://ci.demo.dev/job"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="ci-4501",
            doc_type="ci_run",
            title="Build #4501: payments-api main",
            content=(
                "Build #4501 on payments-api main passed: 212 tests, 0 failed, "
                "coverage 91%. Includes the idempotency changes from PR #801. Canary "
                "verification stage green; artifact promoted to the release channel."
            ),
            url=f"{_BASE}/payments-api/4501",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"status": "pass", "build_number": 4501, "tests": 212},
            last_activity_at=demo_timestamp(1),
        ),
        RawItem(
            external_id="ci-4502",
            doc_type="ci_run",
            title="Build #4502: payments-api PR #803",
            content=(
                "Build #4502 for PR #803 failed: "
                "tests/test_flow.py::test_retry_backoff — AssertionError: expected "
                "jittered delays, got fixed 5s. 211 passed, 1 failed in 42.1s. The new "
                "regression test caught the legacy retry path still wired in the "
                "webhook handler."
            ),
            url=f"{_BASE}/payments-api/4502",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"status": "fail", "build_number": 4502, "tests": 212},
            last_activity_at=demo_timestamp(12),
        ),
        RawItem(
            external_id="ci-4487",
            doc_type="ci_run",
            title="Nightly e2e: auth-service",
            content=(
                "Nightly end-to-end run for auth-service passed: token issue/refresh "
                "round-trips, key rotation overlap, and offboarding revocation all "
                "green. 96 scenarios in 14 minutes."
            ),
            url=f"{_BASE}/auth-service/4487",
            author_email="grace@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            metadata={"status": "pass", "build_number": 4487, "tests": 96},
            last_activity_at=demo_timestamp(4),
        ),
        RawItem(
            external_id="ci-4470",
            doc_type="ci_run",
            title="Coverage gate: web-app",
            content=(
                "Coverage gate failed on web-app: statements 83.4% against the 85% "
                "threshold after the checkout refactor removed tested dead code. "
                "Follow-up ticket filed to cover the new cursor-pagination error "
                "states."
            ),
            url=f"{_BASE}/web-app/4470",
            author_email="jade@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"status": "fail", "build_number": 4470, "coverage": 83.4},
            last_activity_at=demo_timestamp(16),
        ),
        RawItem(
            external_id="ci-4455",
            doc_type="ci_run",
            title="Release mobile-bff v1.42",
            content=(
                "Release build v1.42 of mobile-bff passed and was tagged for the "
                "Monday train. Contract tests against payments-api and auth-service "
                "green; home feed cache invalidation verified in staging."
            ),
            url=f"{_BASE}/mobile-bff/4455",
            author_email="kenji@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            metadata={"status": "pass", "build_number": 4455, "version": "1.42"},
            last_activity_at=demo_timestamp(30),
        ),
        RawItem(
            external_id="ci-4440",
            doc_type="ci_run",
            title="Nightly e2e: data-pipeline",
            content=(
                "Nightly data-pipeline run failed: "
                "tests/test_backfill.py::test_day_batches off-by-one on the batch "
                "boundary (known flake, ENG-1418). All other 74 scenarios passed; "
                "rerun succeeded."
            ),
            url=f"{_BASE}/data-pipeline/4440",
            author_email="lena@demo.dev",
            repo="data-pipeline",
            service="data-pipeline",
            team_name="Data",
            metadata={"status": "fail", "build_number": 4440, "flaky": True},
            last_activity_at=demo_timestamp(44),
        ),
        RawItem(
            external_id="ci-4410",
            doc_type="ci_run",
            title="Canary verify: notifications",
            content=(
                "Canary verification for notifications passed: outbox drain rate "
                "steady, zero dead-letters during the 15 minute window, SES bounce "
                "rate nominal. Promoted to 100%."
            ),
            url=f"{_BASE}/notifications/4410",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"status": "pass", "build_number": 4410},
            last_activity_at=demo_timestamp(80),
        ),
        RawItem(
            external_id="ci-4300",
            doc_type="ci_run",
            title="Release search-svc v2.7 with rerank weights",
            content=(
                "Release build v2.7 of search-svc passed with the v2 ranking weights "
                "behind the search_rerank flag. Offline eval suite green; load test "
                "held p95 under 250ms at 2x peak traffic."
            ),
            url=f"{_BASE}/search-svc/4300",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"status": "pass", "build_number": 4300, "version": "2.7"},
            last_activity_at=demo_timestamp(140),
        ),
    ]


class CiConnector:
    """Deterministic demo connector for the ``ci`` source type."""

    source_type: ClassVar[str] = "ci"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's CI runs (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(CiConnector())
