"""Live source connectors (real HTTP), routed via ``config["mode"] == "live"``.

Each live connector implements the same ``Connector`` protocol as the demo
connectors but reaches a real upstream (GitHub, Jira, Slack, Confluence) through
the shared :mod:`context_engine.connectors.live.http` helper. Cursors live in
``source.sync_state`` and are advanced in place; the ingestion pipeline persists
the mutation after a successful sync.
"""

from __future__ import annotations

from context_engine.connectors.live.confluence import ConfluenceLiveConnector
from context_engine.connectors.live.gcal import GCalLiveConnector
from context_engine.connectors.live.gdrive import GDriveLiveConnector
from context_engine.connectors.live.github import GitHubLiveConnector
from context_engine.connectors.live.gmail import GmailLiveConnector
from context_engine.connectors.live.http import ConnectorAuthError, ConnectorError
from context_engine.connectors.live.jira import JiraLiveConnector
from context_engine.connectors.live.linear import LinearLiveConnector
from context_engine.connectors.live.notion import NotionLiveConnector
from context_engine.connectors.live.slack import SlackLiveConnector
from context_engine.connectors.live.zendesk import ZendeskLiveConnector

# Live connectors are instantiated per-fetch (they read config off the Source),
# so the registry maps a source_type to its connector *class*.
LIVE_CONNECTORS: dict[str, type] = {
    GitHubLiveConnector.source_type: GitHubLiveConnector,
    JiraLiveConnector.source_type: JiraLiveConnector,
    SlackLiveConnector.source_type: SlackLiveConnector,
    ConfluenceLiveConnector.source_type: ConfluenceLiveConnector,
    NotionLiveConnector.source_type: NotionLiveConnector,
    LinearLiveConnector.source_type: LinearLiveConnector,
    ZendeskLiveConnector.source_type: ZendeskLiveConnector,
    GDriveLiveConnector.source_type: GDriveLiveConnector,
    GmailLiveConnector.source_type: GmailLiveConnector,
    GCalLiveConnector.source_type: GCalLiveConnector,
}

__all__ = [
    "LIVE_CONNECTORS",
    "ConfluenceLiveConnector",
    "ConnectorAuthError",
    "ConnectorError",
    "GCalLiveConnector",
    "GDriveLiveConnector",
    "GitHubLiveConnector",
    "GmailLiveConnector",
    "JiraLiveConnector",
    "LinearLiveConnector",
    "NotionLiveConnector",
    "SlackLiveConnector",
    "ZendeskLiveConnector",
]
