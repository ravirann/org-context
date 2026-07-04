#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

exec python -m context_engine.ingestion.scheduler
