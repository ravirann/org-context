"""Live source connectors (real HTTP), routed via ``config["mode"] == "live"``.

Each live connector implements the same ``Connector`` protocol as the demo
connectors but reaches a real upstream (GitHub, Jira, Slack, Confluence) through
the shared :mod:`context_engine.connectors.live.http` helper. Cursors live in
``source.sync_state`` and are advanced in place; the ingestion pipeline persists
the mutation after a successful sync.
"""

from __future__ import annotations

from context_engine.connectors.live.confluence import ConfluenceLiveConnector
from context_engine.connectors.live.github import GitHubLiveConnector
from context_engine.connectors.live.http import ConnectorAuthError, ConnectorError
from context_engine.connectors.live.jira import JiraLiveConnector
from context_engine.connectors.live.slack import SlackLiveConnector

# Live connectors are instantiated per-fetch (they read config off the Source),
# so the registry maps a source_type to its connector *class*.
LIVE_CONNECTORS: dict[str, type] = {
    GitHubLiveConnector.source_type: GitHubLiveConnector,
    JiraLiveConnector.source_type: JiraLiveConnector,
    SlackLiveConnector.source_type: SlackLiveConnector,
    ConfluenceLiveConnector.source_type: ConfluenceLiveConnector,
}

__all__ = [
    "LIVE_CONNECTORS",
    "ConfluenceLiveConnector",
    "ConnectorAuthError",
    "ConnectorError",
    "GitHubLiveConnector",
    "JiraLiveConnector",
    "SlackLiveConnector",
]
