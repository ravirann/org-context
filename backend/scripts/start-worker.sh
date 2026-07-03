#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

exec dramatiq context_engine.observability.worker --processes 1 --threads 4
