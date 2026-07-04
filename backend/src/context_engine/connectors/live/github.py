"""Live GitHub connector: pull requests, repo docs, and issues via the REST API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.http import build_client, request_json
from context_engine.connectors.live.util import (
    cursor_since,
    now_utc,
    parse_iso,
    resolve_acl,
    to_iso,
)
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

DEFAULT_API_URL = "https://api.github.com"
_DOC_PATHS = ("README.md",)
_PER_PAGE = 100
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
"""Sentinel "since" for full enumeration (no cursor filtering)."""


class GitHubLiveConnector:
    """Fetch PRs (+bodies+review comments), repo docs, and issues from GitHub."""

    source_type: ClassVar[str] = "github"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            base_url=str(config.get("api_url") or DEFAULT_API_URL).rstrip("/"),
            bearer_token=str(config["token"]),
            transport=self._transport,
            headers={"X-GitHub-Api-Version": "2022-11-28"},
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        repos: list[str] = list(config.get("repos") or [])
        org = str(config.get("org") or "")

        pr_since = cursor_since(source.sync_state, "pr_cursor", config)
        issues_since = cursor_since(source.sync_state, "issues_cursor", config)
        docs_since = cursor_since(source.sync_state, "docs_cursor", config)

        items: list[RawItem] = []
        max_pr = pr_since
        max_issue = issues_since
        max_doc = docs_since

        async with self._client(source) as client:
            for repo in repos:
                full = f"{org}/{repo}" if org else repo
                private = await self._repo_is_private(client, full)
                acl = resolve_acl(config, private=private)

                for pr in await self._list_prs(client, full):
                    updated = parse_iso(str(pr.get("updated_at", "")))
                    if updated is not None and updated <= pr_since:
                        continue
                    resolved = await self._build_pr(client, full, pr, acl, config)
                    if resolved is None:
                        continue
                    items.append(resolved)
                    if updated is not None and updated > max_pr:
                        max_pr = updated

                for issue in await self._list_issues(client, full, issues_since):
                    built = self._issue_item(full, issue, acl, config)
                    if built is None:
                        continue
                    built_item, updated = built
                    items.append(built_item)
                    if updated is not None and updated > max_issue:
                        max_issue = updated

                for doc in await self._list_docs(client, full, acl, config, docs_since):
                    doc_item, updated = doc
                    items.append(doc_item)
                    if updated is not None and updated > max_doc:
                        max_doc = updated

        source.sync_state["pr_cursor"] = to_iso(max_pr)
        source.sync_state["issues_cursor"] = to_iso(max_issue)
        source.sync_state["docs_cursor"] = to_iso(max_doc)
        return items

    async def list_active_external_ids(self, source: Source) -> list[str] | None:
        """Enumerate every external id currently present upstream (for pruning).

        Unlike ``fetch`` (which returns only the cursor delta), this lists the
        full current set of PRs, issues, and docs so vanished documents can be
        deprecated. Returns ``None`` if the enumeration fails, so a transient
        upstream error never triggers a spurious prune.
        """
        config = source.config
        repos: list[str] = list(config.get("repos") or [])
        org = str(config.get("org") or "")

        active: list[str] = []
        try:
            async with self._client(source) as client:
                for repo in repos:
                    full = f"{org}/{repo}" if org else repo
                    for pr in await self._list_prs(client, full):
                        try:
                            active.append(f"pr-{int(pr['number'])}")
                        except (KeyError, TypeError, ValueError):
                            continue
                    for issue in await self._list_issues(client, full, _EPOCH):
                        try:
                            active.append(f"issue-{full.split('/')[-1]}-{int(issue['number'])}")
                        except (KeyError, TypeError, ValueError):
                            continue
                    for path in _DOC_PATHS:
                        try:
                            resp = await request_json(
                                client, "GET", f"/repos/{full}/contents/{path}"
                            )
                        except Exception:  # noqa: BLE001 — missing docs are not an error
                            continue
                        if isinstance(resp, dict) and _decode_content(resp):
                            active.append(f"doc-{full.split('/')[-1]}-{path}")
        except Exception:  # noqa: BLE001 — never prune on a failed enumeration
            logger.warning("github_list_active_failed", repos=repos)
            return None
        return active

    async def _repo_is_private(self, client: httpx.AsyncClient, full: str) -> bool:
        try:
            repo = await request_json(client, "GET", f"/repos/{full}")
        except Exception:  # noqa: BLE001 — visibility unknown → treat as public
            logger.warning("github_repo_lookup_failed", repo=full)
            return False
        return bool(repo.get("private"))

    async def _list_prs(self, client: httpx.AsyncClient, full: str) -> list[dict[str, Any]]:
        prs = await request_json(
            client,
            "GET",
            f"/repos/{full}/pulls",
            params={"state": "all", "sort": "updated", "direction": "desc", "per_page": _PER_PAGE},
        )
        return prs if isinstance(prs, list) else []

    async def _build_pr(
        self,
        client: httpx.AsyncClient,
        full: str,
        pr: dict[str, Any],
        acl: Any,
        config: dict[str, Any],
    ) -> RawItem | None:
        try:
            number = int(pr["number"])
            title = str(pr["title"])
        except (KeyError, TypeError, ValueError):
            logger.warning("github_pr_malformed", repo=full, keys=list(pr))
            return None

        body = str(pr.get("body") or "")
        comments = await self._review_comments(client, full, number)
        content = title
        if body:
            content += f"\n\n{body}"
        if comments:
            joined = "\n".join(f"- {c}" for c in comments)
            content += f"\n\nReview comments:\n{joined}"

        return RawItem(
            external_id=f"pr-{number}",
            doc_type="pr",
            title=title,
            content=content,
            url=str(pr.get("html_url") or ""),
            author_email=_user_email(pr.get("user")),
            repo=full.split("/")[-1],
            service=full.split("/")[-1],
            team_name=config.get("team_name"),
            acl=acl,
            metadata={"pr_number": number, "state": pr.get("state"), "labels": _labels(pr)},
            last_activity_at=parse_iso(str(pr.get("updated_at", ""))) or now_utc(),
        )

    async def _review_comments(
        self, client: httpx.AsyncClient, full: str, number: int
    ) -> list[str]:
        try:
            raw = await request_json(
                client,
                "GET",
                f"/repos/{full}/pulls/{number}/comments",
                params={"per_page": 5},
            )
        except Exception:  # noqa: BLE001 — comments are best-effort
            return []
        if not isinstance(raw, list):
            return []
        return [str(c.get("body", "")).strip() for c in raw[:5] if c.get("body")]

    async def _list_issues(
        self, client: httpx.AsyncClient, full: str, since: datetime
    ) -> list[dict[str, Any]]:
        issues = await request_json(
            client,
            "GET",
            f"/repos/{full}/issues",
            params={"state": "all", "since": to_iso(since), "per_page": _PER_PAGE},
        )
        if not isinstance(issues, list):
            return []
        # The issues endpoint also returns PRs; drop those (they have pull_request).
        return [i for i in issues if "pull_request" not in i]

    def _issue_item(
        self, full: str, issue: dict[str, Any], acl: Any, config: dict[str, Any]
    ) -> tuple[RawItem, datetime | None] | None:
        try:
            number = int(issue["number"])
            title = str(issue["title"])
        except (KeyError, TypeError, ValueError):
            logger.warning("github_issue_malformed", repo=full, keys=list(issue))
            return None
        body = str(issue.get("body") or "")
        content = f"{title}\n\n{body}" if body else title
        updated = parse_iso(str(issue.get("updated_at", "")))
        item = RawItem(
            external_id=f"issue-{full.split('/')[-1]}-{number}",
            doc_type="ticket",
            title=title,
            content=content,
            url=str(issue.get("html_url") or ""),
            author_email=_user_email(issue.get("user")),
            repo=full.split("/")[-1],
            service=full.split("/")[-1],
            team_name=config.get("team_name"),
            acl=acl,
            metadata={
                "issue_number": number,
                "state": issue.get("state"),
                "labels": _labels(issue),
            },
            last_activity_at=updated or now_utc(),
        )
        return item, updated

    async def _list_docs(
        self,
        client: httpx.AsyncClient,
        full: str,
        acl: Any,
        config: dict[str, Any],
        since: datetime,
    ) -> list[tuple[RawItem, datetime | None]]:
        out: list[tuple[RawItem, datetime | None]] = []
        for path in _DOC_PATHS:
            try:
                content_resp = await request_json(client, "GET", f"/repos/{full}/contents/{path}")
            except Exception:  # noqa: BLE001 — missing docs are not an error
                continue
            if not isinstance(content_resp, dict):
                continue
            decoded = _decode_content(content_resp)
            if not decoded:
                continue
            item = RawItem(
                external_id=f"doc-{full.split('/')[-1]}-{path}",
                doc_type="code",
                title=f"{full.split('/')[-1]}: {path}",
                content=decoded,
                url=str(content_resp.get("html_url") or ""),
                repo=full.split("/")[-1],
                service=full.split("/")[-1],
                team_name=config.get("team_name"),
                acl=acl,
                metadata={"path": path},
                last_activity_at=now_utc(),
            )
            out.append((item, now_utc()))
        return out


def _user_email(user: Any) -> str | None:
    if isinstance(user, dict):
        email = user.get("email")
        if email:
            return str(email)
    return None


def _labels(payload: dict[str, Any]) -> list[str]:
    labels = payload.get("labels") or []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict) and label.get("name"):
            names.append(str(label["name"]))
        elif isinstance(label, str):
            names.append(label)
    return names


def _decode_content(payload: dict[str, Any]) -> str:
    import base64

    encoding = payload.get("encoding")
    raw = payload.get("content")
    if encoding == "base64" and isinstance(raw, str):
        try:
            return base64.b64decode(raw).decode("utf-8", errors="replace").strip()
        except (ValueError, TypeError):
            return ""
    return str(raw or "").strip()
