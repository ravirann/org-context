"""Offline demo GitHub connector: pull requests and code documentation."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_ORG = "https://github.demo.dev/demo-org"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="gh-pr-801",
            doc_type="pr",
            title="payments-api: add idempotency keys to POST /v1/payments/charge",
            content=(
                "This PR enforces Idempotency-Key headers on the charge endpoint. Requests "
                "without a key are rejected with a 400 and the failure is recorded in "
                "payment_attempts for later analysis.\n\n"
                "The key is unique per merchant and stored alongside the payments row, so a "
                "retried webhook or a double-clicked checkout cannot create a second charge. "
                "Rollout is gated behind the strict_idempotency feature flag.\n\n"
                "Includes contract tests pinning the 400 response schema so mobile-bff and "
                "web-app clients fail loudly instead of silently retrying."
            ),
            url=f"{_ORG}/payments-api/pull/801",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"pr_number": 801, "labels": ["payments", "api", "idempotency"]},
            last_activity_at=demo_timestamp(20),
        ),
        RawItem(
            external_id="gh-pr-803",
            doc_type="pr",
            title="payments-api: fix duplicate charge on webhook retry",
            content=(
                "A merchant reported that card 4242424242424242 was charged twice after a "
                "Stripe webhook retry storm; the customer wrote in from shopper@example.com "
                "with both receipts attached.\n\n"
                "Root cause: our webhook handler retried with a fixed 5 second delay and no "
                "deduplication. This change aligns the handler with ADR-0042: exponential "
                "backoff with full jitter, base 200ms, cap 30s, max 6 attempts, and "
                "deduplication on event_id before writing to the payments table.\n\n"
                "Added a regression test that replays the same webhook event twice and "
                "asserts a single side effect."
            ),
            url=f"{_ORG}/payments-api/pull/803",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="payments-retry-policy",
            metadata={
                "pr_number": 803,
                "labels": ["bug", "payments", "webhooks"],
                "stance": "exponential_backoff",
            },
            last_activity_at=demo_timestamp(12),
        ),
        RawItem(
            external_id="gh-pr-812",
            doc_type="pr",
            title="auth-service: rotate JWT signing keys and shorten grace window",
            content=(
                "Rotates the RS256 signing keys for POST /v1/auth/token and shortens the "
                "old-key grace window from 24h to 2h.\n\n"
                "The sessions table keeps the key id per token so verification can pick the "
                "right public key during the overlap. A follow-up will automate rotation "
                "via the infra-terraform pipeline."
            ),
            url=f"{_ORG}/auth-service/pull/812",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            acl=RawAcl(public=False, team_names=["Platform"]),
            metadata={"pr_number": 812, "labels": ["security", "auth"]},
            last_activity_at=demo_timestamp(34),
        ),
        RawItem(
            external_id="gh-pr-818",
            doc_type="pr",
            title="billing-worker: batch invoice generation with outbox publishing",
            content=(
                "Moves invoice generation to day-sized batches and publishes "
                "invoice.created events through the outbox in notification_jobs.\n\n"
                "Consumers must tolerate at-least-once delivery and deduplicate on "
                "event_id. The batch_invoicing flag pauses real-time generation while a "
                "backfill is running to avoid double counting.\n\n"
                "Contains revenue-sensitive queries, so review is restricted to the "
                "Payments team until the finance sign-off lands."
            ),
            url=f"{_ORG}/billing-worker/pull/818",
            author_email="nina@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            acl=RawAcl(public=False, team_names=["Payments"]),
            metadata={"pr_number": 818, "labels": ["billing", "outbox"]},
            last_activity_at=demo_timestamp(45),
        ),
        RawItem(
            external_id="gh-pr-825",
            doc_type="pr",
            title="web-app: migrate search results to cursor pagination",
            content=(
                "Offset pagination against search_index timed out beyond 100k rows. This "
                "migrates the web-app results page to the opaque next_cursor token "
                "returned by GET /v1/search, per the pagination ADR.\n\n"
                "Includes a regression test paging past 100k seeded rows and a fallback "
                "banner when search-svc returns a stale cursor."
            ),
            url=f"{_ORG}/web-app/pull/825",
            author_email="jade@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"pr_number": 825, "labels": ["search", "pagination"]},
            last_activity_at=demo_timestamp(8),
        ),
        RawItem(
            external_id="gh-pr-830",
            doc_type="pr",
            title="mobile-bff: cache the home feed with edge invalidation",
            content=(
                "Caches GET /v1/mobile/home at the edge for 60 seconds with explicit "
                "invalidation on payments and notifications events.\n\n"
                "p95 latency dropped from 450ms to 120ms in the canary. The edge_caching "
                "flag controls rollout; automatic rollback triggers when the 5xx ratio "
                "exceeds 2% against the control group."
            ),
            url=f"{_ORG}/mobile-bff/pull/830",
            author_email="kenji@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            metadata={"pr_number": 830, "labels": ["performance", "mobile"]},
            last_activity_at=demo_timestamp(90),
        ),
        RawItem(
            external_id="gh-code-retry",
            doc_type="code",
            title="payments-api: retry helper module",
            content=(
                "src/payments_api/retry.py implements the shared retry helper. Delays are "
                "exponential with full jitter: base 200ms, factor 2, cap 30s, max 6 "
                "attempts, matching ADR-0042.\n\n"
                "Callers pass an idempotency key; the helper refuses to retry mutating "
                "calls without one. Pool saturation is guarded by a circuit breaker that "
                "opens when utilization stays above 80% for five minutes."
            ),
            url=f"{_ORG}/payments-api/blob/main/src/payments_api/retry.py",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"labels": ["code-doc"], "path": "src/payments_api/retry.py"},
            last_activity_at=demo_timestamp(60),
        ),
        RawItem(
            external_id="gh-code-webhooks",
            doc_type="code",
            title="payments-api: webhook signature verification",
            content=(
                "src/payments_api/webhooks.py verifies provider signatures before "
                "enqueueing work. Invalid signatures return 401 and increment a metric "
                "that alerts SRE on sustained failures.\n\n"
                "Events are deduplicated on event_id against the payments table before "
                "any state change; replayed events are acknowledged but ignored."
            ),
            url=f"{_ORG}/payments-api/blob/main/src/payments_api/webhooks.py",
            author_email="nina@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"labels": ["code-doc"], "path": "src/payments_api/webhooks.py"},
            last_activity_at=demo_timestamp(150),
        ),
        RawItem(
            external_id="gh-code-outbox",
            doc_type="code",
            title="notifications: outbox publisher",
            content=(
                "src/notifications/outbox.py drains the notification_jobs outbox and "
                "publishes domain events asynchronously. Delivery is at-least-once; "
                "consumers deduplicate on event_id.\n\n"
                "Failed publishes dead-letter after 5 attempts and page the on-call via "
                "the SRE alert channel."
            ),
            url=f"{_ORG}/notifications/blob/main/src/notifications/outbox.py",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"labels": ["code-doc"], "path": "src/notifications/outbox.py"},
            last_activity_at=demo_timestamp(210),
        ),
        RawItem(
            external_id="gh-code-authmw",
            doc_type="code",
            title="auth-service: session middleware internals",
            content=(
                "src/auth_service/middleware.py validates bearer tokens against the "
                "sessions table and attaches the resolved principal to the request.\n\n"
                "This document describes the token pinning scheme and the emergency "
                "kill-switch, so access is limited to named platform owners."
            ),
            url=f"{_ORG}/auth-service/blob/main/src/auth_service/middleware.py",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            acl=RawAcl(
                public=False,
                user_emails=["admin@demo.dev", "priya@demo.dev"],
            ),
            metadata={"labels": ["code-doc"], "path": "src/auth_service/middleware.py"},
            last_activity_at=demo_timestamp(30),
        ),
    ]


class GitHubConnector:
    """Deterministic demo connector for the ``github`` source type."""

    source_type: ClassVar[str] = "github"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's PRs and code docs (offline, deterministic)."""
        return _items()


register(GitHubConnector())
