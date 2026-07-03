"""Entrypoint for ``python -m context_engine.mcp_server [--http]``."""

from __future__ import annotations

import sys

from context_engine.mcp_server.server import main


def _run() -> None:
    http = "--http" in sys.argv[1:]
    main(http=http)


if __name__ == "__main__":
    _run()
