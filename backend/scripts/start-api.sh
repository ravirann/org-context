#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

alembic upgrade head
python -m seeds.demo_data --if-empty
exec uvicorn context_engine.api.app:app --factory --host 0.0.0.0 --port 8000
