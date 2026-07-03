SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: setup run run-api run-ui run-worker ingest-demo test test-api test-ui test-e2e \
        coverage lint typecheck eval db-up db-migrate seed clean

setup: ## Install backend + frontend dependencies
	cd backend && uv sync --all-extras
	cd frontend && pnpm install

db-up: ## Start Postgres + Redis only
	$(COMPOSE) up -d db redis
	@until docker compose exec -T db pg_isready -U ce -d context_engine >/dev/null 2>&1; do sleep 1; done

db-migrate: db-up
	cd backend && uv run alembic upgrade head

seed: db-migrate ## Seed realistic demo organization data
	cd backend && uv run ctx seed --reset

ingest-demo: seed ## Alias required by spec: ingest demo data
	@echo "Demo organization ingested."

run: ## Run the full platform via docker compose
	$(COMPOSE) up --build

run-api: db-migrate ## Run API locally with reload
	cd backend && uv run uvicorn context_engine.api.app:app --factory --reload --port 8000

run-worker: db-up
	cd backend && uv run dramatiq context_engine.observability.worker --processes 1 --threads 2

run-ui: ## Run frontend dev server
	cd frontend && pnpm dev

test: test-api test-ui ## All tests

test-api: db-up ## Backend tests with coverage gate (>=85%)
	cd backend && uv run pytest

test-ui: ## Frontend tests with coverage gate (>=85%)
	cd frontend && pnpm test -- --coverage

test-e2e: ## Playwright E2E against the compose stack
	$(COMPOSE) up -d --build db redis api ui
	cd backend && uv run alembic upgrade head && uv run ctx seed --reset
	cd frontend && pnpm exec playwright install --with-deps chromium && pnpm e2e

coverage: ## Combined coverage reports
	cd backend && uv run pytest --cov-report=html --cov-report=xml || true
	cd frontend && pnpm test -- --coverage || true
	@echo "backend: backend/htmlcov/index.html · frontend: frontend/coverage/index.html"

lint:
	cd backend && uv run ruff check src tests seeds && uv run ruff format --check src tests seeds
	cd frontend && pnpm lint

typecheck:
	cd backend && uv run mypy src
	cd frontend && pnpm typecheck

eval: db-up ## Run the eval harness (baseline vs context engine) and print report
	cd backend && uv run ctx eval run --mode comparison

clean:
	$(COMPOSE) down -v
	rm -rf backend/.venv frontend/node_modules
